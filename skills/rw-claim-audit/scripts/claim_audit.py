#!/usr/bin/env python3
"""Create, validate, summarize, and gate claim-to-source audits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rw-claim-audit/v1"
CLAIM_TYPES = {"quantitative", "categorical", "trend", "comparative", "causal", "method", "interpretive", "other"}
VERDICTS = {"VERIFIED", "PARTIAL", "DISTORTED", "UNSUPPORTED", "UNVERIFIABLE_ACCESS", "NOT_CHECKED", "NOT_APPLICABLE"}
BLOCKING = {"DISTORTED", "UNSUPPORTED"}
REVIEW = {"PARTIAL", "UNVERIFIABLE_ACCESS", "NOT_CHECKED"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(result, allow_nan=False)
    return result


def input_errors(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["root must be an object"]
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        return [f"invalid JSON data: {exc}"]
    return []


def load(path: Path) -> dict[str, Any]:
    data = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("audit root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def validate(data: dict[str, Any]) -> list[str]:
    errors = input_errors(data)
    if errors:
        return errors
    try:
        return _validate(data)
    except (TypeError, AttributeError, KeyError, RecursionError) as exc:
        return [f"invalid field type or structure: {exc}"]


def _validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["schema_version", "document_id", "document_path", "document_hash", "audited_at", "claims"]:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    for field in ("document_id", "document_path", "document_hash", "audited_at"):
        if not isinstance(data[field], str) or not data[field].strip():
            errors.append(f"{field} must be a non-empty string")
    if not isinstance(data["document_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", data["document_hash"]):
        errors.append("document_hash must be a SHA-256 hex digest")
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(data["claims"], list):
        errors.append("claims must be an array")
        return errors
    seen: set[str] = set()
    for index, claim in enumerate(data["claims"]):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["id", "text", "location", "claim_type", "source_refs", "verdict", "notes"]:
            if field not in claim:
                errors.append(f"{prefix} missing field: {field}")
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif claim_id in seen:
            errors.append(f"duplicate claim id: {claim_id}")
        else:
            seen.add(claim_id)
        for field in ("text", "location"):
            if not isinstance(claim.get(field), str) or not claim[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if not isinstance(claim.get("notes"), str):
            errors.append(f"{prefix}.notes must be a string")
        if claim.get("verdict") == "NOT_APPLICABLE" and not str(claim.get("notes", "")).strip():
            errors.append(f"{prefix}.NOT_APPLICABLE requires an explanation in notes")
        if claim.get("claim_type") not in CLAIM_TYPES:
            errors.append(f"{prefix}.claim_type is invalid")
        verdict = claim.get("verdict")
        if verdict not in VERDICTS:
            errors.append(f"{prefix}.verdict is invalid")
        refs = claim.get("source_refs")
        if not isinstance(refs, list):
            errors.append(f"{prefix}.source_refs must be an array")
            continue
        ref_ids = [ref.get("id") for ref in refs if isinstance(ref, dict) and isinstance(ref.get("id"), str)]
        if len(ref_ids) != len(set(ref_ids)):
            errors.append(f"{prefix}.source_refs contains duplicate ids")
        for ref_index, ref in enumerate(refs):
            ref_prefix = f"{prefix}.source_refs[{ref_index}]"
            if not isinstance(ref, dict):
                errors.append(f"{ref_prefix} must be an object")
                continue
            for field in ["id", "source_pointer", "locator", "support_note"]:
                if not isinstance(ref.get(field), str) or not ref[field].strip():
                    errors.append(f"{ref_prefix}.{field} must be a non-empty string")
            if "source_path" in ref or "source_sha256" in ref:
                if not isinstance(ref.get("source_path"), str) or not ref["source_path"].strip():
                    errors.append(f"{ref_prefix}.source_path must be a non-empty string")
                if not isinstance(ref.get("source_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref["source_sha256"]):
                    errors.append(f"{ref_prefix}.source_sha256 must be a SHA-256 hex digest")
        if verdict in {"VERIFIED", "PARTIAL", "DISTORTED"} and not refs:
            errors.append(f"{prefix} verdict {verdict} requires at least one source_ref")
        if verdict == "UNVERIFIABLE_ACCESS" and not refs:
            errors.append(f"{prefix} UNVERIFIABLE_ACCESS requires a source_ref with the attempted source pointer")
    return errors


def validate_audit(data: dict[str, Any], audit_path: Path) -> list[str]:
    errors = validate(data)
    if errors:
        return errors
    document = Path(data["document_path"])
    if not document.is_absolute():
        document = audit_path.parent / document
    if not document.is_file():
        errors.append(f"document file is missing: {document}")
        return errors
    if file_hash(document) != data["document_hash"]:
        errors.append("document_hash does not match the current document")
    for claim in data["claims"]:
        for ref in claim["source_refs"]:
            if "source_path" not in ref:
                continue
            source = Path(ref["source_path"])
            if not source.is_absolute():
                source = audit_path.parent / source
            if not source.is_file():
                errors.append(f"claim {claim['id']} source file is missing: {source}")
            elif file_hash(source) != ref["source_sha256"]:
                errors.append(f"claim {claim['id']} source_sha256 does not match current source: {ref['id']}")
    return errors


def gate_status(data: dict[str, Any]) -> str:
    # Structural/disposition gate; callers must also run validate_audit for freshness.
    if validate(data):
        return "BLOCK"
    if not data["claims"]:
        return "REVIEW"
    verdicts = {claim["verdict"] for claim in data["claims"]}
    if verdicts & BLOCKING:
        return "BLOCK"
    if verdicts & REVIEW:
        return "REVIEW"
    for claim in data["claims"]:
        if claim["verdict"] in {"VERIFIED", "PARTIAL", "DISTORTED"}:
            if any(not ref.get("source_path") or not ref.get("source_sha256") for ref in claim["source_refs"]):
                return "REVIEW"
    return "PASS"


def command_init(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists() and not args.force:
        print(f"refusing to overwrite existing file: {output}")
        return 2
    document = Path(args.document_path)
    if not document.is_file():
        print(f"document file is missing: {document}")
        return 2
    if output.resolve() == document.resolve() or (output.exists() and output.samefile(document)):
        print("output must differ from document")
        return 2
    data = {
        "schema_version": SCHEMA_VERSION,
        "document_id": args.document_id,
        "document_path": str(document.resolve()),
        "document_hash": file_hash(document),
        "audited_at": now(),
        "claims": [],
    }
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(output, data)
    print(f"created {output}")
    return 0


def command_add_claim(args: argparse.Namespace) -> int:
    path = Path(args.audit)
    data = load(path)
    if any(claim.get("id") == args.id for claim in data.get("claims", []) if isinstance(claim, dict)):
        print(f"duplicate claim id: {args.id}")
        return 2
    data.setdefault("claims", []).append({
        "id": args.id,
        "text": args.text,
        "location": args.location,
        "claim_type": args.claim_type,
        "source_refs": [],
        "verdict": "NOT_CHECKED",
        "notes": "",
    })
    data["audited_at"] = now()
    errors = validate_audit(data, path)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"added {args.id}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.audit)
    try:
        errors = validate_audit(load(path), path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid audit: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("claim audit valid")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    path = Path(args.audit)
    data = load(path)
    errors = validate_audit(data, path)
    if errors:
        print("\n".join(errors))
        return 2
    counts = {verdict: sum(1 for claim in data["claims"] if claim["verdict"] == verdict) for verdict in sorted(VERDICTS)}
    print(json.dumps({"document_id": data["document_id"], "claims": len(data["claims"]), "verdicts": counts, "gate": gate_status(data)}, indent=2))
    return 0


def command_gate(args: argparse.Namespace) -> int:
    path = Path(args.audit)
    data = load(path)
    errors = validate_audit(data, path)
    if errors:
        print("\n".join(errors))
        return 2
    status = gate_status(data)
    print(status)
    return {"PASS": 0, "REVIEW": 1, "BLOCK": 2}[status]


def command_set_verdict(args: argparse.Namespace) -> int:
    path = Path(args.audit)
    data = load(path)
    claim = next((item for item in data.get("claims", []) if isinstance(item, dict) and item.get("id") == args.claim_id), None)
    if claim is None:
        print(f"claim not found: {args.claim_id}")
        return 2
    source_values = [args.source_id, args.source_pointer, args.locator, args.support_note]
    if any(source_values) and not all(source_values):
        print("source-id, source-pointer, locator, and support-note must be provided together")
        return 2
    if getattr(args, "source_file", None) and not args.source_id:
        print("--source-file requires source reference fields")
        return 2
    if args.source_id:
        source_ref = {
            "id": args.source_id,
            "source_pointer": args.source_pointer,
            "locator": args.locator,
            "support_note": args.support_note,
        }
        explicit_source = getattr(args, "source_file", None)
        source = Path(explicit_source or args.source_pointer)
        if not source.is_absolute():
            source = path.parent / source
        if explicit_source and not source.is_file():
            print(f"source snapshot is missing: {source}")
            return 2
        if source.is_file():
            source_ref.update(source_path=str(source.resolve()), source_sha256=file_hash(source))
        refs = claim.setdefault("source_refs", [])
        existing = next((index for index, item in enumerate(refs) if isinstance(item, dict) and item.get("id") == args.source_id), None)
        if existing is None:
            refs.append(source_ref)
        else:
            refs[existing] = source_ref
    claim["verdict"] = args.verdict
    if args.notes is not None:
        claim["notes"] = args.notes
    data["audited_at"] = now()
    errors = validate_audit(data, path)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"updated {args.claim_id}: {args.verdict}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("output")
    init_parser.add_argument("--document-id", required=True)
    init_parser.add_argument("--document-path", required=True)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    add_parser = subparsers.add_parser("add-claim")
    add_parser.add_argument("audit")
    add_parser.add_argument("--id", required=True)
    add_parser.add_argument("--text", required=True)
    add_parser.add_argument("--location", required=True)
    add_parser.add_argument("--claim-type", choices=sorted(CLAIM_TYPES), required=True)
    add_parser.set_defaults(func=command_add_claim)

    verdict_parser = subparsers.add_parser("set-verdict")
    verdict_parser.add_argument("audit")
    verdict_parser.add_argument("--claim-id", required=True)
    verdict_parser.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    verdict_parser.add_argument("--source-id")
    verdict_parser.add_argument("--source-pointer")
    verdict_parser.add_argument("--source-file", help="original-source snapshot; relative to audit JSON directory")
    verdict_parser.add_argument("--locator")
    verdict_parser.add_argument("--support-note")
    verdict_parser.add_argument("--notes")
    verdict_parser.set_defaults(func=command_set_verdict)

    for name, function in [("validate", command_validate), ("summary", command_summary), ("gate", command_gate)]:
        sub = subparsers.add_parser(name)
        sub.add_argument("audit")
        sub.set_defaults(func=function)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        print(f"BLOCK: invalid input: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
