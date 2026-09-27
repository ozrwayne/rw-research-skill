"""Synthetic PDF and case-integrity tests; no real manuscripts or remote calls."""
import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import paper_case as P

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.pdf=self.root/'paper.pdf'; self.out=self.root/'case'
        with P.fitz.open() as doc:
            page=doc.new_page(); page.insert_text((50,50),'Synthetic evidence.');doc.save(self.pdf)
        self.args=SimpleNamespace(pdf=self.pdf,output=self.out,title='Synthetic',doi='',zotero_library_id=None,zotero_key='',zotero_attachment_key='')
        P.build_case(self.args)
    def load(self,path): return json.loads((self.out/path).read_text())
    def save(self,path,data): P.write_json(self.out/path,data)
    def scaffold(self): P.scaffold_command(SimpleNamespace(output=self.out,force=False))
    def assemble(self):
        self.scaffold()
        P.mark_stage_command(SimpleNamespace(output=self.out,stage='report_assembled',artifact='report.md',status='complete',upstream=[f'stages/{name}' for name,_,_ in P.REPORT_STAGES]))
    def audit(self):
        report=self.out/'report.md'
        value={'schema_version':'rw-claim-audit/v1','document_id':'DOC-SYNTHETIC','document_path':str(report),'document_hash':P.sha256_file(report),'audited_at':'2026-09-19T00:00:00Z','claims':[{'id':'C1','text':'synthetic','location':'p1','claim_type':'other','notes':'','verdict':'VERIFIED','source_refs':[{'id':'S1','source_pointer':str(self.pdf),'locator':'p1','support_note':'Synthetic original-source support checked.','source_path':str(self.pdf),'source_sha256':P.sha256_file(self.pdf)}]}]}
        self.save('audit/claim-audit.json',value); return value
    def preview(self):
        return P.litnet_preview_command(SimpleNamespace(output=self.out,claim_audit=self.out/'audit/claim-audit.json',litnet_work='',zotero_record=''))
    def test_missing_text_is_not_valid(self):
        (self.out/'evidence/text-units.jsonl').unlink()
        self.assertTrue(P.validate_case(self.out))
    def test_changed_text_is_stale(self):
        with (self.out/'evidence/text-units.jsonl').open('a') as f:f.write('{}\n')
        self.assertIn('STALE',';'.join(P.validate_case(self.out)))
    def test_rebuild_preserves_existing_case(self):
        target=self.out/'evidence/claim-candidates.jsonl';target.write_text('precious\n')
        with self.assertRaises(ValueError):P.build_case(self.args)
        self.assertEqual(target.read_text(),'precious\n')
    def test_failed_build_leaves_no_partial_case(self):
        self.args.output=self.root/'newcase'
        with patch.object(P,'extract_visual_evidence',side_effect=ValueError('synthetic failure')):
            with self.assertRaises(ValueError):P.build_case(self.args)
        self.assertFalse(self.args.output.exists())
    def test_path_traversal_in_case_manifest_is_blocked(self):
        case=self.load('case.json');case['artifacts']['litnet_preview']='../outside.json';self.save('case.json',case)
        self.assertTrue(P.validate_case(self.out));self.assertFalse((self.root/'outside.json').exists())
    def test_symlink_scaffold_does_not_write_outside(self):
        outside=self.root/'outside';outside.mkdir();(self.out/'stages').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.scaffold()
        self.assertEqual(list(outside.iterdir()),[])
    def test_missing_state_is_not_valid(self):
        (self.out/'stage-state.json').unlink();self.assertTrue(P.validate_case(self.out))
    def test_stale_source_cannot_be_remarked(self):
        (self.out/'a.md').write_text('synthetic');self.pdf.write_bytes(b'changed')
        with self.assertRaises(ValueError):P.mark_stage_command(SimpleNamespace(output=self.out,stage='research_structure',artifact='a.md',upstream=[],status='complete'))
    def test_unassembled_report_cannot_preview(self):
        self.scaffold();self.audit()
        with self.assertRaisesRegex(ValueError,'report_assembled'):self.preview()
    def test_wrong_report_audit_is_blocked(self):
        self.assemble();data=self.audit();other=self.root/'other.md';other.write_text('other')
        data.update(document_path=str(other),document_hash=P.sha256_file(other));self.save('audit/claim-audit.json',data)
        with self.assertRaisesRegex(ValueError,'bind'):self.preview()
    def test_empty_source_object_does_not_pass(self):
        self.assemble();data=self.audit();data['claims'][0]['source_refs']=[{}]
        self.assertEqual(P.claim_gate(data)[0],'BLOCK')
    def test_unhashed_source_is_review_only(self):
        self.assemble();data=self.audit();ref=data['claims'][0]['source_refs'][0];del ref['source_path'];del ref['source_sha256']
        self.assertEqual(P.claim_gate(data)[0],'REVIEW')
    def test_block_does_not_generate_preview(self):
        self.assemble();data=self.audit();data['claims'][0]['verdict']='UNSUPPORTED';self.save('audit/claim-audit.json',data)
        with self.assertRaisesRegex(ValueError,'BLOCK'):self.preview()
        self.assertFalse((self.out/'litnet-writeback-preview.json').exists())
    def test_changed_claim_source_snapshot_is_blocked(self):
        self.assemble();data=self.audit();snapshot=self.root/'snapshot.txt';snapshot.write_text('first')
        data['claims'][0]['source_refs'][0].update(source_path=str(snapshot),source_sha256=P.sha256_file(snapshot))
        self.save('audit/claim-audit.json',data);snapshot.write_text('second')
        with self.assertRaisesRegex(ValueError,'snapshot'):self.preview()
    def test_valid_complete_case_previews_without_writing_external(self):
        self.assemble();self.audit();self.assertEqual(self.preview(),0)
        result=self.load('litnet-writeback-preview.json');self.assertEqual(result['claim_gate'],'PASS');self.assertFalse(result['write_performed'])

    def test_late_scaffold_symlink_preserves_earlier_stage(self):
        self.scaffold();first=self.out/'stages/01-question.md';first.write_text('human original')
        last=self.out/'stages/05-conclusion.md';last.unlink();target=self.root/'outside.md';target.write_text('outside');last.symlink_to(target)
        with self.assertRaises(ValueError):P.scaffold_command(SimpleNamespace(output=self.out,force=True))
        self.assertEqual(first.read_text(),'human original');self.assertEqual(target.read_text(),'outside')
    def test_preview_cannot_replace_source_snapshot(self):
        self.assemble();data=self.audit();target=self.out/'litnet-writeback-preview.json';target.write_text('source snapshot')
        data['claims'][0]['source_refs'][0].update(source_path=str(target),source_sha256=P.sha256_file(target));self.save('audit/claim-audit.json',data)
        with self.assertRaisesRegex(ValueError,'snapshot must differ'):self.preview()
        self.assertEqual(target.read_text(),'source snapshot')

    def test_duplicate_case_json_key_is_not_accepted(self):
        path=self.out/'case.json';raw=path.read_text();path.write_text(raw.replace('{','{"schema":"ambiguous",',1))
        self.assertIn('duplicate JSON key',';'.join(P.validate_case(self.out)))

    def test_upstream_required_fields_cannot_be_dropped_for_preview(self):
        self.assemble();data=self.audit()
        del data['claims'][0]['claim_type']
        del data['claims'][0]['notes']
        del data['claims'][0]['source_refs'][0]['support_note']
        self.save('audit/claim-audit.json',data)
        self.assertTrue(P.validate_claim_audit(data))
        self.assertEqual(P.claim_gate(data)[0],'BLOCK')
        with self.assertRaisesRegex(ValueError,'invalid claim audit'):self.preview()
        self.assertFalse((self.out/'litnet-writeback-preview.json').exists())

    def test_invalid_upstream_contract_never_becomes_downstream_pass(self):
        self.assemble();valid=self.audit()
        changes=[]
        for field in ['schema_version','document_id','document_path','document_hash','audited_at','claims']:
            changes.append(('missing '+field,lambda d,f=field:d.pop(f)))
        for field in ['id','text','location','claim_type','source_refs','verdict','notes']:
            changes.append(('missing claim '+field,lambda d,f=field:d['claims'][0].pop(f)))
        for field in ['id','source_pointer','locator','support_note']:
            changes.append(('blank source '+field,lambda d,f=field:d['claims'][0]['source_refs'][0].__setitem__(f,' ')))
        changes.extend([
            ('bad type',lambda d:d['claims'][0].__setitem__('claim_type',[])),
            ('bad notes',lambda d:d['claims'][0].__setitem__('notes',{})),
            ('bad verdict',lambda d:d['claims'][0].__setitem__('verdict',[])),
            ('bad document hash',lambda d:d.__setitem__('document_hash','A'*64)),
            ('bad source hash',lambda d:d['claims'][0]['source_refs'][0].__setitem__('source_sha256','A'*64)),
            ('missing paired source path',lambda d:d['claims'][0]['source_refs'][0].pop('source_path')),
            ('missing paired source hash',lambda d:d['claims'][0]['source_refs'][0].pop('source_sha256')),
            ('duplicate source ids',lambda d:d['claims'][0]['source_refs'].append(copy.deepcopy(d['claims'][0]['source_refs'][0]))),
            ('duplicate claim ids',lambda d:d['claims'].append(copy.deepcopy(d['claims'][0]))),
            ('nonfinite data',lambda d:d.__setitem__('extra',float('nan'))),
        ])
        for label,change in changes:
            with self.subTest(case=label):
                data=copy.deepcopy(valid);change(data)
                self.assertTrue(P.validate_claim_audit(data))
                self.assertEqual(P.claim_gate(data)[0],'BLOCK')

    def test_access_failure_retains_attempted_source_contract(self):
        self.assemble();data=self.audit();data['claims'][0]['verdict']='UNVERIFIABLE_ACCESS'
        data['claims'][0]['source_refs']=[]
        self.assertTrue(P.validate_claim_audit(data))
        self.assertEqual(P.claim_gate(data)[0],'BLOCK')

    def test_valid_snapshot_contract_still_previews_as_audited(self):
        self.assemble();data=self.audit()
        self.assertEqual(P.validate_claim_audit(data),[])
        self.assertEqual(P.claim_gate(data)[0],'PASS')
        self.assertEqual(self.preview(),0)
        preview=self.load('litnet-writeback-preview.json')
        self.assertEqual(preview['deep_read_status'],'audited')
        self.assertFalse(preview['write_performed'])

if __name__=='__main__':unittest.main()
