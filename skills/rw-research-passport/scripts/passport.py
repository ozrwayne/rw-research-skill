#!/usr/bin/env python3
"""Create and validate RW Research Passport JSON files."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
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


@contextmanager
def exclusive_lock(path: Path):
    """Serialize cooperating CLI writers using a stable sidecar lock inode."""
    if path.is_symlink():
        raise ValueError("lock path must not be a symbolic link")
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> Any:
    raise ValueError("non-finite JSON number")


def finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def strict_json_loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=unique_json_object,
                      parse_constant=reject_nonfinite, parse_float=finite_float)


def load(path: Path) -> dict[str, Any]:
    data = strict_json_loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("passport root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError("state file must not be a symbolic link")
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
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0
    except (ValueError, TypeError, AttributeError):
        return False


def cycle_errors(items: list[Any], field: str, label: str) -> list[str]:
    links = {item["id"]: item[field] for item in items if isinstance(item, dict)
             and isinstance(item.get("id"), str) and isinstance(item.get(field), str)}
    errors = []
    done: set[str] = set()
    for start in links:
        active: set[str] = set()
        current = start
        while current in links and current not in done:
            if current in active:
                errors.append(f"{label} contains a cycle: {current}")
                break
            active.add(current)
            current = links[current]
        done.update(active)
    return errors


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["passport root must be an object"]
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError):
        return ["state must contain only finite JSON-compatible values"]
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
    if not isinstance(data["title"], str) or not data["title"].strip():
        errors.append("title must be a non-empty string")
    if not valid_timestamp(data["updated_at"]):
        errors.append("updated_at must be a UTC ISO 8601 timestamp")
    if data["stage"] not in tuple(STAGES):
        errors.append(f"invalid stage: {data['stage']}")
    for field in ["materials", "decisions", "unknowns", "handoffs", "audit_log"]:
        if not isinstance(data[field], list):
            errors.append(f"{field} must be an array")
    if "credentials" in data and not isinstance(data["credentials"], list):
        errors.append("credentials must be an array")
    if errors:
        return errors

    for index, entry in enumerate(data["audit_log"]):
        if not isinstance(entry, dict):
            errors.append(f"audit_log[{index}] must be an object")
            continue
        for field in ["action", "target_id", "reason"]:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"audit_log[{index}].{field} must be a non-empty string")
        if not valid_timestamp(entry.get("at")):
            errors.append(f"audit_log[{index}].at must be a UTC ISO 8601 timestamp")

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
        if not valid_timestamp(item.get("added_at")):
            errors.append(f"{prefix}.added_at must be a UTC ISO 8601 timestamp")
        if item.get("status") not in tuple(MATERIAL_STATUSES):
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

    successor_targets: set[str] = set()
    for _, _, supersedes_id in supersedes_links:
        if supersedes_id in successor_targets:
            errors.append(f"material supersession branches from: {supersedes_id}")
        successor_targets.add(supersedes_id)
    errors.extend(cycle_errors(data["materials"], "supersedes_id", "material supersession"))
    material_by_id = {item["id"]: item for item in data["materials"]
                      if isinstance(item, dict) and isinstance(item.get("id"), str)}
    for prefix, _, supersedes_id in supersedes_links:
        if supersedes_id in material_by_id and material_by_id[supersedes_id].get("status") != "superseded":
            errors.append(f"{prefix}.supersedes_id must reference a superseded material")

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
            for field in required_fields:
                if field not in {"evidence_ids", "material_ids"} and (
                    not isinstance(item.get(field), str) or not item[field].strip()
                ):
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if "recorded_at" in required_fields and not valid_timestamp(item.get("recorded_at")):
                errors.append(f"{prefix}.recorded_at must be a UTC ISO 8601 timestamp")
            if collection == "handoffs":
                for field in ["from_stage", "to_stage"]:
                    if item.get(field) not in tuple(STAGES):
                        errors.append(f"{prefix}.{field} is invalid")
            if item.get("status") not in tuple(statuses):
                errors.append(f"{prefix}.status is invalid")
            if collection == "decisions" and isinstance(item.get("id"), str):
                decision_ids.add(item["id"])
            if collection == "unknowns" and isinstance(item.get("id"), str):
                unknown_ids.add(item["id"])
            link_field = "evidence_ids" if collection == "decisions" else "material_ids" if collection == "handoffs" else None
            if link_field:
                links = item.get(link_field)
                if not isinstance(links, list) or not all(isinstance(value, str) and value.strip() for value in links):
                    errors.append(f"{prefix}.{link_field} must be an array of strings")
                else:
                    if len(set(links)) != len(links):
                        errors.append(f"{prefix}.{link_field} contains duplicate references")
                    for value in links:
                        if item.get("status") in ("confirmed", "prepared") and value in material_by_id and material_by_id[value].get("status") in ("rejected", "superseded"):
                            errors.append(f"{prefix}.{link_field} references inactive material: {value}")
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
        if item.get("authority") not in tuple(CREDENTIAL_AUTHORITIES):
            errors.append(f"{prefix}.authority is invalid")
        if item.get("basis") not in tuple(CREDENTIAL_BASES):
            errors.append(f"{prefix}.basis is invalid")
        settled_by = item.get("settled_by")
        if not isinstance(settled_by, list) or not settled_by or not all(
            isinstance(value, str) and (value.startswith("human:") or value.startswith("agent:")) and value.split(":", 1)[1].strip()
            for value in settled_by
        ):
            errors.append(f"{prefix}.settled_by must contain human: or agent: identifiers")
        elif item.get("authority") == "human_confirmed" and not any(value.startswith("human:") for value in settled_by):
            errors.append(f"{prefix}.human_confirmed requires a human: identifier")
        elif item.get("authority") in ("agent_consensus", "delegated") and not any(
            value.startswith("agent:") for value in settled_by
        ):
            errors.append(f"{prefix}.{item.get('authority')} requires an agent: identifier")
        if isinstance(settled_by, list) and all(isinstance(value, str) for value in settled_by):
            if len(set(settled_by)) != len(settled_by):
                errors.append(f"{prefix}.settled_by contains duplicate identifiers")
            if item.get("authority") == "agent_consensus" and len({value for value in settled_by if value.startswith("agent:")}) < 2:
                errors.append(f"{prefix}.agent_consensus requires at least two distinct agents")
        if not valid_timestamp(item.get("issued_at")):
            errors.append(f"{prefix}.issued_at must be a UTC ISO 8601 timestamp")
        snapshot = item.get("decision_snapshot")
        if not isinstance(snapshot, dict):
            errors.append(f"{prefix}.decision_snapshot must be an object")
        else:
            for field in ["statement", "status", "basis", "evidence_ids"]:
                if field not in snapshot:
                    errors.append(f"{prefix}.decision_snapshot missing field: {field}")
            if not isinstance(snapshot.get("statement"), str) or not snapshot.get("statement", "").strip():
                errors.append(f"{prefix}.decision_snapshot.statement must be a non-empty string")
            if snapshot.get("status") not in tuple(DECISION_STATUSES):
                errors.append(f"{prefix}.decision_snapshot.status is invalid")
            if snapshot.get("basis") not in tuple(CREDENTIAL_BASES):
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
        if not isinstance(item.get("decision_id"), str) or item.get("decision_id") not in decision_ids:
            errors.append(f"{prefix}.decision_id references missing decision: {item.get('decision_id')}")
        supersedes = item.get("supersedes")
        if supersedes is not None and (not isinstance(supersedes, str) or supersedes not in credential_ids):
            errors.append(f"{prefix}.supersedes references missing credential: {supersedes}")
        if isinstance(item.get("content_hash"), str) and item["content_hash"] != credential_hash(item):
            errors.append(f"{prefix}.content_hash does not match credential content")
    for duplicate in sorted(duplicate_ids(credentials)):
        errors.append(f"duplicate credential id: {duplicate}")
    errors.extend(cycle_errors(credentials, "supersedes", "credential supersession"))
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
                if not isinstance(credential_id, str):
                    errors.append(f"decisions[{index}].credential_id must be a string")
                    continue
                linked = credentials_by_id.get(credential_id)
                if linked is None:
                    errors.append(f"decisions[{index}].credential_id references missing credential: {credential_id}")
                elif linked.get("decision_id") != decision.get("id"):
                    errors.append(f"decisions[{index}].credential_id links to a different decision")
                elif isinstance(linked.get("decision_snapshot"), dict):
                    snapshot = linked["decision_snapshot"]
                    for field in ["statement", "status", "basis", "evidence_ids"]:
                        # Supersession invalidates the live record, not its immutable credential.
                        if field == "status" and decision.get("status") == "superseded":
                            continue
                        if decision.get(field) != snapshot.get(field):
                            errors.append(f"decisions[{index}].{field} does not match credential snapshot")
        decisions_by_id = {item["id"]: item for item in data["decisions"]
                           if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for index, credential in enumerate(credentials):
            if not isinstance(credential, dict):
                continue
            decision_id = credential.get("decision_id")
            linked_decision = decisions_by_id.get(decision_id) if isinstance(decision_id, str) else None
            if linked_decision is not None and linked_decision.get("credential_id") != credential.get("id"):
                errors.append(f"credentials[{index}] requires a reciprocal decision link")
            supersedes = credential.get("supersedes")
            old = credentials_by_id.get(supersedes) if isinstance(supersedes, str) else None
            if old is not None:
                old_id = old.get("decision_id")
                previous = decisions_by_id.get(old_id) if isinstance(old_id, str) else None
                if previous is not None and previous.get("status") != "superseded":
                    errors.append(f"credentials[{index}].supersedes requires the old decision to be superseded")
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
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
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
    if args.supersedes_id:
        old = next((item for item in data["materials"] if item["id"] == args.supersedes_id), None)
        if old is None:
            print("supersedes-id requires an existing material")
            return 2
        if any(item.get("supersedes_id") == old["id"] for item in data["materials"]):
            print("supersedes-id already has a successor; material supersession must not branch")
            return 2
        # Historical imports may register an already superseded node before its
        # successor. Link it once without pretending its status changed now.
        action = "material_history_linked" if old["status"] == "superseded" else "material_superseded"
        old["status"] = "superseded"
        data["audit_log"].append({"at": timestamp, "action": action, "target_id": old["id"], "reason": args.reason})
        for collection, link, status, replacement in [
            ("decisions", "evidence_ids", "confirmed", "superseded"),
            ("handoffs", "material_ids", "prepared", "rejected"),
        ]:
            for item in data[collection]:
                if item["status"] == status and old["id"] in item[link]:
                    item["status"] = replacement
                    data["audit_log"].append({"at": timestamp, "action": f"{collection[:-1]}_invalidated", "target_id": item["id"], "reason": args.reason})
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
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    decisions = data.setdefault("decisions", [])
    credentials = data.setdefault("credentials", [])
    if any(item.get("id") == args.decision_id for item in decisions if isinstance(item, dict)):
        print(f"duplicate decision id: {args.decision_id}")
        return 2
    if any(item.get("id") == args.credential_id for item in credentials if isinstance(item, dict)):
        print(f"duplicate credential id: {args.credential_id}")
        return 2
    timestamp = now()
    if args.supersedes:
        previous = next((item for item in credentials if item["id"] == args.supersedes), None)
        old_decision = next((item for item in decisions if previous and item["id"] == previous["decision_id"]), None)
        if old_decision is None or old_decision["status"] == "superseded":
            print("supersedes requires an active existing credential decision")
            return 2
        old_decision["status"] = "superseded"
        data["audit_log"].append({"at": timestamp, "action": "decision_superseded", "target_id": old_decision["id"], "reason": args.reason})
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
        data = load(Path(args.path))
        errors = validate(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid passport: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("passport valid" if "credentials" in data else "legacy passport structurally valid; decision credentials not verified")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    result = {
        "project_id": data["project_id"],
        "credential_integrity": "checked" if "credentials" in data else "legacy_unverified",
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
    try:
        if args.command in {"init", "add-material", "record-credential"}:
            path = Path(args.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with exclusive_lock(path.with_name(path.name + ".lock")):
                return args.func(args)
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"invalid passport: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
