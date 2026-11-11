#!/usr/bin/env python3
"""Validate and merge controlled-vocabulary verification records."""

from __future__ import annotations

import argparse
import json
import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from datetime import datetime


def search_helpers():
    spec = importlib.util.spec_from_file_location("rw_search_contract", Path(__file__).with_name("search_strategy.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strategy_errors(strategy: Any) -> list[str]:
    return search_helpers().validate_strategy(strategy)


VOCABULARIES = {"mesh", "emtree", "cinahl", "apa"}
STATUSES = {
    "verified_by_public_api",
    "verified_in_subscribed_platform",
    "user_confirmed",
    "candidate",
    "unverified",
    "rejected",
}
VERIFIED_STATUSES = {
    "verified_by_public_api",
    "verified_in_subscribed_platform",
    "user_confirmed",
}


def load_json(path: str) -> Any:
    return search_helpers().load_json(path)


def validate_record(row: dict[str, Any], concept_ids: set[str]) -> list[str]:
    if not isinstance(row, dict):
        return ["record must be an object"]
    errors: list[str] = []
    if not isinstance(row.get("concept_id"), str):
        errors.append("concept_id must be a string")
    concept_id = str(row.get("concept_id", "")).strip()
    vocabulary = str(row.get("vocabulary", "")).strip().lower()
    status = str(row.get("status", "candidate")).strip()
    if concept_id not in concept_ids:
        errors.append(f"unknown concept_id: {concept_id or '[missing]'}")
    if vocabulary not in VOCABULARIES:
        errors.append(f"unsupported vocabulary: {vocabulary or '[missing]'}")
    if not isinstance(row.get("label"), str) or not row["label"].strip():
        errors.append("label is required")
    for flag in ("explode", "focus"):
        if flag in row and not isinstance(row[flag], bool):
            errors.append(f"{flag} must be boolean")
    if status not in STATUSES:
        errors.append(f"unsupported status: {status}")
    if vocabulary != "mesh" and status == "verified_by_public_api":
        errors.append(f"{vocabulary} cannot use verified_by_public_api")
    if status in VERIFIED_STATUSES:
        if not isinstance(row.get("source"), str) or not row["source"].strip():
            errors.append("verified record requires source")
        if not isinstance(row.get("verified_at"), str) or not row["verified_at"].strip():
            errors.append("verified record requires verified_at")
        try:
            datetime.fromisoformat(row.get("verified_at", "").replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            errors.append("verified_at must be an ISO date or datetime")
    return errors


def merge(strategy: dict[str, Any], records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = strategy_errors(strategy)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty array")
    result = deepcopy(strategy)
    concepts = {str(row.get("id")): row for row in result.get("concepts", [])}
    failures: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    replaced = 0
    for index, raw in enumerate(records, 1):
        if not isinstance(raw, dict):
            failures.append({"index": index, "record": raw, "errors": ["record must be an object"]})
            continue
        row = dict(raw)
        for field in ("concept_id", "vocabulary", "status"):
            if field in row and isinstance(row[field], str):
                row[field] = row[field].strip()
        row["vocabulary"] = str(row.get("vocabulary", "")).lower()
        row.setdefault("status", "candidate")
        row.setdefault("explode", True)
        row.setdefault("focus", False)
        errors = validate_record(row, set(concepts))
        if errors:
            failures.append({"index": index, "record": raw, "errors": errors})
            continue
        concept = concepts[row["concept_id"]]
        headings = concept.setdefault("headings", {}).setdefault(row["vocabulary"], [])
        candidate = {key: value for key, value in row.items() if key not in {"concept_id", "vocabulary"}}
        key = (str(candidate.get("identifier") or ""), str(candidate["label"]).casefold())
        match_index = next(
            (
                position
                for position, existing in enumerate(headings)
                if (
                    key[0] and isinstance(existing, dict) and existing.get("identifier") == key[0]
                ) or (
                    (not key[0] or not isinstance(existing, dict) or not existing.get("identifier"))
                    and str(existing.get("label") if isinstance(existing, dict) else existing).casefold() == key[1]
                )
            ),
            None,
        )
        if match_index is None:
            headings.append(candidate)
        else:
            headings[match_index] = candidate
            replaced += 1
        accepted.append(row)
    report = {
        "accepted": 0 if failures else len(accepted),
        "validated": len(accepted),
        "rejected": len(failures),
        "replaced": 0 if failures else replaced,
        "atomic": True,
        "atomic_scope": "record_merge",
        "failures": failures,
    }
    return deepcopy(strategy) if failures else result, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--records", required=True)
    parser.add_argument("--output")
    parser.add_argument("--report")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        helpers = search_helpers()
        helpers.ensure_distinct_paths([Path(args.strategy), Path(args.records)], [Path(value) for value in (args.output, args.report) if value])
        strategy = load_json(args.strategy)
        payload = load_json(args.records)
        records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("records must be a list")
        merged, report = merge(strategy, records)
        if args.report:
            helpers.dump_json(report, args.report)
        if args.dry_run:
            sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        elif args.output and not report["rejected"]:
            helpers.dump_json(merged, args.output)
        else:
            sys.stdout.write(json.dumps({"strategy": merged, "report": report}, ensure_ascii=False, indent=2) + "\n")
        return 1 if report["rejected"] else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
