#!/usr/bin/env python3
"""Validate the machine-readable degradation registry."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "degradation-registry.json"
SCENARIOS_PATH = ROOT / "docs" / "degradation-scenarios.json"
ID_PATTERN = re.compile(r"DEG-\d{3}$")
SCENARIO_ID_PATTERN = re.compile(r"SCN-DEG-\d{3}-[A-Z]$")
SEVERITIES = {"advisory", "review", "block"}
REQUIRED_TEXT = {"capability", "trigger", "status", "severity", "fallback", "must_not", "user_signal"}


def validate_registry(registry: dict, manifest: dict, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    if registry.get("schema_version") != "rw-degradation-registry/v1":
        failures.append("unsupported degradation registry schema_version")
    statuses = registry.get("statuses")
    if not isinstance(statuses, list) or not statuses or not all(isinstance(item, str) and item for item in statuses):
        failures.append("registry statuses must be a non-empty string list")
        statuses = []
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        return failures + ["registry entries must be a non-empty list"]

    skill_names = set(manifest.get("skills", []))
    entry_names = {
        entry.get("name")
        for entry in manifest.get("entry_skills", [])
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    ids: list[str] = []
    covered_entry_names: set[str] = set()
    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            failures.append(f"{prefix} must be an object")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not ID_PATTERN.fullmatch(entry_id):
            failures.append(f"{prefix}.id must match DEG-000")
            entry_id = prefix
        else:
            ids.append(entry_id)
        for field in REQUIRED_TEXT:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append(f"{entry_id}: {field} must be a non-empty string")
        if entry.get("status") not in statuses:
            failures.append(f"{entry_id}: status is outside registry statuses")
        if entry.get("severity") not in SEVERITIES:
            failures.append(f"{entry_id}: severity must be advisory, review, or block")

        owners = entry.get("owners")
        if not isinstance(owners, list) or not owners or not all(isinstance(owner, str) and owner for owner in owners):
            failures.append(f"{entry_id}: owners must be a non-empty string list")
        else:
            unknown_owners = sorted(set(owners) - skill_names)
            if unknown_owners:
                failures.append(f"{entry_id}: owners outside manifest: {', '.join(unknown_owners)}")
            covered_entry_names.update(set(owners) & entry_names)

        test_refs = entry.get("test_refs")
        if not isinstance(test_refs, list) or not test_refs or not all(isinstance(item, str) and item for item in test_refs):
            failures.append(f"{entry_id}: test_refs must be a non-empty string list")
        else:
            for test_ref in test_refs:
                path = Path(test_ref)
                if path.is_absolute() or ".." in path.parts:
                    failures.append(f"{entry_id}: unsafe test_ref: {test_ref}")
                elif not (root / path).is_file():
                    failures.append(f"{entry_id}: test_ref does not exist: {test_ref}")

    duplicate_ids = sorted(entry_id for entry_id, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        failures.append(f"duplicate degradation ids: {', '.join(duplicate_ids)}")
    uncovered_entries = sorted(entry_names - covered_entry_names)
    if uncovered_entries:
        failures.append(f"public entries without degradation coverage: {', '.join(uncovered_entries)}")
    return failures


def resolve_scenario(registry: dict, scenario: dict) -> dict:
    entries = {
        entry["id"]: entry
        for entry in registry.get("entries", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    registry_id = scenario.get("registry_id")
    if registry_id not in entries:
        raise KeyError(f"unknown registry id: {registry_id}")
    entry = entries[registry_id]
    return {
        "scenario_id": scenario.get("id"),
        "entry_skill": scenario.get("entry_skill"),
        "registry_id": registry_id,
        "status": entry["status"],
        "user_signal": entry["user_signal"],
        "fallback": entry["fallback"],
        "must_not": entry["must_not"],
    }


def validate_scenarios(
    scenarios_document: dict,
    registry: dict,
    manifest: dict,
    root: Path = ROOT,
) -> list[str]:
    failures: list[str] = []
    if scenarios_document.get("schema_version") != "rw-degradation-scenarios/v1":
        failures.append("unsupported degradation scenarios schema_version")
    scenarios = scenarios_document.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return failures + ["degradation scenarios must be a non-empty list"]

    entry_routes = {
        entry["name"]: set(entry["routes"])
        for entry in manifest.get("entry_skills", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("routes"), list)
    }
    registry_entries = {
        entry["id"]: entry
        for entry in registry.get("entries", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    scenario_ids: list[str] = []
    entry_counts: Counter[str] = Counter()
    for index, scenario in enumerate(scenarios):
        prefix = f"scenarios[{index}]"
        if not isinstance(scenario, dict):
            failures.append(f"{prefix} must be an object")
            continue
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
            failures.append(f"{prefix}.id is invalid")
            scenario_id = prefix
        else:
            scenario_ids.append(scenario_id)

        entry_skill = scenario.get("entry_skill")
        if entry_skill not in entry_routes:
            failures.append(f"{scenario_id}: unknown public entry: {entry_skill}")
            continue
        entry_counts[entry_skill] += 1

        registry_id = scenario.get("registry_id")
        registry_entry = registry_entries.get(registry_id)
        if registry_entry is None:
            failures.append(f"{scenario_id}: unknown registry id: {registry_id}")
            continue
        if not (set(registry_entry.get("owners", [])) & entry_routes[entry_skill]):
            failures.append(f"{scenario_id}: registry entry is outside the public entry route")
        if scenario.get("expected_status") != registry_entry.get("status"):
            failures.append(f"{scenario_id}: expected_status does not match registry")

        prompt = scenario.get("prompt")
        contract_id = scenario.get("behavior_contract_id")
        if not isinstance(prompt, str) or not prompt.strip():
            failures.append(f"{scenario_id}: prompt must be a non-empty string")
        if not isinstance(contract_id, str) or not contract_id:
            failures.append(f"{scenario_id}: behavior_contract_id is missing")
            continue
        contract_path = root / "skills" / entry_skill / "references" / "behavior-tests.json"
        if not contract_path.is_file():
            failures.append(f"{scenario_id}: behavior contract file is missing")
            continue
        contracts = json.loads(contract_path.read_text(encoding="utf-8"))
        matching_contracts = [contract for contract in contracts if contract.get("id") == contract_id]
        if len(matching_contracts) != 1:
            failures.append(f"{scenario_id}: behavior contract must exist exactly once")
            continue
        contract = matching_contracts[0]
        if contract.get("prompt") != prompt:
            failures.append(f"{scenario_id}: prompt differs from behavior contract")
        if contract.get("degradation_registry_id") != registry_id:
            failures.append(f"{scenario_id}: behavior contract registry id differs")
        if contract.get("expected_status") != registry_entry.get("status"):
            failures.append(f"{scenario_id}: behavior contract status differs")
        if registry_entry.get("user_signal") not in contract.get("must_do", []):
            failures.append(f"{scenario_id}: user signal is missing from must_do")
        if registry_entry.get("fallback") not in contract.get("must_do", []):
            failures.append(f"{scenario_id}: fallback is missing from must_do")
        if registry_entry.get("must_not") not in contract.get("must_not", []):
            failures.append(f"{scenario_id}: registry prohibition is missing from must_not")

    duplicate_ids = sorted(item for item, count in Counter(scenario_ids).items() if count > 1)
    if duplicate_ids:
        failures.append(f"duplicate degradation scenario ids: {', '.join(duplicate_ids)}")
    for entry_skill in sorted(entry_routes):
        if entry_counts[entry_skill] < 2:
            failures.append(f"{entry_skill}: requires at least two degradation scenarios")
    return failures


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    failures = validate_registry(registry, manifest)
    failures.extend(validate_scenarios(scenarios, registry, manifest))
    result = {
        "entries": len(registry.get("entries", [])),
        "scenarios": len(scenarios.get("scenarios", [])),
        "statuses": registry.get("statuses", []),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
