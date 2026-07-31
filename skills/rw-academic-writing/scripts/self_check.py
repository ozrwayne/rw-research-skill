#!/usr/bin/env python3
"""Validate one standalone RW research skill without workspace dependencies."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    refs = root / "references"
    failures: list[str] = []
    required = [
        "SKILL.md", "agents/openai.yaml", "assets/worksheet.md",
        "references/standalone.md", "references/source-map.md", "references/standards.md",
        "references/writing-functions.md",
        "references/method.md", "references/domain-guide.md", "references/atoms.jsonl",
        "references/axioms.md", "references/cases.md", "references/behavior-tests.json",
        "references/acceptance.md", "references/source-evidence.md", "references/maturity.json",
    ]
    for relative in required:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"missing or empty: {relative}")
    atoms = [json.loads(line) for line in (refs / "atoms.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    tests = json.loads((refs / "behavior-tests.json").read_text(encoding="utf-8"))
    maturity = json.loads((refs / "maturity.json").read_text(encoding="utf-8"))
    axiom_count = (refs / "axioms.md").read_text(encoding="utf-8").count("## AXIOM-")
    if len(atoms) < 40:
        failures.append("fewer than 40 atoms")
    if axiom_count < 13:
        failures.append("fewer than 13 axioms")
    if len(tests) < 10 or sum(test["id"].startswith("counterexample") for test in tests) < 3:
        failures.append("behavior test coverage below target")
    if maturity.get("atom_count") != len(atoms):
        failures.append("maturity atom_count is stale")
    if maturity.get("axiom_count") != axiom_count:
        failures.append("maturity axiom_count is stale")
    if maturity.get("behavior_test_count") != len(tests):
        failures.append("maturity behavior_test_count is stale")
    test_ids = {test.get("id") for test in tests}
    required_test_ids = {
        "case-5-citation-chain",
        "case-6-chapter-label",
        "counterexample-10-force-explanation",
        "case-11-conceptual-closure",
    }
    if not required_test_ids.issubset(test_ids):
        failures.append("writing-function behavior tests missing")
    if not maturity.get("standalone") or maturity.get("local_hard_dependencies"):
        failures.append("standalone maturity contract failed")
    forbidden = (
        "/" + "Users" + "/",
        "private-" + "workspace/",
        "personal-" + "vault/",
        "research-" + "lab/",
        "~/" + ".claude",
    )
    for path in root.rglob("*"):
        if not path.is_file() or path == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden:
            if marker in text:
                failures.append(f"hard local dependency in {path.relative_to(root)}: {marker}")
    print(json.dumps({"skill": root.name, "standalone": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
