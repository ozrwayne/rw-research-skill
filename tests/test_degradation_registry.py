import copy
import json
import unittest
from pathlib import Path

from scripts.check_degradation_registry import REGISTRY_PATH, SCENARIOS_PATH, validate_registry, validate_scenarios


ROOT = Path(__file__).resolve().parents[1]


class DegradationRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_current_registry_is_valid(self):
        self.assertEqual(validate_registry(self.registry, self.manifest), [])
        self.assertEqual(validate_scenarios(self.scenarios, self.registry, self.manifest), [])

    def test_unknown_owner_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["owners"].append("rw-not-a-skill")
        failures = validate_registry(registry, self.manifest)
        self.assertTrue(any("owners outside manifest" in failure for failure in failures))

    def test_missing_test_reference_is_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["test_refs"] = ["tests/does-not-exist.py"]
        failures = validate_registry(registry, self.manifest)
        self.assertTrue(any("test_ref does not exist" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
