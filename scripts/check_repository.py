#!/usr/bin/env python3
"""Check release metadata, public counts, directories, and Skill links."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


try:
    from .package_safety import load_metadata, regular_files
except ImportError:
    from package_safety import load_metadata, regular_files


ROOT = Path(__file__).resolve().parents[1]


def run_json_check(argv: list[str], label: str, failures: list[str], allow_legacy_self_check: bool = False) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        failure = f"{label}: check failed to run: {exc}"
        failures.append(failure)
        return {"failures": [failure]}
    if allow_legacy_self_check and result.returncode == 0 and result.stdout.strip() == "self-check passed":
        return {"standalone": True, "failures": [], "format": "legacy-self-check"}
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict) or not isinstance(payload.get("failures"), list) or not all(isinstance(item, str) for item in payload["failures"]):
            raise ValueError("invalid check result schema")
    except (ValueError, TypeError):
        payload = {"failures": ["check did not return a JSON object with a failures list"]}
    failures.extend(f"{label}: {item}" for item in payload["failures"])
    if result.returncode:
        failures.append(f"{label}: exited with status {result.returncode}")
    return payload


def main() -> int:
    failures: list[str] = []
    try:
        manifest, version = load_metadata(ROOT)
        regular_files(ROOT / "skills")
        skill_names = manifest["skills"]
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"failures": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    actual_dirs = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir() and not path.name.startswith("__")}
    missing_dirs = sorted(set(skill_names) - actual_dirs)
    extra_dirs = sorted(actual_dirs - set(skill_names))
    if missing_dirs:
        failures.append(f"manifest Skill directories missing: {', '.join(missing_dirs)}")
    if extra_dirs:
        failures.append(f"Skill directories outside manifest: {', '.join(extra_dirs)}")

    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
        return 1

    contracts = run_json_check([sys.executable, str(ROOT / "scripts/check_skill_contracts.py")], "skill-contracts", failures)
    if failures:
        print(json.dumps({"contracts": contracts, "failures": failures}, ensure_ascii=False, indent=2))
        return 1

    metrics = {"skills": len(skill_names), "atoms": 0, "axioms": 0, "cases": 0, "contracts": 0}
    link_refs: dict[str, set[str]] = {}
    for name in skill_names:
        skill = ROOT / "skills" / name
        refs = skill / "references"
        if not (skill / "SKILL.md").is_file():
            continue
        metrics["atoms"] += sum(1 for line in (refs / "atoms.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
        metrics["axioms"] += (refs / "axioms.md").read_text(encoding="utf-8").count("## AXIOM-")
        metrics["cases"] += len(re.findall(r"^## ", (refs / "cases.md").read_text(encoding="utf-8"), re.MULTILINE))
        metrics["contracts"] += len(json.loads((refs / "behavior-tests.json").read_text(encoding="utf-8")))
        for linked in re.findall(r"`(rw-[a-z0-9-]+)`", (skill / "SKILL.md").read_text(encoding="utf-8")):
            if linked not in skill_names:
                link_refs.setdefault(linked, set()).add(name)
    for linked, owners in sorted(link_refs.items()):
        failures.append(f"Skill link outside manifest: {linked} from {', '.join(sorted(owners))}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected_intro = (
        f"对外提供 {len(manifest.get('entry_skills', []))} 个入口，内部保留 {metrics['skills']} 个科研 Skill。"
        f"当前包含 {metrics['atoms']} 条知识原子、"
        f"{metrics['axioms']} 条公理、{metrics['cases']} 个案例和反例，以及 {metrics['contracts']} 条行为合同。"
    )
    if expected_intro not in readme:
        failures.append("README public metrics are stale")
    if "个行为测试" in readme or "条行为测试" in readme:
        failures.append("README still labels behavior contracts as executed tests")
    if f"当前版本：`v{version}`" not in readme:
        failures.append("README current version is stale")

    entry_points = run_json_check([sys.executable, str(ROOT / "scripts/check_entry_points.py")], "entry-points", failures)
    degradation = run_json_check([sys.executable, str(ROOT / "scripts/check_degradation_registry.py")], "degradation", failures)
    privacy = run_json_check([sys.executable, str(ROOT / "scripts/check_public_privacy.py")], "privacy", failures)
    cross_model = run_json_check([sys.executable, str(ROOT / "scripts/cross_model_eval.py"), "check"], "cross-model", failures)

    result = {
        "version": version,
        "metrics": metrics,
        "contracts": contracts,
        "entry_points": entry_points,
        "degradation": degradation,
        "privacy": privacy,
        "cross_model": cross_model,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
