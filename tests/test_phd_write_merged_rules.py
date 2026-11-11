"""Structural checks for the merged-rule fixtures. These do not judge model behaviour."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/rw-phd-write"
SPEC = importlib.util.spec_from_file_location("phd_write_self_check_merged", SKILL / "scripts/self_check.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class MergedRuleContractTests(unittest.TestCase):
    def setUp(self):
        self.contracts = json.loads((SKILL / "references/behavior-tests.json").read_text())
        self.rows = [row for row in self.contracts if row.get("gate") == "merged_rules_v1"]

    def test_valid_set_passes(self):
        self.assertEqual(CHECK.validate_merged_rule_contracts(self.contracts), [])

    def test_missing_dont_contract_fails(self):
        rows = [row for row in self.rows if not (row.get("rule") == "verbatim_numbers" and row.get("group") == "dont")]
        self.assertTrue(CHECK.validate_merged_rule_contracts(rows))

    def test_unknown_rule_or_group_fails(self):
        for key, value in (("rule", "not_a_rule"), ("group", "revise")):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            self.assertTrue(CHECK.validate_merged_rule_contracts(rows))

    def test_duplicate_ids_fail(self):
        rows = self.rows + [copy.deepcopy(self.rows[0])]
        self.assertTrue(CHECK.validate_merged_rule_contracts(rows))

    def test_empty_prompts_fail(self):
        for key in ("generation_prompt", "prompt"):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = "   "
            self.assertTrue(CHECK.validate_merged_rule_contracts(rows))

    def test_holdout_or_executed_label_fails(self):
        for key, value in (("evaluation_set", "holdout"), ("execution_status", "passed"), ("fixture_kind", "real")):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            self.assertTrue(CHECK.validate_merged_rule_contracts(rows))


if __name__ == "__main__":
    unittest.main()
