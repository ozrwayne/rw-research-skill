from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
from scripts import cross_model_eval as MODULE


class CrossModelEvalTests(unittest.TestCase):
    def test_json_extraction_from_fence(self) -> None:
        self.assertEqual({"ok": True}, MODULE.extract_json("```json\n{\"ok\": true}\n```"))

    def test_deterministic_scoring(self) -> None:
        response = {"verdict": "DISTORTED", "ids": ["B-3"], "note": "Use 18%."}
        checks = [
            {"path": "verdict", "op": "eq", "value": "DISTORTED"},
            {"path": "ids", "op": "set_eq", "value": ["B-3"]},
            {"path": "note", "op": "contains", "value": "18%"},
        ]
        result = MODULE.score_response(response, checks)
        self.assertTrue(result["passed"])
        self.assertEqual(1.0, result["score"])

    def test_skill_context_excludes_published_tests(self) -> None:
        context = MODULE.build_skill_context("rw-claim-audit")
        self.assertNotIn("## behavior-tests.json", context)
        self.assertNotIn("## cases.md", context)
        self.assertNotIn("## references/acceptance.md", context)

    def test_default_fixtures_are_held_out_and_valid(self) -> None:
        fixtures = MODULE.load_json(MODULE.DEFAULT_FIXTURES)
        models = MODULE.load_json(MODULE.DEFAULT_MODELS)
        self.assertEqual([], MODULE.validate_inputs(fixtures, models))


if __name__ == "__main__":
    unittest.main()
