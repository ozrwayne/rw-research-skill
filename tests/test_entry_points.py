import copy
import json
import unittest
from pathlib import Path

from scripts.check_entry_points import validate_entry_points


ROOT = Path(__file__).resolve().parents[1]


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_current_entry_map_is_complete(self):
        self.assertEqual(validate_entry_points(self.manifest), [])
        self.assertEqual(len(self.manifest["entry_skills"]), 4)
        self.assertEqual(len(self.manifest["skills"]) - len(self.manifest["entry_skills"]), 18)

    def test_duplicate_route_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entry_skills"][1]["routes"].append("rw-research-router")
        failures = validate_entry_points(manifest)
        self.assertTrue(any("multiple entry owners" in failure for failure in failures))

    def test_unowned_skill_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["entry_skills"][0]["routes"].remove("rw-research-learning")
        failures = validate_entry_points(manifest)
        self.assertTrue(any("without an entry owner" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
