import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("revision_patch", Path(__file__).with_name("revision_patch.py"))
rp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rp
spec.loader.exec_module(rp)


class PatchRegression(unittest.TestCase):
    def test_anchor_manifest_cannot_overwrite_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source.md'; source.write_text('ORIGINAL\n')
            args=argparse.Namespace(input=str(source), output=str(root/'out.md'), manifest=str(source), force=True)
            with self.assertRaises(ValueError):
                rp.command_anchor(args)
            self.assertEqual(source.read_text(), 'ORIGINAL\n')

    def test_anchor_paths_must_be_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source.md'; source.write_text('ORIGINAL\n')
            target=root/'out.md'
            with self.assertRaises(ValueError):
                rp.command_anchor(argparse.Namespace(input=str(source), output=str(target), manifest=str(target), force=True))
            self.assertFalse(target.exists())

    def test_hardlink_alias_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source.md'; source.write_text('ORIGINAL\n'); alias=root/'alias.md'; alias.hardlink_to(source)
            with self.assertRaises(ValueError):
                rp.command_anchor(argparse.Namespace(input=str(source), output=str(alias), manifest=str(root/'m.json'), force=True))
            self.assertEqual(source.read_text(), 'ORIGINAL\n')

    def test_roundtrip_preserves_bytes_and_fenced_blank_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source.md'; output=root/'anchored.md'; manifest=root/'m.json'
            raw=b'\r\nTitle\r\n\r\n\r\n```python\r\na = 1\r\n\r\nb = 2\r\n```\r\n\r\nEnd'
            source.write_bytes(raw)
            rp.command_anchor(argparse.Namespace(input=str(source), output=str(output), manifest=str(manifest), force=False))
            text=output.read_bytes().decode()
            self.assertEqual(rp.MARKER_RE.sub('', text).encode(), raw)
            self.assertEqual(sum('```python' in block.text for block in rp.parse_anchored(text)),1)
            self.assertTrue(any('a = 1\r\n\r\nb = 2' in block.text for block in rp.parse_anchored(text)))

    def make_patch(self, root):
        source=root/'source.md'; output=root/'anchored.md'; manifest=root/'m.json'; patch=root/'p.json'
        source.write_text('One\n\nTwo\n\nThree\n')
        rp.command_anchor(argparse.Namespace(input=str(source), output=str(output), manifest=str(manifest), force=False))
        m=json.loads(manifest.read_text()); block=m['blocks'][0]
        patch.write_text(json.dumps({'schema_version':rp.PATCH_VERSION,'base_document_hash':m['base_document_hash'],'operations':[{'op':'replace','block_id':block['block_id'],'expected_hash':block['block_hash'],'new_text':'Changed','reason':'synthetic','issue_ids':['I-1']}]}))
        return source, output, manifest, patch

    def args(self, root, output, manifest, patch, **changes):
        import hashlib
        args=dict(document=str(output),manifest=str(manifest),patch=str(patch),output=str(root/'revised.md'),report=str(root/'report.json'),allow_large_patch=False,force=True,confirm_patch_sha256=hashlib.sha256(patch.read_bytes()).hexdigest())
        args.update(changes); return argparse.Namespace(**args)

    def test_apply_report_cannot_replace_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source, output, manifest, patch=self.make_patch(root); before=output.read_bytes()
            with self.assertRaises(ValueError):
                rp.command_apply(self.args(root,output,manifest,patch,report=str(output)))
            self.assertEqual(output.read_bytes(),before)

    def test_apply_requires_exact_patch_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _, output, manifest, patch=self.make_patch(root)
            self.assertEqual(rp.command_apply(self.args(root,output,manifest,patch,confirm_patch_sha256=None)),2)
            self.assertFalse((root/'revised.md').exists())

    def test_apply_preserves_untouched_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _, output, manifest, patch=self.make_patch(root)
            self.assertEqual(rp.command_apply(self.args(root,output,manifest,patch)),0)
            self.assertEqual((root/'revised.md').read_bytes(),output.read_bytes().replace(b'One',b'Changed'))

    def test_empty_issue_ids_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _, output, manifest, patch=self.make_patch(root)
            p=json.loads(patch.read_text());p['operations'][0]['issue_ids']=[];patch.write_text(json.dumps(p))
            self.assertTrue(rp.validate_inputs(output,manifest,patch,False)[3])

    def test_yaml_frontmatter_is_not_broken_by_marker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'s.md';output=root/'a.md';manifest=root/'m.json'
            raw=b'---\ntitle: Synthetic\n---\n\n# Heading\n\nParagraph\n'
            source.write_bytes(raw)
            rp.command_anchor(argparse.Namespace(input=str(source),output=str(output),manifest=str(manifest),force=False))
            self.assertTrue(output.read_bytes().startswith(b'---\ntitle: Synthetic\n---\n'))
            self.assertEqual(rp.MARKER_RE.sub('',output.read_bytes().decode()).encode(),raw)

    def test_failed_second_output_commit_rolls_back_first(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); a=root/'a';b=root/'b';a.write_bytes(b'OLD A');b.write_bytes(b'OLD B')
            original=rp.os.replace
            calls=[]
            def fail_second(src,dst):
                calls.append(dst)
                if len(calls)==2:raise OSError('synthetic replacement failure')
                return original(src,dst)
            with patch.object(rp.os,'replace',side_effect=fail_second):
                with self.assertRaises(OSError):rp.write_outputs({a:'NEW A',b:'NEW B'})
            self.assertEqual(a.read_bytes(),b'OLD A');self.assertEqual(b.read_bytes(),b'OLD B')
            self.assertEqual(sorted(p.name for p in root.iterdir()),['a','b'])

    def test_changed_patch_confirmation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); _,output,manifest,patch=self.make_patch(root);args=self.args(root,output,manifest,patch)
            patch.write_text(patch.read_text()+' ')
            self.assertEqual(rp.command_apply(args),2)
            self.assertFalse((root/'revised.md').exists())

    def test_manifest_extra_or_duplicate_blocks_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,output,manifest,patch=self.make_patch(root)
            data=json.loads(manifest.read_text());data['blocks'].append(data['blocks'][0]);manifest.write_text(json.dumps(data))
            self.assertTrue(rp.validate_inputs(output,manifest,patch,False)[3])

    def test_invalid_report_parent_does_not_leave_partial_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,output,manifest,patch=self.make_patch(root)
            obstacle=root/'not-a-directory';obstacle.write_bytes(b'unchanged')
            args=self.args(root,output,manifest,patch,report=str(obstacle/'report.json'))
            with self.assertRaises(OSError):rp.command_apply(args)
            self.assertFalse((root/'revised.md').exists())
            self.assertEqual(obstacle.read_bytes(),b'unchanged')

if __name__=='__main__': unittest.main()
