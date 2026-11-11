#!/usr/bin/env python3
"""Validate the standalone RW Research Learning skill."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


def load_scanner(path: Path):
    spec = importlib.util.spec_from_file_location("research_learning_scan", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    refs = root / "references"
    failures: list[str] = []
    required = [
        "SKILL.md",
        "agents/openai.yaml",
        "assets/profile-template.json",
        "references/standalone.md",
        "references/method.md",
        "references/scan-policy.md",
        "references/profile-schema.md",
        "references/source-map.md",
        "references/source-evidence.md",
        "references/atoms.jsonl",
        "references/axioms.md",
        "references/cases.md",
        "references/behavior-tests.json",
        "references/acceptance.md",
        "references/maturity.json",
        "scripts/research_learning_scan.py",
    ]
    for relative in required:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"missing or empty: {relative}")

    if failures:
        print(json.dumps({"skill": root.name, "standalone": False, "failures": failures}, ensure_ascii=False, indent=2))
        return 1

    try:
        atoms = [
            json.loads(line)
            for line in (refs / "atoms.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(atoms) < 29:
            failures.append("fewer than 29 atoms")
        if len({atom.get("id") for atom in atoms}) != len(atoms):
            failures.append("duplicate atom ids")
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid atoms: {exc}")

    try:
        tests = json.loads((refs / "behavior-tests.json").read_text(encoding="utf-8"))
        if len(tests) < 13 or sum(test["id"].startswith("counterexample") for test in tests) < 3:
            failures.append("behavior test coverage below target")
        if any(test.get("fixture_kind") != "synthetic" for test in tests):
            failures.append("behavior tests must use synthetic fixtures")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        failures.append(f"invalid behavior tests: {exc}")

    try:
        maturity = json.loads((refs / "maturity.json").read_text(encoding="utf-8"))
        if not maturity.get("standalone") or maturity.get("local_hard_dependencies"):
            failures.append("standalone maturity contract failed")
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid maturity contract: {exc}")

    if (refs / "axioms.md").read_text(encoding="utf-8").count("## AXIOM-") < 12:
        failures.append("fewer than 12 axioms")

    try:
        scanner = load_scanner(root / "scripts" / "research_learning_scan.py")
        template = json.loads((root / "assets" / "profile-template.json").read_text(encoding="utf-8"))
        profile_failures = scanner.validate_profile(template)
        if profile_failures:
            failures.extend(f"profile template: {item}" for item in profile_failures)
        if template.get("visibility") != "private_local":
            failures.append("profile template must be private_local")
        external_only = json.loads(json.dumps(template))
        external_only["capabilities"] = [{
            "name": "Synthetic method",
            "status": "applied",
            "judgment": "Synthetic judgment",
            "confidence": "medium",
            "evidence": [{
                "path": "synthetic/reference.pdf",
                "locator": "page 1",
                "reason": "Reference description only.",
                "source_kind": "external_reference",
                "authorship_confidence": "low",
                "currentness": "reference",
            }],
        }]
        if "capabilities[0].applied requires user-role evidence" not in scanner.validate_profile(external_only):
            failures.append("external-only applied evidence was accepted")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            corpus = temp_root / "synthetic-research"
            state = temp_root / "state"
            corpus.mkdir()
            (corpus / "notes.md").write_text("# Method\n\nSynthetic analysis note.\n", encoding="utf-8")
            (corpus / "broken.docx").write_bytes(b"not-a-zip")
            connection = scanner.connect_database(state)
            try:
                counts, _ = scanner.scan_root(
                    connection, corpus, "self-check", scanner.DEFAULT_MAX_FILE_BYTES,
                    scanner.DEFAULT_MAX_TEXT_CHARS,
                )
            finally:
                connection.close()
            if counts.get("indexed") != 1 or counts.get("unreadable") != 1:
                failures.append("per-file failure containment failed")
            candidates, _ = scanner.discover_candidate_roots([temp_root], 4, 10)
            if not candidates or any("text" in item for item in candidates):
                failures.append("metadata-only landscape discovery failed")
    except Exception as exc:  # noqa: BLE001 - self-check reports import and schema errors
        failures.append(f"scanner self-check failed: {type(exc).__name__}: {exc}")

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
