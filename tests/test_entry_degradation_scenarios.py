import copy
import json
import unittest
from pathlib import Path

from scripts.check_degradation_registry import (
    REGISTRY_PATH,
    SCENARIOS_PATH,
    resolve_scenario,
    validate_scenarios,
)


ROOT = Path(__file__).resolve().parents[1]


class EntryDegradationScenarioTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.scenarios_document = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def assert_entry_scenarios(self, entry_skill, expected_statuses):
        scenarios = [
            scenario
            for scenario in self.scenarios_document["scenarios"]
            if scenario["entry_skill"] == entry_skill
        ]
        self.assertEqual(len(scenarios), 2)
        resolved = [resolve_scenario(self.registry, scenario) for scenario in scenarios]
        self.assertEqual({item["status"] for item in resolved}, expected_statuses)
        for result in resolved:
            self.assertTrue(result["user_signal"])
            self.assertTrue(result["fallback"])
            self.assertTrue(result["must_not"])

    def test_research_router_degradation_scenarios(self):
        self.assert_entry_scenarios(
            "rw-research-router",
            {"REVIEW", "PENDING_VERIFICATION"},
        )

    def test_paper_extractor_degradation_scenarios(self):
        self.assert_entry_scenarios(
            "rw-paper-extractor",
            {"BLOCK", "REVIEW"},
        )

    def test_research_referee_degradation_scenarios(self):
        self.assert_entry_scenarios(
            "rw-research-referee",
            {"REVIEW", "BLOCK"},
        )

    def test_phd_write_degradation_scenarios(self):
        self.assert_entry_scenarios(
            "rw-phd-write",
            {"BLOCK", "PENDING_VERIFICATION"},
        )

    def test_scenarios_match_registry_and_behavior_contracts(self):
        self.assertEqual(
            validate_scenarios(
                self.scenarios_document,
                self.registry,
                self.manifest,
            ),
            [],
        )

    def test_status_drift_is_rejected(self):
        scenarios = copy.deepcopy(self.scenarios_document)
        scenarios["scenarios"][0]["expected_status"] = "BLOCK"
        failures = validate_scenarios(scenarios, self.registry, self.manifest)
        self.assertTrue(any("expected_status does not match registry" in failure for failure in failures))

    def test_missing_entry_scenarios_is_rejected(self):
        scenarios = copy.deepcopy(self.scenarios_document)
        scenarios["scenarios"] = [
            scenario
            for scenario in scenarios["scenarios"]
            if scenario["entry_skill"] != "rw-phd-write"
        ]
        failures = validate_scenarios(scenarios, self.registry, self.manifest)
        self.assertTrue(any("requires at least two degradation scenarios" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
