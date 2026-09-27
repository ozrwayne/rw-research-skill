#!/usr/bin/env python3
"""Validate one standalone RW research skill without workspace dependencies."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


CONTRAST_IDS = {
    'contrast-empty-contrast', 'contrast-redundant-summary',
    'contrast-affirmative-shell', 'contrast-synonym-only-repair',
    'contrast-concrete-comparison', 'contrast-defined-constructs',
    'contrast-functional-topic-sentence', 'contrast-scientific-hedging',
    'contrast-missing-context', 'contrast-missing-evidence',
    'contrast-limited-edit-scope', 'contrast-scope-drift',
}


def validate_contrast_contracts(tests: list[dict]) -> list[str]:
    """Validate fixture coverage/schema only, never the semantic verdict."""
    failures = []
    rows = [row for row in tests if row.get('gate') == 'abstract_contrast_v1']
    ids = [row.get('id') for row in rows]
    if set(ids) != CONTRAST_IDS or len(ids) != len(CONTRAST_IDS):
        failures.append('abstract-contrast paired contract IDs missing or duplicated')
    if Counter(row.get('group') for row in rows) != {'revise': 4, 'preserve': 4, 'boundary': 4}:
        failures.append('abstract-contrast coverage requires 4 cases in each group')
    if {row.get('language') for row in rows} != {'en', 'zh'}:
        failures.append('abstract-contrast coverage requires English and Chinese')
    verdicts = {'PASS', 'NEEDS_REVISION', 'NEEDS_CONTEXT'}
    actions = {'KEEP', 'DELETE', 'MERGE', 'REWRITE', 'ASK_AUTHOR'}
    dimensions = {'missed_issue', 'false_positive', 'claim_drift', 'unnecessary_expansion'}
    for row in rows:
        identifier = row.get('id')
        for key in ('generation_prompt', 'prompt'):
            if not isinstance(row.get(key), str) or not row[key].strip():
                failures.append(f'{identifier}: non-empty {key} required')
        if row.get('fixture_kind') != 'synthetic' or row.get('evaluation_set') != 'development':
            failures.append(f'{identifier}: synthetic development fixture required')
        for key in ('must_do', 'must_not'):
            if not isinstance(row.get(key), list) or not row[key] or any(not isinstance(x, str) or not x.strip() for x in row[key]):
                failures.append(f'{identifier}: non-empty {key} list required')
        expected = row.get('review_expectation')
        if not isinstance(expected, dict):
            failures.append(f'{identifier}: separate review expectation required')
            continue
        for key, allowed in (('verdicts', verdicts), ('actions', actions)):
            values = expected.get(key)
            if not isinstance(values, list) or not values or any(not isinstance(x, str) or x not in allowed for x in values):
                failures.append(f'{identifier}: invalid {key}')
        if row.get('group') == 'preserve' and expected != {'verdicts': ['PASS'], 'actions': ['KEEP']}:
            failures.append(f'{identifier}: preservation control must expect PASS / KEEP')
        values = row.get('evaluation_dimensions')
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values) or set(values) != dimensions:
            failures.append(f'{identifier}: evaluation dimensions incomplete')
    return failures



NECESSITY_IDS = {'necessity-zero-draft', 'necessity-missing-context', 'necessity-multi-turn', 'necessity-decision-provenance', 'necessity-continuation', 'necessity-global-repetition', 'necessity-context-needed', 'necessity-preference-invariance', 'necessity-move', 'necessity-reviewer-reword', 'necessity-sole-rationale', 'necessity-uncertainty', 'necessity-counterevidence', 'necessity-no-change', 'necessity-context-repeated', 'necessity-reporting'}


def validate_necessity_contracts(tests: list[dict]) -> list[str]:
    """Check fixture schema, not whether any model follows the instructions."""
    failures = []
    rows = [r for r in tests if isinstance(r, dict) and r.get('gate') == 'content_necessity_v1']
    ids = [r.get('id') for r in rows]
    if set(ids) != NECESSITY_IDS or len(ids) != len(NECESSITY_IDS):
        failures.append('content-necessity coverage missing or duplicated')
    for row in rows:
        name = row.get('id')
        if row.get('mode') not in {'generation', 'continuation', 'review', 'multi_turn', 'paired'}:
            failures.append(f'{name}: invalid mode')
        if not isinstance(row.get('prompt'), str) or not row['prompt'].strip():
            failures.append(f'{name}: missing neutral task input')
        for key in ('must_do', 'must_not'):
            values = row.get(key)
            if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
                failures.append(f'{name}: invalid {key}')
        if row.get('fixture_kind') != 'synthetic' or row.get('evaluation_set') != 'development':
            failures.append(f'{name}: synthetic regression provenance required')
        # Outcomes belong in separate raw-output records, not in fixture metadata.
        if row.get('execution_status') != 'not_run':
            failures.append(f'{name}: fixture must not assert unrecorded execution')
        for mode, key, count in [('multi_turn', 'follow_up_prompts', 3), ('paired', 'variant_prompts', 2)]:
            if row.get('mode') == mode:
                values = row.get(key)
                if not isinstance(values, list) or len(values) != count or any(not isinstance(x, str) or not x.strip() for x in values):
                    failures.append(f'{name}: invalid {key}')
    return failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    refs = root / "references"
    failures: list[str] = []
    required = [
        "SKILL.md", "agents/openai.yaml", "assets/worksheet.md",
        "references/standalone.md", "references/source-map.md", "references/standards.md",
        "references/writing-functions.md",
        "references/abstract-contrast-gate.md",
        "references/content-necessity-gate.md",
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
    failures.extend(validate_contrast_contracts(tests))
    failures.extend(validate_necessity_contracts(tests))
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
