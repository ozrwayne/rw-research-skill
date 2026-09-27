"""Mutate synthetic copies to verify structural checks fail closed."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('skill_contracts',ROOT/'scripts/check_skill_contracts.py')
CHECK=importlib.util.module_from_spec(spec);spec.loader.exec_module(CHECK)
class SkillContractsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'rw-synthetic';refs=self.root/'references';refs.mkdir(parents=True)
        (self.root/'SKILL.md').write_text('---\nname: rw-synthetic\ndescription: Synthetic test.\n---\n# Synthetic\n')
        (refs/'atoms.jsonl').write_text(json.dumps({'id':'A1','knowledge':'Synthetic','source':'fixture'})+'\n')
        (refs/'behavior-tests.json').write_text(json.dumps([{'id':'C1','prompt':'Synthetic','expect':{'status':'review'}}]))
        (refs/'axioms.md').write_text('## AXIOM-01\n- 来源原子：`A1`。\n')
        for name in ['source-map.md','acceptance.md']:(refs/name).write_text('# Synthetic\n')
    def test_valid_fixture_passes(self):self.assertEqual(CHECK.validate_skill(self.root),[])
    def test_missing_contract_fails_closed(self):
        (self.root/'references/behavior-tests.json').unlink();self.assertTrue(CHECK.validate_skill(self.root))
    def test_duplicate_atom_id_is_detected(self):
        p=self.root/'references/atoms.jsonl';p.write_text(p.read_text()*2)
        self.assertIn('duplicate knowledge atom id',' '.join(CHECK.validate_skill(self.root)))
    def test_orphan_axiom_reference_is_detected(self):
        (self.root/'references/axioms.md').write_text('- 来源原子：`missing`。')
        self.assertIn('missing atom',' '.join(CHECK.validate_skill(self.root)))
    def test_malformed_contract_not_counted_as_coverage(self):
        (self.root/'references/behavior-tests.json').write_text('[{"id":"x","prompt":"test","must_do":"bad"}]')
        self.assertTrue(CHECK.validate_skill(self.root))
    def test_missing_declared_resource_is_detected(self):
        with (self.root/'SKILL.md').open('a') as f:f.write('Read `scripts/missing.py`.\n')
        self.assertIn('missing resource',' '.join(CHECK.validate_skill(self.root)))
    def test_code_syntax_error_fails(self):
        p=self.root/'scripts';p.mkdir();(p/'broken.py').write_text('def broken(\n')
        self.assertTrue(CHECK.validate_skill(self.root))
    def test_duplicate_frontmatter_fails(self):
        p=self.root/'SKILL.md';p.write_text(p.read_text().replace('description:','name: rw-other\ndescription:'))
        self.assertTrue(CHECK.validate_skill(self.root))
    def test_nonfinite_json_fails(self):
        (self.root/'references/example.json').write_text('{"n": NaN}')
        self.assertTrue(CHECK.validate_skill(self.root))
    def test_overflow_and_ambiguous_json_fail(self):
        for value in ('{"n":1e999}', '{"n":1,"n":2}'):
            with self.subTest(value=value):
                (self.root/'references/example.json').write_text(value)
                self.assertTrue(CHECK.validate_skill(self.root))
if __name__=='__main__':unittest.main()
