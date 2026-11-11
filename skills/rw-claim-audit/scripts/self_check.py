#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        "SKILL.md", "agents/openai.yaml", "scripts/claim_audit.py", "references/method.md",
        "references/verdicts.md", "references/axioms.md", "references/atoms.jsonl",
        "references/cases.md", "references/source-map.md", "references/source-evidence.md",
        "references/acceptance.md", "references/behavior-tests.json", "assets/claim-audit-template.json",
    ]
    missing = [item for item in required if not (ROOT / item).exists()]
    atoms = [json.loads(line) for line in (ROOT / "references/atoms.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    tests = json.loads((ROOT / "references/behavior-tests.json").read_text(encoding="utf-8"))
    errors = []
    if missing:
        errors.append(f"missing files: {', '.join(missing)}")
    if len(atoms) < 10:
        errors.append("need at least 10 atoms")
    if len(tests) < 3:
        errors.append("need at least 3 behavior tests")
    if "TODO" in (ROOT / "SKILL.md").read_text(encoding="utf-8"):
        errors.append("SKILL.md contains TODO")
    if errors:
        print("\n".join(errors))
        return 1
    print("self-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
