"""Structural/packaging regression tests; these do not judge generated prose."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from scripts.build_skillhub_release import module_text

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/rw-phd-write'
SPEC = importlib.util.spec_from_file_location('phd_write_self_check', SKILL / 'scripts/self_check.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ContrastContractTests(unittest.TestCase):
    def setUp(self):
        self.contracts = json.loads((SKILL / 'references/behavior-tests.json').read_text())
        self.rows = [row for row in self.contracts if row.get('gate') == 'abstract_contrast_v1']

    def test_paired_contracts_valid(self):
        self.assertEqual(CHECK.validate_contrast_contracts(self.contracts), [])

    def test_missing_and_duplicate_cases_fail(self):
        for rows in (self.rows[:-1], self.rows + [copy.deepcopy(self.rows[0])]):
            with self.subTest(count=len(rows)):
                self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_both_generation_and_review_prompts_required(self):
        for key in ('generation_prompt', 'prompt'):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = ''
            self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_preservation_control_cannot_expect_deletion(self):
        rows = copy.deepcopy(self.rows)
        next(row for row in rows if row['group'] == 'preserve')['review_expectation']['actions'] = ['DELETE']
        self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_diagnosis_and_action_are_not_interchangeable(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['review_expectation']['verdicts'] = ['MERGE']
        self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_tuned_fixtures_are_not_labelled_holdout(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['evaluation_set'] = 'holdout'
        self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_synthetic_inputs_and_all_dimensions_required(self):
        for key, value in (('fixture_kind', 'personal_manuscript'), ('evaluation_dimensions', ['missed_issue'])):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_malformed_expectation_is_reported(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['review_expectation'] = None
        self.assertTrue(CHECK.validate_contrast_contracts(rows))

    def test_compact_package_preserves_reference_and_fixture_data(self):
        rendered = module_text(SKILL)
        ref = 'abstract-contrast-gate.md'
        anchor = 'ref-abstract-contrast-gate-md'
        self.assertIn(f'<a id="{anchor}"></a>', rendered)
        self.assertIn(f'modules/rw-phd-write.md#{anchor}', rendered)
        self.assertNotIn(f'references/{ref}', rendered)
        # Compare the complete reference after the documented path transform,
        # not just the presence of the gate's title or one keyword.
        from scripts.build_skillhub_release import compact_paths, public_text
        reference = (SKILL / 'references' / ref).read_text()
        expected = compact_paths(public_text(reference, Path(ref)), SKILL).strip()
        self.assertIn(expected, rendered)
        section = rendered.split('### behavior-tests.json\n\n', 1)[1].split('\n<a id=', 1)[0]
        packaged = {row['id']: row for row in json.loads(section)}
        for row in self.rows:
            self.assertEqual(row, packaged[row['id']])


if __name__ == '__main__':
    unittest.main()
