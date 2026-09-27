#!/usr/bin/env python3
"""Create and validate RW Peer Review ledger JSON files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rw-peer-review/v1"
STAGES = {"intake", "panel", "debate", "synthesis", "delivered", "closed"}
REVIEWER_ROLES = {"method", "domain", "adversary", "editor"}
MODEL_FAMILIES = {"claude", "codex", "human", "other"}
SOURCE_TYPES = {"manuscript", "reference", "data", "note"}
FINDING_IMPACTS = {"blocking", "non_blocking"}
FINDING_STATUSES = {"open", "sustained", "narrowed", "withdrawn", "answered", "deferred", "needs_input"}
FINDING_CLOSED_STATUSES = FINDING_STATUSES - {"open"}
CREDENTIAL_AUTHORITIES = {"advisory", "agent_consensus", "delegated", "human_confirmed"}
CREDENTIAL_BASES = {"evidence", "reasoning", "delegated_choice"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        raise ValueError("review ledger root must be an object")
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


def finding_content_hash(finding: dict[str, Any]) -> str:
    payload = {key: value for key, value in finding.items() if key != "credential_id"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_reviewers(data: dict[str, Any], errors: list[str]) -> set[str]:
    reviewer_ids: set[str] = set()
    for index, item in enumerate(data["reviewers"]):
        prefix = f"reviewers[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["id", "role", "model_family", "assigned_at"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        identifier = item.get("id")
        if isinstance(identifier, str):
            if not ((identifier.startswith("agent:") or identifier.startswith("human:")) and identifier.split(":", 1)[1].strip()):
                errors.append(f"{prefix}.id must start with agent: or human:")
            reviewer_ids.add(identifier)
        if item.get("role") not in REVIEWER_ROLES:
            errors.append(f"{prefix}.role is invalid")
        if item.get("model_family") not in MODEL_FAMILIES:
            errors.append(f"{prefix}.model_family is invalid")
    for duplicate in sorted(duplicate_ids(data["reviewers"])):
        errors.append(f"duplicate reviewer id: {duplicate}")
    return reviewer_ids


def validate_sources(data: dict[str, Any], errors: list[str]) -> set[str]:
    source_ids: set[str] = set()
    for index, item in enumerate(data["sources"]):
        prefix = f"sources[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ["id", "type", "title", "pointer", "added_at"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if item.get("type") not in SOURCE_TYPES:
            errors.append(f"{prefix}.type is invalid")
        if isinstance(item.get("id"), str):
            source_ids.add(item["id"])
    for duplicate in sorted(duplicate_ids(data["sources"])):
        errors.append(f"duplicate source id: {duplicate}")
    return source_ids


def validate_findings(
    data: dict[str, Any], errors: list[str], reviewer_ids: set[str], source_ids: set[str], credential_ids: set[str]
) -> set[str]:
    finding_ids: set[str] = set()
    for index, item in enumerate(data["findings"]):
        prefix = f"findings[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "id", "location", "quote", "problem", "fix",
            "publication_impact", "status", "evidence_ids", "raised_by", "recorded_at",
        ]:
            if field not in item:
                errors.append(f"{prefix} missing field: {field}")
        for field in ["id", "location", "quote", "problem", "fix", "recorded_at"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if isinstance(item.get("id"), str):
            finding_ids.add(item["id"])
        if item.get("publication_impact") not in FINDING_IMPACTS:
            errors.append(f"{prefix}.publication_impact is invalid")
        if item.get("status") not in FINDING_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if item.get("raised_by") not in reviewer_ids:
            errors.append(f"{prefix}.raised_by references missing reviewer: {item.get('raised_by')}")
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
            errors.append(f"{prefix}.evidence_ids must be an array of strings")
            evidence_ids = []
        else:
            for value in evidence_ids:
                if value not in source_ids:
                    errors.append(f"{prefix}.evidence_ids references missing source: {value}")
        resolution_note = item.get("resolution_note")
        if item.get("status") in FINDING_CLOSED_STATUSES:
            if not isinstance(resolution_note, str) or not resolution_note.strip():
                errors.append(f"{prefix}.{item.get('status')} requires a resolution_note")
            if item.get("status") == "withdrawn" and not evidence_ids:
                errors.append(f"{prefix}.withdrawn requires at least one evidence id")
        elif resolution_note is not None and not isinstance(resolution_note, str):
            errors.append(f"{prefix}.resolution_note must be a string")
        credential_id = item.get("credential_id")
        if credential_id is not None and credential_id not in credential_ids:
            errors.append(f"{prefix}.credential_id references missing credential: {credential_id}")
        evidence_credential_ids = item.get("evidence_credential_ids")
        context_pack_id = item.get("context_pack_id")
        if evidence_credential_ids is not None:
            if not isinstance(evidence_credential_ids, list) or not evidence_credential_ids or not all(
                isinstance(value, str) and value.strip() for value in evidence_credential_ids
            ):
                errors.append(f"{prefix}.evidence_credential_ids must be a non-empty array of strings")
            if not isinstance(context_pack_id, str) or not context_pack_id.strip():
                errors.append(f"{prefix}.context_pack_id is required with evidence_credential_ids")
        elif context_pack_id is not None:
            errors.append(f"{prefix}.evidence_credential_ids is required with context_pack_id")
    for duplicate in sorted(duplicate_ids(data["findings"])):
        errors.append(f"duplicate finding id: {duplicate}")
    return finding_ids


def validate_credentials(
    data: dict[str, Any], errors: list[str], finding_ids: set[str], source_ids: set[str], credential_ids: set[str]
) -> None:
    for index, item in enumerate(data["credentials"]):
        prefix = f"credentials[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "id", "finding_id", "session_id", "record_pointer", "settled_by",
            "authority", "basis", "scope", "finding_snapshot", "issued_at", "content_hash",
        ]:
            if field not in item:
                errors.append(f"{prefix} missing field: {field}")
        for field in ["id", "finding_id", "session_id", "record_pointer", "scope", "issued_at", "content_hash"]:
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if item.get("authority") not in CREDENTIAL_AUTHORITIES:
            errors.append(f"{prefix}.authority is invalid")
        if item.get("basis") not in CREDENTIAL_BASES:
            errors.append(f"{prefix}.basis is invalid")
        settled_by = item.get("settled_by")
        if not isinstance(settled_by, list) or not settled_by or not all(
            isinstance(value, str) and (value.startswith("human:") or value.startswith("agent:")) and value.split(":", 1)[1].strip()
            for value in settled_by
        ):
            errors.append(f"{prefix}.settled_by must contain human: or agent: identifiers")
        elif item.get("authority") == "human_confirmed" and not any(value.startswith("human:") for value in settled_by):
            errors.append(f"{prefix}.human_confirmed requires a human: identifier")
        elif item.get("authority") in {"agent_consensus", "delegated"} and not any(
            value.startswith("agent:") for value in settled_by
        ):
            errors.append(f"{prefix}.{item.get('authority')} requires an agent: identifier")
        if isinstance(settled_by, list) and all(isinstance(value, str) for value in settled_by):
            if len(set(settled_by)) != len(settled_by):
                errors.append(f"{prefix}.settled_by contains duplicate identifiers")
            if item.get("authority") == "agent_consensus" and len({value for value in settled_by if value.startswith("agent:")}) < 2:
                errors.append(f"{prefix}.agent_consensus requires at least two distinct agents")
        snapshot = item.get("finding_snapshot")
        if not isinstance(snapshot, dict):
            errors.append(f"{prefix}.finding_snapshot must be an object")
        else:
            for field in ["status", "publication_impact", "resolution_note", "evidence_ids"]:
                if field not in snapshot:
                    errors.append(f"{prefix}.finding_snapshot missing field: {field}")
            if snapshot.get("status") not in FINDING_STATUSES:
                errors.append(f"{prefix}.finding_snapshot.status is invalid")
            if snapshot.get("publication_impact") not in FINDING_IMPACTS:
                errors.append(f"{prefix}.finding_snapshot.publication_impact is invalid")
            if not isinstance(snapshot.get("resolution_note"), str) or not snapshot.get("resolution_note", "").strip():
                errors.append(f"{prefix}.finding_snapshot.resolution_note must be a non-empty string")
            if snapshot.get("status") == "withdrawn" and item.get("authority") == "advisory":
                errors.append(f"{prefix}.advisory credential cannot withdraw a finding")
            evidence_ids = snapshot.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
                errors.append(f"{prefix}.finding_snapshot.evidence_ids must be an array of strings")
            else:
                for value in evidence_ids:
                    if value not in source_ids:
                        errors.append(f"{prefix}.finding_snapshot.evidence_ids references missing source: {value}")
                if item.get("basis") == "evidence" and not evidence_ids:
                    errors.append(f"{prefix}.evidence basis requires at least one evidence id")
            evidence_credential_ids = snapshot.get("evidence_credential_ids")
            context_pack_id = snapshot.get("context_pack_id")
            if evidence_credential_ids is not None:
                if not isinstance(evidence_credential_ids, list) or not evidence_credential_ids or not all(
                    isinstance(value, str) and value.strip() for value in evidence_credential_ids
                ):
                    errors.append(
                        f"{prefix}.finding_snapshot.evidence_credential_ids must be a non-empty array of strings"
                    )
                if not isinstance(context_pack_id, str) or not context_pack_id.strip():
                    errors.append(
                        f"{prefix}.finding_snapshot.context_pack_id is required with evidence_credential_ids"
                    )
        if item.get("finding_id") not in finding_ids:
            errors.append(f"{prefix}.finding_id references missing finding: {item.get('finding_id')}")
        supersedes = item.get("supersedes")
        if supersedes is not None and (not isinstance(supersedes, str) or supersedes not in credential_ids):
            errors.append(f"{prefix}.supersedes references missing credential: {supersedes}")
        if isinstance(item.get("content_hash"), str) and item["content_hash"] != credential_hash(item):
            errors.append(f"{prefix}.content_hash does not match credential content")
    for duplicate in sorted(duplicate_ids(data["credentials"])):
        errors.append(f"duplicate credential id: {duplicate}")


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
    required = [
        "schema_version", "review_id", "manuscript", "stage", "updated_at",
        "reviewers", "sources", "findings", "credentials", "audit_log",
    ]
    for field in required:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(data["review_id"], str) or not data["review_id"].strip():
        errors.append("review_id must be a non-empty string")
    if data["stage"] not in STAGES:
        errors.append(f"invalid stage: {data['stage']}")
    for field in ["reviewers", "sources", "findings", "credentials", "audit_log"]:
        if not isinstance(data[field], list):
            errors.append(f"{field} must be an array")
    manuscript = data["manuscript"]
    if not isinstance(manuscript, dict):
        errors.append("manuscript must be an object")
    else:
        for field in ["id", "title", "journal", "version", "pointer"]:
            if not isinstance(manuscript.get(field), str) or not manuscript[field].strip():
                errors.append(f"manuscript.{field} must be a non-empty string")
    if errors:
        return errors

    reviewer_ids = validate_reviewers(data, errors)
    source_ids = validate_sources(data, errors)
    credential_ids = {
        item["id"] for item in data["credentials"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    finding_ids = validate_findings(data, errors, reviewer_ids, source_ids, credential_ids)
    validate_credentials(data, errors, finding_ids, source_ids, credential_ids)

    by_credential = {item["id"]: item for item in data["credentials"] if isinstance(item, dict) and isinstance(item.get("id"), str)}
    superseded = {item.get("supersedes") for item in data["credentials"] if isinstance(item, dict) and isinstance(item.get("supersedes"), str)}
    for index, finding in enumerate(data["findings"]):
        if not isinstance(finding, dict) or not isinstance(finding.get("credential_id"), str):
            continue
        credential = by_credential.get(finding["credential_id"])
        if credential is None:
            continue
        if credential.get("finding_id") != finding.get("id"):
            errors.append(f"findings[{index}].credential_id belongs to a different finding")
        if credential["id"] in superseded:
            errors.append(f"findings[{index}].credential_id has been superseded")
        bound_hash = credential.get("finding_content_hash")
        if bound_hash is not None and bound_hash != finding_content_hash(finding):
            errors.append(f"findings[{index}].credential_id is stale for current finding content")
        snapshot = credential.get("finding_snapshot")
        if isinstance(snapshot, dict):
            for field in ("status", "publication_impact", "resolution_note", "evidence_ids", "evidence_credential_ids", "context_pack_id"):
                if snapshot.get(field) != finding.get(field):
                    errors.append(f"findings[{index}].credential_id snapshot is stale for {field}")
    for item in by_credential.values():
        predecessor = by_credential.get(item.get("supersedes"))
        if predecessor and (predecessor.get("finding_id") != item.get("finding_id") or predecessor["id"] == item["id"]):
            errors.append(f"credential {item['id']} has invalid supersedes lineage")
        seen = set()
        current = item
        while current and current.get("supersedes"):
            identifier = current["id"]
            if identifier in seen:
                errors.append(f"credential {item['id']} has cyclic supersedes lineage")
                break
            seen.add(identifier)
            current = by_credential.get(current.get("supersedes"))

    if data["stage"] in {"synthesis", "delivered", "closed"}:
        for index, item in enumerate(data["findings"]):
            if not isinstance(item, dict):
                continue
            if item.get("status") == "open" and item.get("publication_impact") == "blocking":
                errors.append(f"findings[{index}] is open and blocking; stage {data['stage']} is not allowed")
    return errors


def append_audit(data: dict[str, Any], timestamp: str, action: str, target_id: str, reason: str) -> None:
    data["updated_at"] = timestamp
    data.setdefault("audit_log", []).append(
        {"at": timestamp, "action": action, "target_id": target_id, "reason": reason}
    )


def write_if_valid(path: Path, data: dict[str, Any], message: str) -> int:
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(message)
    return 0


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"refusing to overwrite existing file: {path}")
        return 2
    timestamp = now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "review_id": args.review_id,
        "manuscript": {
            "id": args.manuscript_id,
            "title": args.title,
            "journal": args.journal,
            "version": args.version,
            "pointer": args.pointer,
        },
        "stage": args.stage,
        "updated_at": timestamp,
        "reviewers": [],
        "sources": [],
        "findings": [],
        "credentials": [],
        "audit_log": [
            {"at": timestamp, "action": "review_initialized", "target_id": args.review_id, "reason": "review opened"}
        ],
    }
    return write_if_valid(path, data, f"created {path}")


def command_add_reviewer(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    reviewers = data.setdefault("reviewers", [])
    if any(item.get("id") == args.id for item in reviewers if isinstance(item, dict)):
        print(f"duplicate reviewer id: {args.id}")
        return 2
    timestamp = now()
    reviewers.append({
        "id": args.id,
        "role": args.role,
        "model_family": args.model_family,
        "assigned_at": timestamp,
    })
    append_audit(data, timestamp, "reviewer_assigned", args.id, args.reason)
    return write_if_valid(path, data, f"assigned {args.id}")


def command_add_source(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    sources = data.setdefault("sources", [])
    if any(item.get("id") == args.id for item in sources if isinstance(item, dict)):
        print(f"duplicate source id: {args.id}")
        return 2
    timestamp = now()
    sources.append({
        "id": args.id,
        "type": args.type,
        "title": args.title,
        "pointer": args.pointer,
        "added_at": timestamp,
    })
    append_audit(data, timestamp, "source_added", args.id, args.reason)
    return write_if_valid(path, data, f"added {args.id}")


def command_add_finding(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    findings = data.setdefault("findings", [])
    if any(item.get("id") == args.id for item in findings if isinstance(item, dict)):
        print(f"duplicate finding id: {args.id}")
        return 2
    timestamp = now()
    finding = {
        "id": args.id,
        "location": args.location,
        "quote": args.quote,
        "problem": args.problem,
        "fix": args.fix,
        "publication_impact": args.publication_impact,
        "status": args.status,
        "evidence_ids": args.evidence_id,
        "raised_by": args.raised_by,
        "recorded_at": timestamp,
    }
    if args.resolution_note:
        finding["resolution_note"] = args.resolution_note
    evidence_credential_ids = getattr(args, "evidence_credential_id", [])
    context_pack_id = getattr(args, "context_pack_id", None)
    if evidence_credential_ids:
        finding["evidence_credential_ids"] = evidence_credential_ids
        finding["context_pack_id"] = context_pack_id
    findings.append(finding)
    append_audit(data, timestamp, "finding_added", args.id, args.reason)
    return write_if_valid(path, data, f"added {args.id}")


def command_set_finding_status(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    target = next(
        (item for item in data.get("findings", []) if isinstance(item, dict) and item.get("id") == args.finding_id),
        None,
    )
    if target is None:
        print(f"missing finding: {args.finding_id}")
        return 2
    timestamp = now()
    # An old ruling remains in history, but no longer attests to a changed finding.
    target.pop("credential_id", None)
    target["status"] = args.status
    if args.resolution_note:
        target["resolution_note"] = args.resolution_note
    for value in args.evidence_id:
        if value not in target.setdefault("evidence_ids", []):
            target["evidence_ids"].append(value)
    append_audit(data, timestamp, "finding_status_set", args.finding_id, args.reason)
    return write_if_valid(path, data, f"updated {args.finding_id}")


def command_record_credential(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    credentials = data.setdefault("credentials", [])
    if any(item.get("id") == args.credential_id for item in credentials if isinstance(item, dict)):
        print(f"duplicate credential id: {args.credential_id}")
        return 2
    target = next(
        (item for item in data.get("findings", []) if isinstance(item, dict) and item.get("id") == args.finding_id),
        None,
    )
    if target is None:
        print(f"missing finding: {args.finding_id}")
        return 2
    timestamp = now()
    credential = {
        "id": args.credential_id,
        "finding_id": args.finding_id,
        "session_id": args.session_id,
        "record_pointer": args.record_pointer,
        "settled_by": args.settled_by,
        "authority": args.authority,
        "basis": args.basis,
        "scope": args.scope,
        "finding_content_hash": finding_content_hash(target),
        "finding_snapshot": {
            "status": target.get("status"),
            "publication_impact": target.get("publication_impact"),
            "resolution_note": target.get("resolution_note", ""),
            "evidence_ids": list(target.get("evidence_ids", [])),
        },
        "issued_at": timestamp,
        "supersedes": args.supersedes,
    }
    if target.get("evidence_credential_ids"):
        credential["finding_snapshot"]["evidence_credential_ids"] = list(target["evidence_credential_ids"])
        credential["finding_snapshot"]["context_pack_id"] = target.get("context_pack_id")
    credential["content_hash"] = credential_hash(credential)
    credentials.append(credential)
    target["credential_id"] = args.credential_id
    append_audit(data, timestamp, "review_credential_recorded", args.credential_id, args.reason)
    return write_if_valid(path, data, f"recorded {args.credential_id}")


def command_validate(args: argparse.Namespace) -> int:
    try:
        errors = validate(load(Path(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid review ledger: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("review ledger valid")
    return 0


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    findings = data.get("findings", [])
    return {
        "review_id": data["review_id"],
        "manuscript": data["manuscript"]["title"],
        "journal": data["manuscript"]["journal"],
        "stage": data["stage"],
        "reviewers": {
            role: sum(1 for item in data.get("reviewers", []) if item["role"] == role)
            for role in sorted(REVIEWER_ROLES)
        },
        "sources": len(data.get("sources", [])),
        "findings": len(findings),
        "finding_statuses": {
            status: sum(1 for item in findings if item["status"] == status)
            for status in sorted(FINDING_STATUSES)
        },
        "open_blocking": sum(
            1 for item in findings if item["status"] == "open" and item["publication_impact"] == "blocking"
        ),
        "open_non_blocking": sum(
            1 for item in findings if item["status"] == "open" and item["publication_impact"] == "non_blocking"
        ),
        "credentials": len(data.get("credentials", [])),
    }


def command_summary(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    print(json.dumps(summarize(data), ensure_ascii=False, indent=2))
    return 0


def command_gate(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    summary = summarize(data)
    if not data["findings"]:
        print("REVIEW: no findings recorded; review completeness is not established")
        return 1
    if summary["open_blocking"]:
        print(f"BLOCK: {summary['open_blocking']} open blocking findings")
        return 2
    if summary["open_non_blocking"]:
        print(f"REVIEW: {summary['open_non_blocking']} open non-blocking findings")
        return 1
    active_ids = {finding.get("credential_id") for finding in data["findings"] if isinstance(finding.get("credential_id"), str)}
    if any(item["id"] in active_ids and not item.get("finding_content_hash") for item in data["credentials"]):
        print("REVIEW: legacy active credentials lack current finding content binding; reissue before reuse")
        return 1
    print("PASS: every finding has a recorded outcome; disposition only, not acceptance or evidence freshness")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("path")
    init_parser.add_argument("--review-id", required=True)
    init_parser.add_argument("--manuscript-id", required=True)
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--journal", required=True)
    init_parser.add_argument("--version", default="v1")
    init_parser.add_argument("--pointer", required=True)
    init_parser.add_argument("--stage", choices=sorted(STAGES), default="intake")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    reviewer_parser = subparsers.add_parser("add-reviewer")
    reviewer_parser.add_argument("path")
    reviewer_parser.add_argument("--id", required=True)
    reviewer_parser.add_argument("--role", choices=sorted(REVIEWER_ROLES), required=True)
    reviewer_parser.add_argument("--model-family", choices=sorted(MODEL_FAMILIES), required=True)
    reviewer_parser.add_argument("--reason", default="reviewer assigned")
    reviewer_parser.set_defaults(func=command_add_reviewer)

    source_parser = subparsers.add_parser("add-source")
    source_parser.add_argument("path")
    source_parser.add_argument("--id", required=True)
    source_parser.add_argument("--type", choices=sorted(SOURCE_TYPES), required=True)
    source_parser.add_argument("--title", required=True)
    source_parser.add_argument("--pointer", required=True)
    source_parser.add_argument("--reason", default="source registered")
    source_parser.set_defaults(func=command_add_source)

    finding_parser = subparsers.add_parser("add-finding")
    finding_parser.add_argument("path")
    finding_parser.add_argument("--id", required=True)
    finding_parser.add_argument("--location", required=True)
    finding_parser.add_argument("--quote", required=True)
    finding_parser.add_argument("--problem", required=True)
    finding_parser.add_argument("--fix", required=True)
    finding_parser.add_argument("--publication-impact", choices=sorted(FINDING_IMPACTS), required=True)
    finding_parser.add_argument("--status", choices=sorted(FINDING_STATUSES), default="open")
    finding_parser.add_argument("--evidence-id", action="append", default=[])
    finding_parser.add_argument("--evidence-credential-id", action="append", default=[])
    finding_parser.add_argument("--context-pack-id")
    finding_parser.add_argument("--raised-by", required=True)
    finding_parser.add_argument("--resolution-note")
    finding_parser.add_argument("--reason", default="finding recorded")
    finding_parser.set_defaults(func=command_add_finding)

    status_parser = subparsers.add_parser("set-finding-status")
    status_parser.add_argument("path")
    status_parser.add_argument("--finding-id", required=True)
    status_parser.add_argument("--status", choices=sorted(FINDING_STATUSES), required=True)
    status_parser.add_argument("--resolution-note")
    status_parser.add_argument("--evidence-id", action="append", default=[])
    status_parser.add_argument("--reason", default="finding status changed")
    status_parser.set_defaults(func=command_set_finding_status)

    credential_parser = subparsers.add_parser("record-credential")
    credential_parser.add_argument("path")
    credential_parser.add_argument("--credential-id", required=True)
    credential_parser.add_argument("--finding-id", required=True)
    credential_parser.add_argument("--session-id", required=True)
    credential_parser.add_argument("--record-pointer", required=True)
    credential_parser.add_argument("--settled-by", action="append", required=True)
    credential_parser.add_argument("--authority", choices=sorted(CREDENTIAL_AUTHORITIES), required=True)
    credential_parser.add_argument("--basis", choices=sorted(CREDENTIAL_BASES), required=True)
    credential_parser.add_argument("--scope", required=True)
    credential_parser.add_argument("--supersedes")
    credential_parser.add_argument("--reason", default="finding disposition settled")
    credential_parser.set_defaults(func=command_record_credential)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=command_validate)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("path")
    summary_parser.set_defaults(func=command_summary)

    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("path")
    gate_parser.set_defaults(func=command_gate)
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
