import copy
import json
import tempfile
import unittest
from pathlib import Path
import claim_audit as ca

class ClaimAuditRegression(unittest.TestCase):
    def fixture(self, root):
        doc=root/'doc.md'; source=root/'paper.txt'; doc.write_text('The value is 12.'); source.write_text('Twelve observations.')
        data={'schema_version':ca.SCHEMA_VERSION,'document_id':'D','document_path':str(doc),'document_hash':ca.file_hash(doc),'audited_at':ca.now(),'claims':[{'id':'C','text':'The value is 12.','location':'p1','claim_type':'quantitative','source_refs':[{'id':'S','source_pointer':'paper.txt','locator':'p1','support_note':'value matches','source_path':'paper.txt','source_sha256':ca.file_hash(source)}],'verdict':'VERIFIED','notes':''}]}
        return data,source

    def test_valid_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); data,_=self.fixture(root)
            self.assertEqual(ca.validate_audit(data,root/'audit.json'),[])
            self.assertEqual(ca.gate_status(data),'PASS')

    def test_changed_source_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); data,source=self.fixture(root);source.write_text('Now different')
            self.assertTrue(ca.validate_audit(data,root/'audit.json'))

    def test_legacy_unhashed_verified_is_review(self):
        with tempfile.TemporaryDirectory() as d:
            data,_=self.fixture(Path(d));ref=data['claims'][0]['source_refs'][0];ref.pop('source_path');ref.pop('source_sha256')
            self.assertEqual(ca.gate_status(data),'REVIEW')

    def test_empty_claim_text_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data,_=self.fixture(Path(d));data['claims'][0]['text']=' '
            self.assertTrue(ca.validate(data))

    def test_not_applicable_requires_explanation(self):
        with tempfile.TemporaryDirectory() as d:
            data,_=self.fixture(Path(d));data['claims'][0]['verdict']='NOT_APPLICABLE'
            self.assertTrue(ca.validate(data))

    def test_unhashable_enum_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data,_=self.fixture(Path(d));data['claims'][0]['verdict']=[]
            self.assertTrue(ca.validate(data))

    def test_nan_and_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.json'
            for text in ('{"x":NaN}','{"x":1,"x":2}'):
                path.write_text(text)
                with self.assertRaises(ValueError):ca.load(path)

if __name__=='__main__':unittest.main()
