#!/usr/bin/env python3
"""Create and validate RW Research Passport JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rw-research-passport/v1"
STAGES = {"question", "discovery", "extraction", "synthesis", "design", "analysis", "writing", "review", "submission", "closed"}
MATERIAL_STATUSES = {"raw", "extracted", "verified", "rejected", "superseded"}
DECISION_STATUSES = {"proposed", "confirmed", "rejected", "superseded"}
UNKNOWN_STATUSES = {"open", "resolved", "blocked"}
HANDOFF_STATUSES = {"prepared", "accepted", "rejected"}
CREDENTIAL_AUTHORITIES = {"advisory", "agent_consensus", "delegated", "human_confirmed"}
CREDENTIAL_BASES = {"evidence", "reasoning", "delegated_choice"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("passport root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def duplicate_ids(items: list[Any]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            item_id = item["id"]
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)
    return duplicates


def credential_hash(credential: dict[str, Any]) -> str:
    payload = {key: value for key, value in credential.items() if key != "content_hash"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["schema_version", "project_id", "title", "stage", "updated_at", "materials", "decisions", "unknowns", "handoffs", "audit_log"]
    for field in required:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(data["project_id"], str) or not data["project_id"].strip():
        errors.append("project_id must be a non-empty string")
    if data["stage"] not in STAGES:
        errors.append(f"invalid stage: {data['stage']}")
    for field in ["materials", "decisions", "unknowns", "handoffs", "audit_log"]:
        if not isinstance(data[field], list):
            errors.append(f"{field} must be an array")
    if "credentials" in data and not isinstance(data["credentials"], list):
        errors.append("credentials must be an array")
    if errors:
        return errors

    material_ids: set[str] = set()
    supersedes_links: list[tuple[str, str, str]] = []
    for index, item in enumerate(data["materials"]):
        prefix = f"materials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["id", "type", "title", "source_pointer", "status", "added_at"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if item.get("status") not in MATERIAL_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if isinstance(item.get("id"), str):
            material_ids.add(item["id"])
        content_sha256 = item.get("content_sha256")
        if content_sha256 is not None and (
            not isinstance(content_sha256, str)
            or len(content_sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in content_sha256)
        ):
            errors.append(f"{prefix}.content_sha256 must be a 64-character hexadecimal string")
        supersedes_id = item.get("supersedes_id")
        if supersedes_id is not None:
            if not isinstance(supersedes_id, str) or not supersedes_id.strip():
                errors.append(f"{prefix}.supersedes_id must be a non-empty string")
            elif isinstance(item.get("id"), str):
                supersedes_links.append((prefix, item["id"], supersedes_id))
    for duplicate in sorted(duplicate_ids(data["materials"])):
        errors.append(f"duplicate material id: {duplicate}")
    for prefix, item_id, supersedes_id in supersedes_links:
        if supersedes_id == item_id:
            errors.append(f"{prefix}.supersedes_id cannot reference itself")
        elif supersedes_id not in material_ids:
            errors.append(f"{prefix}.supersedes_id references missing material: {supersedes_id}")

    decision_ids: set[str] = set()
    unknown_ids: set[str] = set()
    for collection, required_fields, statuses in [
        ("decisions", ["id", "statement", "status", "evidence_ids", "recorded_at"], DECISION_STATUSES),
        ("unknowns", ["id", "question", "status"], UNKNOWN_STATUSES),
        ("handoffs", ["id", "from_stage", "to_stage", "material_ids", "status", "recorded_at"], HANDOFF_STATUSES),
    ]:
        for index, item in enumerate(data[collection]):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in required_fields:
                if field not in item:
                    errors.append(f"{prefix} missing field: {field}")
            if item.get("status") not in statuses:
                errors.append(f"{prefix}.status is invalid")
            if collection == "decisions" and isinstance(item.get("id"), str):
                decision_ids.add(item["id"])
            if collection == "unknowns" and isinstance(item.get("id"), str):
                unknown_ids.add(item["id"])
            link_field = "evidence_ids" if collection == "decisions" else "material_ids" if collection == "handoffs" else None
            if link_field:
                links = item.get(link_field)
                if not isinstance(links, list) or not all(isinstance(value, str) for value in links):
                    errors.append(f"{prefix}.{link_field} must be an array of strings")
                else:
                    for value in links:
                        if value not in material_ids:
                            errors.append(f"{prefix}.{link_field} references missing material: {value}")
        for duplicate in sorted(duplicate_ids(data[collection])):
            errors.append(f"duplicate {collection[:-1]} id: {duplicate}")

    credentials = data.get("credentials", [])
    credential_ids = {
        item["id"] for item in credentials
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for index, item in enumerate(credentials):
        prefix = f"credentials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "id", "decision_id", "session_id", "record_pointer", "settled_by",
            "authority", "basis", "scope", "decision_snapshot", "unknown_ids", "issued_at", "content_hash",
        ]:
            if field not in item:
                errors.append(f"{prefix} missing field: {field}")
        for field in ["id", "decision_id", "session_id", "record_pointer", "scope", "issued_at", "content_hash"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if item.get("authority") not in CREDENTIAL_AUTHORITIES:
            errors.append(f"{prefix}.authority is invalid")
        if item.get("basis") not in CREDENTIAL_BASES:
            errors.append(f"{prefix}.basis is invalid")
        settled_by = item.get("settled_by")
        if not isinstance(settled_by, list) or not settled_by or not all(
            isinstance(value, str) and (value.startswith("human:") or value.startswith("agent:"))
            for value in settled_by
        ):
            errors.append(f"{prefix}.settled_by must contain human: or agent: identifiers")
        elif item.get("authority") == "human_confirmed" and not any(value.startswith("human:") for value in settled_by):
            errors.append(f"{prefix}.human_confirmed requires a human: identifier")
        elif item.get("authority") in {"agent_consensus", "delegated"} and not any(
            value.startswith("agent:") for value in settled_by
        ):
            errors.append(f"{prefix}.{item.get('authority')} requires an agent: identifier")
        snapshot = item.get("decision_snapshot")
        if not isinstance(snapshot, dict):
            errors.append(f"{prefix}.decision_snapshot must be an object")
        else:
            for field in ["statement", "status", "basis", "evidence_ids"]:
                if field not in snapshot:
                    errors.append(f"{prefix}.decision_snapshot missing field: {field}")
            if not isinstance(snapshot.get("statement"), str) or not snapshot.get("statement", "").strip():
                errors.append(f"{prefix}.decision_snapshot.statement must be a non-empty string")
            if snapshot.get("status") not in DECISION_STATUSES:
                errors.append(f"{prefix}.decision_snapshot.status is invalid")
            if snapshot.get("basis") not in CREDENTIAL_BASES:
                errors.append(f"{prefix}.decision_snapshot.basis is invalid")
            if snapshot.get("basis") != item.get("basis"):
                errors.append(f"{prefix}.decision_snapshot.basis must match credential basis")
            if snapshot.get("status") == "confirmed" and item.get("authority") == "advisory":
                errors.append(f"{prefix}.advisory credential cannot confirm a decision")
            evidence_ids = snapshot.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
                errors.append(f"{prefix}.decision_snapshot.evidence_ids must be an array of strings")
            else:
                for value in evidence_ids:
                    if value not in material_ids:
                        errors.append(f"{prefix}.decision_snapshot.evidence_ids references missing material: {value}")
                if item.get("basis") == "evidence" and not evidence_ids:
                    errors.append(f"{prefix}.evidence basis requires at least one evidence id")
        linked_unknowns = item.get("unknown_ids")
        if not isinstance(linked_unknowns, list) or not all(isinstance(value, str) for value in linked_unknowns):
            errors.append(f"{prefix}.unknown_ids must be an array of strings")
        else:
            for value in linked_unknowns:
                if value not in unknown_ids:
                    errors.append(f"{prefix}.unknown_ids references missing unknown: {value}")
        if item.get("decision_id") not in decision_ids:
            errors.append(f"{prefix}.decision_id references missing decision: {item.get('decision_id')}")
        supersedes = item.get("supersedes")
        if supersedes is not None and (not isinstance(supersedes, str) or supersedes not in credential_ids):
            errors.append(f"{prefix}.supersedes references missing credential: {supersedes}")
        if isinstance(item.get("content_hash"), str) and item["content_hash"] != credential_hash(item):
            errors.append(f"{prefix}.content_hash does not match credential content")
    for duplicate in sorted(duplicate_ids(credentials)):
        errors.append(f"duplicate credential id: {duplicate}")
    credentials_by_id = {
        item["id"]: item for item in credentials
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if "credentials" in data:
        for index, decision in enumerate(data["decisions"]):
            if not isinstance(decision, dict):
                continue
            credential_id = decision.get("credential_id")
            if decision.get("status") == "confirmed" and not credential_id:
                errors.append(f"decisions[{index}].confirmed decision requires credential_id")
            if credential_id:
                linked = credentials_by_id.get(credential_id)
                if linked is None:
                    errors.append(f"decisions[{index}].credential_id references missing credential: {credential_id}")
                elif linked.get("decision_id") != decision.get("id"):
                    errors.append(f"decisions[{index}].credential_id links to a different decision")
    return errors


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"refusing to overwrite existing file: {path}")
        return 2
    timestamp = now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "project_id": args.project_id,
        "title": args.title,
        "stage": args.stage,
        "updated_at": timestamp,
        "materials": [],
        "decisions": [],
        "unknowns": [],
        "handoffs": [],
        "credentials": [],
        "audit_log": [{"at": timestamp, "action": "passport_initialized", "target_id": args.project_id, "reason": "project state created"}],
    }
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"created {path}")
    return 0


def command_add_material(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    if any(item.get("id") == args.id for item in data.get("materials", []) if isinstance(item, dict)):
        print(f"duplicate material id: {args.id}")
        return 2
    timestamp = now()
    material = {
        "id": args.id,
        "type": args.type,
        "title": args.title,
        "source_pointer": args.source_pointer,
        "status": args.status,
        "added_at": timestamp,
    }
    if args.content_sha256:
        material["content_sha256"] = args.content_sha256
    if args.supersedes_id:
        material["supersedes_id"] = args.supersedes_id
    data.setdefault("materials", []).append(material)
    data["updated_at"] = timestamp
    data.setdefault("audit_log", []).append({"at": timestamp, "action": "material_added", "target_id": args.id, "reason": args.reason})
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"added {args.id}")
    return 0


def command_record_credential(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    decisions = data.setdefault("decisions", [])
    credentials = data.setdefault("credentials", [])
    if any(item.get("id") == args.decision_id for item in decisions if isinstance(item, dict)):
        print(f"duplicate decision id: {args.decision_id}")
        return 2
    if any(item.get("id") == args.credential_id for item in credentials if isinstance(item, dict)):
        print(f"duplicate credential id: {args.credential_id}")
        return 2
    timestamp = now()
    decision = {
        "id": args.decision_id,
        "statement": args.statement,
        "status": args.status,
        "basis": args.basis,
        "evidence_ids": args.evidence_id,
        "recorded_at": timestamp,
        "credential_id": args.credential_id,
    }
    credential = {
        "id": args.credential_id,
        "decision_id": args.decision_id,
        "session_id": args.session_id,
        "record_pointer": args.record_pointer,
        "settled_by": args.settled_by,
        "authority": args.authority,
        "basis": args.basis,
        "scope": args.scope,
        "decision_snapshot": {
            "statement": args.statement,
            "status": args.status,
            "basis": args.basis,
            "evidence_ids": args.evidence_id,
        },
        "unknown_ids": args.unknown_id,
        "issued_at": timestamp,
        "supersedes": args.supersedes,
    }
    credential["content_hash"] = credential_hash(credential)
    decisions.append(decision)
    credentials.append(credential)
    data["updated_at"] = timestamp
    data.setdefault("audit_log", []).append({
        "at": timestamp,
        "action": "research_credential_recorded",
        "target_id": args.credential_id,
        "reason": args.reason,
    })
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded {args.credential_id}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        errors = validate(load(Path(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid passport: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("passport valid")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    result = {
        "project_id": data["project_id"],
        "stage": data["stage"],
        "materials": len(data["materials"]),
        "material_statuses": {status: sum(1 for item in data["materials"] if item["status"] == status) for status in sorted(MATERIAL_STATUSES)},
        "open_unknowns": sum(1 for item in data["unknowns"] if item["status"] == "open"),
        "prepared_handoffs": sum(1 for item in data["handoffs"] if item["status"] == "prepared"),
        "credentials": len(data.get("credentials", [])),
        "credential_authorities": {
            authority: sum(1 for item in data.get("credentials", []) if item["authority"] == authority)
            for authority in sorted(CREDENTIAL_AUTHORITIES)
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("path")
    init_parser.add_argument("--project-id", required=True)
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--stage", choices=sorted(STAGES), default="question")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    add_parser = subparsers.add_parser("add-material")
    add_parser.add_argument("path")
    add_parser.add_argument("--id", required=True)
    add_parser.add_argument("--type", required=True)
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--source-pointer", required=True)
    add_parser.add_argument("--status", choices=sorted(MATERIAL_STATUSES), default="raw")
    add_parser.add_argument("--content-sha256")
    add_parser.add_argument("--supersedes-id")
    add_parser.add_argument("--reason", default="material registered")
    add_parser.set_defaults(func=command_add_material)

    credential_parser = subparsers.add_parser("record-credential")
    credential_parser.add_argument("path")
    credential_parser.add_argument("--credential-id", required=True)
    credential_parser.add_argument("--decision-id", required=True)
    credential_parser.add_argument("--statement", required=True)
    credential_parser.add_argument("--status", choices=sorted(DECISION_STATUSES), default="proposed")
    credential_parser.add_argument("--session-id", required=True)
    credential_parser.add_argument("--record-pointer", required=True)
    credential_parser.add_argument("--settled-by", action="append", required=True)
    credential_parser.add_argument("--authority", choices=sorted(CREDENTIAL_AUTHORITIES), required=True)
    credential_parser.add_argument("--basis", choices=sorted(CREDENTIAL_BASES), required=True)
    credential_parser.add_argument("--scope", required=True)
    credential_parser.add_argument("--evidence-id", action="append", default=[])
    credential_parser.add_argument("--unknown-id", action="append", default=[])
    credential_parser.add_argument("--supersedes")
    credential_parser.add_argument("--reason", default="discussion produced a research credential")
    credential_parser.set_defaults(func=command_record_credential)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=command_validate)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("path")
    summary_parser.set_defaults(func=command_summary)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
