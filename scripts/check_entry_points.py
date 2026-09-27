#!/usr/bin/env python3
"""Validate the public entry-point map in manifest.json."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


try:
    from .package_safety import skill_names, no_symlink
except ImportError:
    from package_safety import skill_names, no_symlink


ROOT = Path(__file__).resolve().parents[1]


def validate_entry_points(manifest: dict, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    try:
        skills = skill_names(manifest)
    except (ValueError, TypeError, AttributeError) as exc:
        return [str(exc)]
    entries = manifest.get("entry_skills")
    if not isinstance(skills, list) or not all(isinstance(item, str) and item for item in skills):
        return ["manifest skills must be a non-empty string list"]
    if not isinstance(entries, list):
        return ["manifest entry_skills must be a list"]
    if not 3 <= len(entries) <= 4:
        failures.append("manifest must expose 3 to 4 entry skills")

    entry_names: list[str] = []
    routed: list[str] = []
    for index, entry in enumerate(entries):
        prefix = f"entry_skills[{index}]"
        if not isinstance(entry, dict):
            failures.append(f"{prefix} must be an object")
            continue
        name = entry.get("name")
        label = entry.get("label")
        intent = entry.get("intent")
        routes = entry.get("routes")
        if not isinstance(name, str) or not name:
            failures.append(f"{prefix}.name must be a non-empty string")
            continue
        entry_names.append(name)
        if name not in skills:
            failures.append(f"{name}: entry skill is outside manifest skills")
        if name in skills and not (root / "skills" / name / "SKILL.md").is_file():
            failures.append(f"{name}: entry SKILL.md is missing")
        if not isinstance(label, str) or not label.strip():
            failures.append(f"{name}: label is missing")
        if not isinstance(intent, str) or not intent.strip():
            failures.append(f"{name}: intent is missing")
        if not isinstance(routes, list) or not routes:
            failures.append(f"{name}: routes must be a non-empty list")
            continue
        if not all(isinstance(route, str) and route for route in routes):
            failures.append(f"{name}: routes must contain non-empty strings")
            continue
        if name not in routes:
            failures.append(f"{name}: routes must include the entry skill itself")
        routed.extend(routes)

    duplicate_entries = sorted(name for name, count in Counter(entry_names).items() if count > 1)
    if duplicate_entries:
        failures.append(f"duplicate entry skills: {', '.join(duplicate_entries)}")

    skill_set = set(skills)
    entry_name_set = set(entry_names)
    for name in skills:
        path = root / "skills" / name / "SKILL.md"
        try:
            no_symlink(path)
            skill_text = path.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            failures.append(f"{name}: {exc}")
            continue
        frontmatter = skill_text.split("---", 2)[1] if skill_text.startswith("---") else ""
        is_internal = "metadata:\n  internal: true" in frontmatter
        if name in entry_name_set and is_internal:
            failures.append(f"{name}: public entry must not be marked internal")
        if name not in entry_name_set and not is_internal:
            failures.append(f"{name}: internal route must set metadata.internal to true")

    route_counts = Counter(routed)
    unknown = sorted(set(routed) - skill_set)
    missing = sorted(skill_set - set(routed))
    duplicates = sorted(name for name, count in route_counts.items() if count > 1)
    if unknown:
        failures.append(f"entry routes outside manifest skills: {', '.join(unknown)}")
    if missing:
        failures.append(f"skills without an entry owner: {', '.join(missing)}")
    if duplicates:
        failures.append(f"skills with multiple entry owners: {', '.join(duplicates)}")
    return failures


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    failures = validate_entry_points(manifest)
    result = {
        "entry_skills": [entry.get("name") for entry in manifest.get("entry_skills", []) if isinstance(entry, dict)],
        "public_entries": len(manifest.get("entry_skills", [])),
        "internal_skills": len(manifest.get("skills", [])) - len(manifest.get("entry_skills", [])),
        "total_skills": len(manifest.get("skills", [])),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
