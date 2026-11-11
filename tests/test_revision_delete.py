"""Execute real v2 patch CLI; no private manuscript or network access."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'skills/rw-revision-patch/scripts/revision_patch.py'


class ExplicitDeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source.md'; self.doc=self.root/'anchored.md'
        self.manifest=self.root/'manifest.json'; self.patch=self.root/'patch.json'
        self.output=self.root/'output.md'; self.report=self.root/'report.json'
        self.source.write_bytes(b'---\r\ntitle: Example\r\n---\r\n# Heading\r\n\r\nOne.\r\n\r\nTwo.\r\n\r\nThree.\r\n\r\nFour.\r\n')
        r=self.cli('anchor',self.source,'--output',self.doc,'--manifest',self.manifest)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.m=json.loads(self.manifest.read_text()); self.before=self.doc.read_bytes(); self.original=self.source.read_bytes()

    def cli(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True)

    def operation(self,index,op='delete'):
        row=self.m['blocks'][index-1]
        result={'op':op,'block_id':row['block_id'],'expected_hash':row['block_hash'],'reason':'Approved synthetic test','issue_ids':['SYN-1']}
        if op=='replace':result['new_text']='Updated.'
        return result

    def prepare(self,ops,version='v2'):
        self.patch.write_text(json.dumps({'schema_version':'rw-revision-patch/'+version,'base_document_hash':self.m['base_document_hash'],'operations':ops}))

    def apply(self,*extra,confirm=None):
        confirm=confirm if confirm is not None else hashlib.sha256(self.patch.read_bytes()).hexdigest()
        return self.cli('apply',self.doc,'--manifest',self.manifest,'--patch',self.patch,'--output',self.output,'--report',self.report,'--confirm-patch-sha256',confirm,*extra)

    def assert_rejected(self,ops,version='v2',extra=()):
        self.prepare(ops,version); result=self.apply(*extra)
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertFalse(self.output.exists()); self.assertFalse(self.report.exists())
        self.assertEqual(self.before,self.doc.read_bytes()); self.assertEqual(self.original,self.source.read_bytes())

    def span(self,index):
        start=self.before.index(f'<!--rw-block:B{index:04d}-->'.encode())
        nxt=f'<!--rw-block:B{index+1:04d}-->'.encode()
        end=self.before.index(nxt) if nxt in self.before else len(self.before)
        return self.before[start:end]

    def test_middle_delete_preserves_every_other_byte(self):
        self.prepare([self.operation(3)]); r=self.apply()
        self.assertEqual(0,r.returncode,r.stdout+r.stderr)
        self.assertEqual(self.before.replace(self.span(3),b''),self.output.read_bytes())
        self.assertEqual(self.original,self.source.read_bytes());self.assertEqual(self.before,self.doc.read_bytes())
        report=json.loads(self.report.read_text())
        self.assertEqual((1,4,4), (report['deleted_blocks'],report['remaining_blocks'],report['preserved_blocks']))
        self.assertEqual(report['schema_version'],'rw-revision-report/v2')
        self.assertIsNone(report['changes'][0]['new_hash'])

    def test_first_block_delete_preserves_frontmatter(self):
        # Replace title with an ordinary paragraph, then re-anchor to update hashes.
        self.doc.write_bytes(self.before.replace(b'# Heading',b'Opening'))
        newdoc=self.root/'fresh.md';newman=self.root/'fresh.json'
        self.cli('anchor',self.doc,'--output',newdoc,'--manifest',newman)
        self.doc=newdoc;self.manifest=newman;self.m=json.loads(newman.read_text());self.before=newdoc.read_bytes()
        self.prepare([self.operation(1)]);r=self.apply()
        self.assertEqual(0,r.returncode,r.stdout)
        self.assertEqual(self.before.replace(self.span(1),b''),self.output.read_bytes())

    def test_last_and_adjacent_deletions(self):
        self.prepare([self.operation(4),self.operation(5)]);r=self.apply()
        self.assertEqual(0,r.returncode,r.stdout)
        self.assertEqual(self.before.replace(self.span(4),b'').replace(self.span(5),b''),self.output.read_bytes())

    def test_mixed_replace_delete_and_reanchor(self):
        self.prepare([self.operation(3),self.operation(4,'replace')]);r=self.apply()
        self.assertEqual(0,r.returncode,r.stdout)
        self.assertEqual(self.before.replace(self.span(3),b'').replace(b'Three.',b'Updated.'),self.output.read_bytes())
        r=self.cli('anchor',self.output,'--output',self.root/'next.md','--manifest',self.root/'next.json')
        self.assertEqual(0,r.returncode,r.stdout)
        rows=json.loads((self.root/'next.json').read_text())['blocks']
        self.assertEqual(['B0001','B0002','B0004','B0005'],[r['block_id'] for r in rows])
        r=self.cli('check',self.output,'--manifest',self.manifest,'--patch',self.patch)
        self.assertNotEqual(0,r.returncode)

    def test_v1_rejects_delete(self):self.assert_rejected([self.operation(2)],'v1')

    def test_empty_replace_is_not_delete(self):
        op=self.operation(2,'replace');op['new_text']='\n';self.assert_rejected([op])

    def test_delete_rejects_replacement_field(self):
        for value in [None,'','new']:
            with self.subTest(value=value):
                op=self.operation(2);op['new_text']=value;self.assert_rejected([op])

    def test_stale_hash_and_duplicate_and_bad_id(self):
        op=self.operation(2);op['expected_hash']='stale';self.assert_rejected([op])
        self.assert_rejected([self.operation(2),self.operation(2)])
        op=self.operation(2);op['block_id']='B0999';self.assert_rejected([op])

    def test_invalid_second_operation_blocks_whole_batch(self):
        bad=self.operation(3);bad['reason']='';self.assert_rejected([self.operation(2),bad])

    def test_heading_and_delete_all_rejected_even_with_large_flag(self):
        self.assert_rejected([self.operation(1)])
        self.assert_rejected([self.operation(i) for i in range(1,6)],extra=('--allow-large-patch',))

    def test_setext_heading_with_crlf_is_protected(self):
        self.doc.write_bytes(self.before.replace(b'One.',b'Section\r\n---\r\nDetail.'))
        newdoc=self.root/'setext.md';newman=self.root/'setext.json'
        r=self.cli('anchor',self.doc,'--output',newdoc,'--manifest',newman)
        self.assertEqual(0,r.returncode,r.stdout)
        self.doc=newdoc;self.manifest=newman;self.m=json.loads(newman.read_text());self.before=newdoc.read_bytes()
        self.assert_rejected([self.operation(2)])

    def test_large_delete_needs_flag(self):
        ops=[self.operation(i) for i in range(2,6)];self.assert_rejected(ops)
        r=self.apply('--allow-large-patch');self.assertEqual(0,r.returncode,r.stdout)

    def test_confirmation_and_stale_document(self):
        self.prepare([self.operation(2)])
        r=self.apply(confirm='0'*64);self.assertNotEqual(0,r.returncode);self.assertFalse(self.output.exists())
        self.doc.write_bytes(self.before+b'changed')
        r=self.apply();self.assertNotEqual(0,r.returncode);self.assertFalse(self.output.exists())

    def test_malformed_operation_does_not_write(self):
        self.assert_rejected([self.operation(2),None])
        op=self.operation(2);op['block_id']=[];self.assert_rejected([op])

if __name__=='__main__':unittest.main()
