"""Structural checks for the plain-claim gate fixtures. These do not judge prose."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/rw-phd-write"
SPEC = importlib.util.spec_from_file_location("phd_write_self_check", SKILL / "scripts/self_check.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class PlainClaimContractTests(unittest.TestCase):
    def setUp(self):
        self.contracts = json.loads((SKILL / "references/behavior-tests.json").read_text())
        self.rows = [row for row in self.contracts if row.get("gate") == "plain_claim_v1"]

    def test_valid_set_passes(self):
        self.assertEqual(CHECK.validate_plain_claim_contracts(self.contracts), [])

    def test_missing_category_coverage_fails(self):
        rows = [row for row in self.rows if not (row.get("writing_category") == "defensive" and row.get("group") == "revise")]
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_missing_collocation_coverage_fails(self):
        rows = [row for row in self.rows if row.get("writing_category") != "collocation"]
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_missing_hard_marker_coverage_fails(self):
        rows = [row for row in self.rows if not (row.get("writing_category") == "hard_marker" and row.get("group") == "preserve")]
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_duplicate_ids_fail(self):
        rows = self.rows + [copy.deepcopy(self.rows[0])]
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_empty_prompts_fail(self):
        for key in ("generation_prompt", "prompt"):
            rows = copy.deepcopy(self.rows)
            rows[0][key] = "   "
            self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_preserve_cannot_expect_delete(self):
        rows = copy.deepcopy(self.rows)
        next(row for row in rows if row["group"] == "preserve")["review_expectation"]["actions"] = ["DELETE"]
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))

    def test_holdout_label_fails(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["evaluation_set"] = "holdout"
        self.assertTrue(CHECK.validate_plain_claim_contracts(rows))


if __name__ == "__main__":
    unittest.main()
