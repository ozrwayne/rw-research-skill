"""Contracts and packaging only; not semantic quality or model evaluation."""
import copy
import json
import unittest
from tests.test_phd_write_contrast import CHECK, SKILL
from scripts.build_skillhub_release import module_text, compact_paths, public_text
from pathlib import Path


class NecessityContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = [r for r in json.loads((SKILL/'references/behavior-tests.json').read_text()) if r.get('gate') == 'content_necessity_v1']

    def test_contracts_valid(self):
        self.assertEqual([], CHECK.validate_necessity_contracts(self.rows))

    def test_missing_and_duplicate_fail(self):
        for rows in (self.rows[:-1], self.rows+[self.rows[0]]):
            self.assertTrue(CHECK.validate_necessity_contracts(rows))

    def test_bad_schema_fails(self):
        for key, value in [('prompt', ''), ('must_do', []), ('must_not', None), ('mode', 'unknown'), ('fixture_kind', 'private'), ('evaluation_set', 'holdout'), ('execution_status', 'passed')]:
            with self.subTest(key=key):
                rows=copy.deepcopy(self.rows); rows[0][key]=value
                self.assertTrue(CHECK.validate_necessity_contracts(rows))

    def test_pair_and_turn_inputs_required(self):
        for mode,key in [('paired','variant_prompts'),('multi_turn','follow_up_prompts')]:
            rows=copy.deepcopy(self.rows)
            next(r for r in rows if r['mode']==mode)[key]=[]
            self.assertTrue(CHECK.validate_necessity_contracts(rows))

    def test_compact_package_preserves_gate_and_contracts(self):
        rendered=module_text(SKILL)
        ref='content-necessity-gate.md'
        self.assertIn('modules/rw-phd-write.md#ref-content-necessity-gate-md', rendered)
        self.assertIn(compact_paths(public_text((SKILL/'references'/ref).read_text(),Path(ref)),SKILL).strip(), rendered)
        section=rendered.split('### behavior-tests.json\n\n',1)[1].split('\n<a id=',1)[0]
        packaged={r['id']:r for r in json.loads(section)}
        for r in self.rows:self.assertEqual(r,packaged[r['id']])

if __name__=='__main__':unittest.main()
