#!/usr/bin/env python3
"""Check structured Skill handoffs against the release manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_TOKEN = re.compile(r"`(rw-[a-z0-9-]+)`")
CASE_NEXT = re.compile(r"下一步：\s*(rw-[a-z0-9-]+)")
STRUCTURED_FILES = {
    "SKILL.md",
    "domain-guide.md",
    "cases.md",
    "source-map.md",
    "behavior-tests.json",
}


def _expected_next(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"expected_next", "next_skill"}:
                if isinstance(child, str) and child:
                    found.add(child)
                elif isinstance(child, list):
                    found.update(item for item in child if isinstance(item, str) and item)
            else:
                found.update(_expected_next(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_expected_next(child))
    return found


def find_referenced_skills(root: Path = ROOT) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    for path in sorted((root / "skills").glob("*/**/*")):
        if not path.is_file() or path.name not in STRUCTURED_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        candidates = set(SKILL_TOKEN.findall(text))
        if path.name == "cases.md":
            candidates.update(CASE_NEXT.findall(text))
        if path.name == "behavior-tests.json":
            try:
                candidates.update(_expected_next(json.loads(text)))
            except json.JSONDecodeError:
                continue
        for candidate in candidates:
            references.setdefault(candidate, set()).add(str(path.relative_to(root)))
    return references


def validate_skill_links(manifest: dict, root: Path = ROOT) -> list[str]:
    known = set(manifest.get("skills", []))
    failures: list[str] = []
    for name, paths in sorted(find_referenced_skills(root).items()):
        if name not in known:
            failures.append(f"Skill handoff outside manifest: {name} from {', '.join(sorted(paths))}")
    return failures


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    failures = validate_skill_links(manifest)
    print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
