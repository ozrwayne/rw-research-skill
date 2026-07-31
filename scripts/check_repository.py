#!/usr/bin/env python3
"""Check release metadata, public counts, directories, and Skill links."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    skill_names = list(dict.fromkeys(manifest["skills"]))
    if len({version, manifest.get("version"), plugin.get("version")}) != 1:
        failures.append("VERSION, manifest.json, and plugin.json do not match")
    if len(skill_names) != len(manifest["skills"]):
        failures.append("manifest contains duplicate Skill names")

    actual_dirs = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir() and not path.name.startswith("__")}
    missing_dirs = sorted(set(skill_names) - actual_dirs)
    extra_dirs = sorted(actual_dirs - set(skill_names))
    if missing_dirs:
        failures.append(f"manifest Skill directories missing: {', '.join(missing_dirs)}")
    if extra_dirs:
        failures.append(f"Skill directories outside manifest: {', '.join(extra_dirs)}")

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
    entry_count = len(manifest.get("entry_skills", []))
    internal_count = metrics["skills"] - entry_count
    expected_intro = (
        f"仓库共 {metrics['skills']} 个科研 Skill，其中 {entry_count} 个是公开入口，"
        f"{internal_count} 个是内部模块。当前包含 {metrics['atoms']} 条知识原子、"
        f"{metrics['axioms']} 条公理、{metrics['cases']} 个案例和反例，以及 {metrics['contracts']} 条行为合同。"
    )
    if expected_intro not in readme:
        failures.append("README public metrics are stale")
    if "个行为测试" in readme or "条行为测试" in readme:
        failures.append("README still labels behavior contracts as executed tests")
    if f"当前版本：`v{version}`" not in readme:
        failures.append("README current version is stale")

    entry_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_entry_points.py")],
        capture_output=True,
        text=True,
    )
    try:
        entry_points = json.loads(entry_check.stdout)
    except json.JSONDecodeError:
        entry_points = {"failures": ["entry-point check did not return JSON"]}
    if entry_check.returncode:
        failures.extend(f"entry-points: {item}" for item in entry_points.get("failures", []))

    degradation_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_degradation_registry.py")],
        capture_output=True,
        text=True,
    )
    try:
        degradation = json.loads(degradation_check.stdout)
    except json.JSONDecodeError:
        degradation = {"failures": ["degradation check did not return JSON"]}
    if degradation_check.returncode:
        failures.extend(f"degradation: {item}" for item in degradation.get("failures", []))

    privacy_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_public_privacy.py")],
        capture_output=True,
        text=True,
    )
    try:
        privacy = json.loads(privacy_check.stdout)
    except json.JSONDecodeError:
        privacy = {"failures": ["privacy check did not return JSON"]}
    if privacy_check.returncode:
        failures.extend(f"privacy: {item}" for item in privacy.get("failures", []))

    cross_model_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cross_model_eval.py"), "check"],
        capture_output=True,
        text=True,
    )
    try:
        cross_model = json.loads(cross_model_check.stdout)
    except json.JSONDecodeError:
        cross_model = {"failures": ["cross-model check did not return JSON"]}
    if cross_model_check.returncode:
        failures.extend(f"cross-model: {item}" for item in cross_model.get("failures", []))

    skill_link_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_skill_links.py")],
        capture_output=True,
        text=True,
    )
    try:
        skill_links = json.loads(skill_link_check.stdout)
    except json.JSONDecodeError:
        skill_links = {"failures": ["Skill link check did not return JSON"]}
    if skill_link_check.returncode:
        failures.extend(f"skill-links: {item}" for item in skill_links.get("failures", []))

    result = {
        "version": version,
        "metrics": metrics,
        "entry_points": entry_points,
        "degradation": degradation,
        "privacy": privacy,
        "cross_model": cross_model,
        "skill_links": skill_links,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
