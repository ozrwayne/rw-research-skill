#!/usr/bin/env python3
"""Check that the Codex agent card and the SKILL.md of every Skill agree on
which Skill they name, so the same task resolves to the same Skill whether a
user invokes it through Codex's `$name` syntax or through Claude Code / another
Agent Skills host by name."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER_NAME = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
DEFAULT_PROMPT_TARGET = re.compile(r"default_prompt:.*?\$([a-z0-9-]+)")


def _skill_frontmatter_name(skill: Path) -> str | None:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    frontmatter = text.split("---", 2)[1]
    match = FRONTMATTER_NAME.search(frontmatter)
    return match.group(1) if match else None


def _openai_yaml_target(skill: Path) -> str | None:
    path = skill / "agents" / "openai.yaml"
    if not path.is_file():
        return None
    match = DEFAULT_PROMPT_TARGET.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def validate_agent_parity(manifest: dict, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for name in manifest.get("skills", []):
        skill = root / "skills" / name
        if not (skill / "SKILL.md").is_file():
            failures.append(f"{name}: missing SKILL.md")
            continue
        frontmatter_name = _skill_frontmatter_name(skill)
        if frontmatter_name != name:
            failures.append(
                f"{name}: SKILL.md frontmatter name is {frontmatter_name!r}, expected {name!r}"
            )
        agent_target = _openai_yaml_target(skill)
        if agent_target is None:
            failures.append(f"{name}: agents/openai.yaml is missing or has no default_prompt $target")
        elif agent_target != name:
            failures.append(
                f"{name}: agents/openai.yaml default_prompt points at ${agent_target}, expected ${name}"
            )
    return failures


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    failures = validate_agent_parity(manifest)
    print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
