#!/usr/bin/env python3
"""Create, validate, and record on-device submission packets."""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SCHEMA_VERSION = "rw-journal-submission/submission-packet/v2"
LEGACY_SCHEMA_VERSION = "rw-journal-submission/submission-packet/v1"
FIELD_STATUSES = {"confirmed", "missing", "needs_author_confirmation", "not_applicable"}
PORTAL_STEP_STATUSES = {"complete", "incomplete", "unverified"}
FINAL_SUBMISSION_STATES = {"not_submitted", "awaiting_human_submit", "submitted", "unverified"}
SUBMISSION_EVIDENCE_SOURCES = {"user_confirmation", "platform_receipt"}
AGENT_OBSERVATIONS = {"not_observed", "observed"}
DISPLAY_ITEM_KINDS = {"figure", "table"}
DISPLAY_NUMBERING_POLICIES = {"separate_sequences", "global_sequence"}
PROOF_STATES = {"not_generated", "available", "opened", "reviewed", "unverified"}
PROOF_TEXT_CHECKS = {"not_run", "passed", "failed", "not_available"}
PROOF_VISUAL_CHECKS = {"not_run", "needs_human_visual_check", "human_confirmed", "agent_verified"}
RETURN_EVENT_STATES = {"returned", "resolved"}

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
DISPLAY_LABEL_RE = re.compile(r"\b(Figure|Table)\s+(\d+)\b", re.IGNORECASE)


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
        raise ValueError("submission packet root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ValueError("state file must not be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0
    except (ValueError, TypeError, AttributeError):
        return False


def require_string(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(data.get(field), str) or not data[field].strip():
        errors.append(f"{field} must be a non-empty string")


def duplicate_ids(items: list[Any]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            if item["id"] in seen:
                duplicates.add(item["id"])
            seen.add(item["id"])
    return duplicates


def validate_status(item: dict[str, Any], prefix: str, errors: list[str]) -> None:
    status = item.get("status")
    if status not in tuple(FIELD_STATUSES):
        errors.append(f"{prefix}.status must be one of: {', '.join(sorted(FIELD_STATUSES))}")


def default_final_submission() -> dict[str, Any]:
    return {"state": "not_submitted", "evidence": None, "agent_observation": "not_observed"}


def default_proof() -> dict[str, Any]:
    return {
        "state": "not_generated",
        "text_check": "not_run",
        "visual_check": "not_run",
        "checked_at": "",
        "evidence_source": "",
        "agent_observation": "not_observed",
    }


def default_display_policy() -> dict[str, Any]:
    return {
        "separate_files_required": False,
        "numbering_policy": "separate_sequences",
        "main_manuscript_embeds": "allowed",
        "main_material_id": "",
    }


def validate_final_submission(portal: dict[str, Any], errors: list[str]) -> None:
    final_submission = portal.get("final_submission")
    if final_submission is None:
        return
    if not isinstance(final_submission, dict):
        errors.append("portal.final_submission must be an object")
        return
    state = final_submission.get("state")
    if state not in tuple(FINAL_SUBMISSION_STATES):
        errors.append("portal.final_submission.state is invalid")
    observation = final_submission.get("agent_observation")
    if observation not in tuple(AGENT_OBSERVATIONS):
        errors.append("portal.final_submission.agent_observation is invalid")
    evidence = final_submission.get("evidence")
    if state == "submitted" and not isinstance(evidence, dict):
        errors.append("portal.final_submission.evidence is required when state is submitted")
        return
    if state != "submitted" and evidence is not None:
        errors.append("portal.final_submission.evidence must be null unless state is submitted")
    if evidence is None:
        return
    if not isinstance(evidence, dict):
        errors.append("portal.final_submission.evidence must be an object or null")
        return
    source = evidence.get("source")
    if source not in tuple(SUBMISSION_EVIDENCE_SOURCES):
        errors.append("portal.final_submission.evidence.source is invalid")
    if not valid_timestamp(evidence.get("recorded_at")):
        errors.append("portal.final_submission.evidence.recorded_at must be a UTC ISO 8601 timestamp")
    for field in ["manuscript_id", "receipt_reference"]:
        value = evidence.get(field, "")
        if not isinstance(value, str):
            errors.append(f"portal.final_submission.evidence.{field} must be a string")
    if source == "platform_receipt" and not any(
        isinstance(evidence.get(field), str) and evidence[field].strip()
        for field in ["manuscript_id", "receipt_reference"]
    ):
        errors.append("platform_receipt requires manuscript_id or receipt_reference")
    if source == "user_confirmation" and observation != "not_observed":
        errors.append("user_confirmation requires agent_observation not_observed")
    if source == "platform_receipt" and observation != "observed":
        errors.append("platform_receipt requires agent_observation observed")


def validate_display_items(data: dict[str, Any], errors: list[str]) -> None:
    policy = data.get("display_policy")
    items = data.get("display_items")
    if not isinstance(policy, dict):
        errors.append("display_policy must be an object")
        return
    if not isinstance(policy.get("separate_files_required"), bool):
        errors.append("display_policy.separate_files_required must be a boolean")
    if policy.get("numbering_policy") not in tuple(DISPLAY_NUMBERING_POLICIES):
        errors.append("display_policy.numbering_policy is invalid")
    if policy.get("main_manuscript_embeds") not in ("allowed", "forbidden"):
        errors.append("display_policy.main_manuscript_embeds must be allowed or forbidden")
    if not isinstance(policy.get("main_material_id"), str):
        errors.append("display_policy.main_material_id must be a string")
    if policy.get("separate_files_required") and policy.get("main_manuscript_embeds") != "forbidden":
        errors.append("separate_files_required requires main_manuscript_embeds forbidden")
    if not isinstance(items, list):
        errors.append("display_items must be an array")
        return

    material_ids = {
        item.get("id")
        for item in data.get("materials", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    numbers_by_kind: dict[str, list[int]] = {"figure": [], "table": []}
    numbers_global: list[int] = []
    for index, item in enumerate(items):
        prefix = f"display_items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        require_string(item, "id", errors)
        validate_status(item, prefix, errors)
        kind = item.get("kind")
        if kind not in tuple(DISPLAY_ITEM_KINDS):
            errors.append(f"{prefix}.kind is invalid")
            continue
        number = item.get("number")
        if type(number) is not int or number < 1:
            errors.append(f"{prefix}.number must be a positive integer")
        else:
            numbers_by_kind[kind].append(number)
            numbers_global.append(number)
        expected_reference = f"{kind.title()} {number}" if type(number) is int else ""
        if item.get("body_reference") != expected_reference:
            errors.append(f"{prefix}.body_reference must be {expected_reference!r}")
        material_id = item.get("material_id")
        if not isinstance(material_id, str) or material_id not in material_ids:
            errors.append(f"{prefix}.material_id must refer to a material")
        upload_order = item.get("upload_order")
        if type(upload_order) is not int or upload_order < 1:
            errors.append(f"{prefix}.upload_order must be a positive integer")
    for item_id in sorted(duplicate_ids(items)):
        errors.append(f"duplicate display_item id: {item_id}")
    if policy.get("numbering_policy") == "separate_sequences":
        for kind, numbers in numbers_by_kind.items():
            if sorted(numbers) != list(range(1, len(numbers) + 1)):
                errors.append(f"{kind} numbers must be consecutive from 1 under separate_sequences")
    elif policy.get("numbering_policy") == "global_sequence":
        if sorted(numbers_global) != list(range(1, len(numbers_global) + 1)):
            errors.append("display item numbers must be consecutive from 1 under global_sequence")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_docx_snapshot(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".docx":
        raise ValueError(f"main manuscript must be a .docx file for embedded-display preflight: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.getinfo("word/document.xml").file_size > 32 * 1024 * 1024:
                raise ValueError("DOCX main document exceeds the 32 MiB XML limit")
            document = archive.read("word/document.xml")
            file_names = archive.namelist()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"cannot read DOCX main manuscript: {path}: {exc}") from exc
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise ValueError(f"invalid DOCX document XML: {exc}") from exc
    # Word may split one word across formatting runs; preserve paragraph boundaries.
    text = "\n".join("".join(node.text or "" for node in paragraph.iter(f"{{{WORD_NAMESPACE}}}t"))
                     for paragraph in root.iter(f"{{{WORD_NAMESPACE}}}p"))
    labels = {
        (kind.lower(), int(number))
        for kind, number in DISPLAY_LABEL_RE.findall(text)
    }
    drawings = len(root.findall(f".//{{{WORD_NAMESPACE}}}drawing"))
    drawings += len(root.findall(f".//{{{WORD_NAMESPACE}}}object"))
    drawings += len(root.findall(f".//{{{WORD_NAMESPACE}}}pict"))
    drawings += len(root.findall(f".//{{{DRAWING_NAMESPACE}}}blip"))
    return {
        "labels": labels,
        "tables": len(root.findall(f".//{{{WORD_NAMESPACE}}}tbl")),
        "drawings": drawings,
        "embedded_media": len([name for name in file_names if name.startswith("word/media/")]),
    }


def display_preflight(data: dict[str, Any], base_dir: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    errors = validate(data)
    if errors:
        return errors, {}
    if data["schema_version"] != SCHEMA_VERSION:
        return ["preflight-display-items requires a v2 submission packet"], {}
    policy = data["display_policy"]
    if not policy["separate_files_required"]:
        return ["preflight-display-items requires display_policy.separate_files_required true"], {}
    material_by_id = {
        material["id"]: material
        for material in data["materials"]
        if isinstance(material, dict) and isinstance(material.get("id"), str)
    }
    main_material = material_by_id.get(policy["main_material_id"])
    if main_material is None:
        return ["display_policy.main_material_id must refer to the main manuscript material"], {}
    main_path_value = main_material.get("path")
    if not isinstance(main_path_value, str) or not main_path_value:
        return ["main manuscript material requires a non-empty path"], {}
    base_dir = base_dir or Path.cwd()
    main_path = (base_dir / main_path_value).resolve()
    if not main_path.is_file():
        return [f"main manuscript file does not exist: {main_path}"], {}
    try:
        snapshot = read_docx_snapshot(main_path)
    except ValueError as exc:
        return [str(exc)], {}

    expected_labels = {(item["kind"], item["number"]) for item in data["display_items"]}
    reported: dict[str, Any] = {
        "main_manuscript": {
            "path": str(main_path),
            "sha256": sha256(main_path),
            "tables": snapshot["tables"],
            "drawings": snapshot["drawings"],
            "embedded_media": snapshot["embedded_media"],
            "display_labels": [f"{kind.title()} {number}" for kind, number in sorted(snapshot["labels"])],
        },
        "standalone_files": [],
    }
    preflight_errors: list[str] = []
    if main_material.get("status") != "confirmed":
        preflight_errors.append("main manuscript material must be confirmed")
    declared_main_hash = main_material.get("sha256")
    if declared_main_hash and declared_main_hash != reported["main_manuscript"]["sha256"]:
        preflight_errors.append("main manuscript file hash does not match packet")
    used_paths = {main_path}
    main_stat = main_path.stat()
    used_identities = {(main_stat.st_dev, main_stat.st_ino)}
    if policy["main_manuscript_embeds"] == "forbidden":
        for name in ["tables", "drawings", "embedded_media"]:
            if snapshot[name]:
                preflight_errors.append(f"main manuscript contains {snapshot[name]} embedded {name}")
    missing_labels = expected_labels - snapshot["labels"]
    unexpected_labels = snapshot["labels"] - expected_labels
    if missing_labels:
        preflight_errors.append("main manuscript is missing display references: " + ", ".join(f"{kind.title()} {number}" for kind, number in sorted(missing_labels)))
    if unexpected_labels:
        preflight_errors.append("main manuscript has unregistered display references: " + ", ".join(f"{kind.title()} {number}" for kind, number in sorted(unexpected_labels)))
    upload_orders: list[int] = []
    for item in data["display_items"]:
        material = material_by_id[item["material_id"]]
        file_path_value = material.get("path")
        if not isinstance(file_path_value, str) or not file_path_value:
            preflight_errors.append(f"{item['id']} material requires a non-empty path")
            continue
        if item.get("status") != "confirmed" or material.get("status") != "confirmed":
            preflight_errors.append(f"{item['id']} display item and material must be confirmed")
        file_path = (base_dir / file_path_value).resolve()
        if file_path in used_paths:
            preflight_errors.append(f"{item['id']} requires a distinct standalone file")
        used_paths.add(file_path)
        if not file_path.is_file():
            preflight_errors.append(f"{item['id']} standalone file does not exist: {file_path}")
            continue
        file_stat = file_path.stat()
        identity = (file_stat.st_dev, file_stat.st_ino)
        if identity in used_identities and file_path != main_path:
            preflight_errors.append(f"{item['id']} requires a distinct standalone file, not a hard link")
        used_identities.add(identity)
        actual_hash = sha256(file_path)
        declared_hash = material.get("sha256", "")
        if declared_hash and declared_hash != actual_hash:
            preflight_errors.append(f"{item['id']} standalone file hash does not match packet")
        reported["standalone_files"].append({
            "id": item["id"],
            "body_reference": item["body_reference"],
            "path": str(file_path),
            "sha256": actual_hash,
            "upload_order": item["upload_order"],
        })
        upload_orders.append(item["upload_order"])
    if len(upload_orders) != len(set(upload_orders)):
        preflight_errors.append("display item upload_order values must be unique")
    return preflight_errors, reported


def validate_proof(portal: dict[str, Any], errors: list[str]) -> None:
    proof = portal.get("proof")
    if not isinstance(proof, dict):
        errors.append("portal.proof must be an object")
        return
    if proof.get("state") not in tuple(PROOF_STATES):
        errors.append("portal.proof.state is invalid")
    if proof.get("text_check") not in tuple(PROOF_TEXT_CHECKS):
        errors.append("portal.proof.text_check is invalid")
    if proof.get("visual_check") not in tuple(PROOF_VISUAL_CHECKS):
        errors.append("portal.proof.visual_check is invalid")
    if proof.get("agent_observation") not in tuple(AGENT_OBSERVATIONS):
        errors.append("portal.proof.agent_observation is invalid")
    if not isinstance(proof.get("checked_at"), str):
        errors.append("portal.proof.checked_at must be a string")
    if not isinstance(proof.get("evidence_source"), str):
        errors.append("portal.proof.evidence_source must be a string")
    if proof.get("checked_at") and not valid_timestamp(proof.get("checked_at")):
        errors.append("portal.proof.checked_at must be a UTC ISO 8601 timestamp")
    if proof.get("state") == "not_generated" and (
        proof.get("text_check") != "not_run" or proof.get("visual_check") != "not_run"
    ):
        errors.append("not_generated proof cannot contain completed checks")
    if proof.get("state") == "reviewed" and (
        proof.get("text_check") not in ("passed", "not_available")
        or proof.get("visual_check") not in ("human_confirmed", "agent_verified")
    ):
        errors.append("reviewed proof requires a successful text check (or not_available) and verified visual check")
    if proof.get("visual_check") in ("human_confirmed", "agent_verified"):
        if proof.get("state") not in ("opened", "reviewed"):
            errors.append("verified visual check requires opened or reviewed proof")
        if not valid_timestamp(proof.get("checked_at")):
            errors.append("verified visual check requires a UTC checked_at timestamp")
        if not isinstance(proof.get("evidence_source"), str) or not proof["evidence_source"].strip():
            errors.append("verified visual check requires evidence_source")
    if proof.get("visual_check") == "agent_verified" and proof.get("agent_observation") != "observed":
        errors.append("agent_verified proof requires agent_observation observed")
    if proof.get("visual_check") == "human_confirmed" and proof.get("agent_observation") != "not_observed":
        errors.append("human_confirmed proof requires agent_observation not_observed")


def validate_return_events(portal: dict[str, Any], errors: list[str]) -> None:
    events = portal.get("return_events")
    if not isinstance(events, list):
        errors.append("portal.return_events must be an array")
        return
    for index, event in enumerate(events):
        prefix = f"portal.return_events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be an object")
            continue
        require_string(event, "id", errors)
        if event.get("state") not in tuple(RETURN_EVENT_STATES):
            errors.append(f"{prefix}.state is invalid")
        require_string(event, "reason", errors)
        if not valid_timestamp(event.get("returned_at")):
            errors.append(f"{prefix}.returned_at must be a UTC ISO 8601 timestamp")
        for field in ["resolved_at", "resolution", "evidence"]:
            if not isinstance(event.get(field, ""), str):
                errors.append(f"{prefix}.{field} must be a string")
        if event.get("state") == "returned" and (event.get("resolved_at") or event.get("resolution")):
            errors.append(f"{prefix}.returned event must not contain resolution fields")
        if event.get("state") == "resolved":
            require_string(event, "evidence", errors)
            if not valid_timestamp(event.get("resolved_at")):
                errors.append(f"{prefix}.resolved_at must be a UTC ISO 8601 timestamp")
            elif valid_timestamp(event.get("returned_at")) and datetime.fromisoformat(event["resolved_at"].replace("Z", "+00:00")) < datetime.fromisoformat(event["returned_at"].replace("Z", "+00:00")):
                errors.append(f"{prefix}.resolved_at precedes returned_at")
            require_string(event, "resolution", errors)
    for event_id in sorted(duplicate_ids(events)):
        errors.append(f"duplicate return_event id: {event_id}")


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["submission packet root must be an object"]
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError):
        return ["state must contain only finite JSON-compatible values"]
    required = [
        "schema_version", "submission_id", "created_at", "updated_at", "manuscript", "target",
        "materials", "authors", "declarations", "reviewers", "portal", "gaps", "audit_log",
    ]
    for field in required:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    schema_version = data["schema_version"]
    if schema_version not in (LEGACY_SCHEMA_VERSION, SCHEMA_VERSION):
        errors.append(f"schema_version must be {LEGACY_SCHEMA_VERSION} or {SCHEMA_VERSION}")
    require_string(data, "submission_id", errors)
    for field in ["created_at", "updated_at"]:
        if not valid_timestamp(data.get(field)):
            errors.append(f"{field} must be a UTC ISO 8601 timestamp")
    for field in ["manuscript", "target", "portal"]:
        if not isinstance(data[field], dict):
            errors.append(f"{field} must be an object")
    for field in ["materials", "authors", "declarations", "reviewers", "gaps", "audit_log"]:
        if not isinstance(data[field], list):
            errors.append(f"{field} must be an array")
    if errors:
        return errors

    for index, entry in enumerate(data["audit_log"]):
        if not isinstance(entry, dict):
            errors.append(f"audit_log[{index}] must be an object")
            continue
        for field in ["action", "target_id"]:
            require_string(entry, field, errors)
        if not valid_timestamp(entry.get("at")):
            errors.append(f"audit_log[{index}].at must be a UTC ISO 8601 timestamp")
    for index, material in enumerate(data["materials"]):
        if isinstance(material, dict) and material.get("sha256") is not None:
            if not isinstance(material["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", material["sha256"]):
                errors.append(f"materials[{index}].sha256 must be a lowercase SHA-256 digest")
    manuscript = data["manuscript"]
    target = data["target"]
    require_string(manuscript, "title", errors)
    require_string(target, "journal", errors)
    require_string(target, "platform", errors)

    for collection in ["materials", "authors", "declarations", "reviewers", "gaps"]:
        for index, item in enumerate(data[collection]):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            require_string(item, "id", errors)
            validate_status(item, prefix, errors)
        for item_id in sorted(duplicate_ids(data[collection])):
            errors.append(f"duplicate {collection[:-1]} id: {item_id}")

    for index, author in enumerate(data["authors"]):
        if not isinstance(author, dict):
            continue
        prefix = f"authors[{index}]"
        require_string(author, "name", errors)
        for field in ["email", "corresponding_author", "credit_roles"]:
            value = author.get(field)
            if not isinstance(value, dict):
                errors.append(f"{prefix}.{field} must be an object with value and status")
            elif value.get("status") not in tuple(FIELD_STATUSES):
                errors.append(f"{prefix}.{field}.status is invalid")
            elif "value" not in value:
                errors.append(f"{prefix}.{field}.value is required")
            elif value.get("status") == "confirmed":
                actual = value["value"]
                valid = (isinstance(actual, str) and bool(actual.strip())) if field == "email" else (
                    isinstance(actual, bool) if field == "corresponding_author" else
                    isinstance(actual, list) and bool(actual) and all(isinstance(role, str) and role.strip() for role in actual)
                )
                if not valid:
                    errors.append(f"{prefix}.{field}.confirmed value has the wrong type or is empty")

    portal = data["portal"]
    if schema_version == SCHEMA_VERSION and not isinstance(portal.get("final_submission"), dict):
        errors.append("v2 portal.final_submission is required")
    validate_final_submission(portal, errors)
    steps = portal.get("steps")
    if not isinstance(steps, list):
        errors.append("portal.steps must be an array")
    else:
        for index, step in enumerate(steps):
            prefix = f"portal.steps[{index}]"
            if not isinstance(step, dict):
                errors.append(f"{prefix} must be an object")
                continue
            require_string(step, "name", errors)
            if step.get("status") not in tuple(PORTAL_STEP_STATUSES):
                errors.append(f"{prefix}.status is invalid")
            if step.get("status") == "complete" and step.get("errors"):
                errors.append(f"{prefix}.complete step must not retain errors")
            if "errors" in step and (not isinstance(step["errors"], list) or not all(isinstance(value, str) for value in step["errors"])):
                errors.append(f"{prefix}.errors must be an array of strings")
        names = [step.get("name") for step in steps if isinstance(step, dict) and isinstance(step.get("name"), str)]
        if len(names) != len(set(names)):
            errors.append("portal.steps contains duplicate names")
    if schema_version == SCHEMA_VERSION:
        validate_display_items(data, errors)
        validate_proof(portal, errors)
        validate_return_events(portal, errors)
    return errors


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"refusing to overwrite existing file: {path}")
        return 2
    timestamp = now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "submission_id": args.submission_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "manuscript": {"title": args.title, "article_type": args.article_type, "version": args.version},
        "target": {"journal": args.journal, "platform": args.platform, "requirements_checked_at": ""},
        "materials": [], "authors": [], "declarations": [], "reviewers": [],
        "display_policy": default_display_policy(),
        "display_items": [],
        "portal": {
            "system": args.platform,
            "journal_url": "",
            "draft_id": "",
            "checked_at": "",
            "steps": [],
            "proof": default_proof(),
            "return_events": [],
            "final_submission": default_final_submission(),
        },
        "gaps": [],
        "audit_log": [{"at": timestamp, "action": "submission_packet_initialized", "target_id": args.submission_id}],
    }
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"created {path}")
    return 0


def command_record_portal_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    timestamp = now()
    portal = data["portal"]
    previous_portal = copy.deepcopy(portal)
    portal["system"] = args.system
    portal["checked_at"] = timestamp
    if args.journal_url:
        portal["journal_url"] = args.journal_url
    if args.draft_id:
        portal["draft_id"] = args.draft_id
    step = {"name": args.step, "status": args.status, "errors": args.error or []}
    portal["steps"] = [item for item in portal["steps"] if item.get("name") != args.step]
    portal["steps"].append(step)
    data["updated_at"] = timestamp
    data["audit_log"].append({"at": timestamp, "action": "portal_checked", "target_id": args.step, "status": args.status, "previous": previous_portal})
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded {args.step}")
    return 0


def command_record_proof_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    if data["schema_version"] != SCHEMA_VERSION:
        print("record-proof-check requires a v2 submission packet")
        return 2
    if args.visual_check == "human_confirmed" and args.agent_observation != "not_observed":
        print("human_confirmed proof requires --agent-observation not_observed")
        return 2
    timestamp = args.checked_at or now()
    previous_proof = copy.deepcopy(data["portal"]["proof"])
    data["portal"]["proof"] = {
        "state": args.state,
        "text_check": args.text_check,
        "visual_check": args.visual_check,
        "checked_at": timestamp,
        "evidence_source": args.evidence_source or "",
        "agent_observation": args.agent_observation,
    }
    data["updated_at"] = timestamp
    data["audit_log"].append({
        "at": timestamp,
        "action": "proof_check_recorded",
        "previous": previous_proof,
        "target_id": data["submission_id"],
        "status": args.visual_check,
        "agent_observation": args.agent_observation,
    })
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded proof check: {args.visual_check}")
    return 0


def command_record_return(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    if data["schema_version"] != SCHEMA_VERSION:
        print("record-return requires a v2 submission packet")
        return 2
    timestamp = args.recorded_at or now()
    events = data["portal"]["return_events"]
    existing = next((event for event in events if event.get("id") == args.return_id), None)
    previous_event = copy.deepcopy(existing)
    if args.state == "returned":
        if existing is not None:
            print(f"return event already exists: {args.return_id}")
            return 2
        if not args.reason:
            print("returned requires --reason")
            return 2
        event = {
            "id": args.return_id,
            "state": "returned",
            "reason": args.reason,
            "returned_at": timestamp,
            "resolved_at": "",
            "resolution": "",
            "evidence": args.evidence or "",
        }
        events.append(event)
    else:
        if existing is None:
            print(f"return event not found: {args.return_id}")
            return 2
        if existing["state"] == "resolved":
            print("resolved return events are immutable; record a new return event")
            return 2
        if not args.resolution:
            print("resolved requires --resolution")
            return 2
        if not args.evidence or not args.evidence.strip():
            print("resolved requires --evidence for the saved correction")
            return 2
        existing["state"] = "resolved"
        existing["resolved_at"] = timestamp
        existing["resolution"] = args.resolution
        existing["evidence"] = args.evidence or existing.get("evidence", "")
    data["updated_at"] = timestamp
    data["audit_log"].append({
        "at": timestamp,
        "action": "return_event_recorded",
        "previous": previous_event,
        "target_id": args.return_id,
        "status": args.state,
    })
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded return event: {args.return_id} {args.state}")
    return 0


def command_record_submission_result(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = load(path)
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    if args.state == "submitted" and not args.evidence_source:
        print("submitted requires --evidence-source")
        return 2
    if args.evidence_source and args.state != "submitted":
        print("--evidence-source is only valid when state is submitted")
        return 2
    if args.evidence_source == "user_confirmation" and args.agent_observation != "not_observed":
        print("user_confirmation requires --agent-observation not_observed")
        return 2
    if args.evidence_source == "platform_receipt" and args.agent_observation != "observed":
        print("platform_receipt requires --agent-observation observed")
        return 2
    timestamp = args.recorded_at or now()
    evidence = None
    if args.evidence_source:
        evidence = {
            "source": args.evidence_source,
            "recorded_at": timestamp,
            "manuscript_id": args.manuscript_id or "",
            "receipt_reference": args.receipt_reference or "",
        }
    final_submission = {
        "state": args.state,
        "evidence": evidence,
        "agent_observation": args.agent_observation,
    }
    previous_result = copy.deepcopy(data["portal"].get("final_submission"))
    data["portal"]["final_submission"] = final_submission
    data["updated_at"] = timestamp
    data["audit_log"].append({
        "at": timestamp,
        "action": "submission_result_recorded",
        "previous": previous_result,
        "target_id": data["submission_id"],
        "status": args.state,
        "evidence_source": args.evidence_source or "",
        "agent_observation": args.agent_observation,
    })
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded submission result: {args.state}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        errors = validate(load(Path(args.path)))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid submission packet: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print("submission packet valid")
    return 0


def command_preflight_display_items(args: argparse.Namespace) -> int:
    try:
        errors, report = display_preflight(load(Path(args.path)), Path(args.path).resolve().parent)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"invalid submission packet: {exc}")
        return 2
    if errors:
        print("\n".join(errors))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_summary(args: argparse.Namespace) -> int:
    data = load(Path(args.path))
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    result = {
        "submission_id": data["submission_id"],
        "journal": data["target"]["journal"],
        "materials": len(data["materials"]),
        "authors": len(data["authors"]),
        "reviewers": len(data["reviewers"]),
        "gaps": len(data["gaps"]),
        "incomplete_portal_steps": [step["name"] for step in data["portal"]["steps"] if step["status"] == "incomplete"],
        "proof": data["portal"].get("proof", {}),
        "return_events": data["portal"].get("return_events", []),
        "final_submission": data["portal"].get("final_submission", default_final_submission()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("path")
    init.add_argument("--submission-id", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--journal", required=True)
    init.add_argument("--platform", required=True)
    init.add_argument("--article-type", default="")
    init.add_argument("--version", default="")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)
    portal = commands.add_parser("record-portal-check")
    portal.add_argument("path")
    portal.add_argument("--system", required=True)
    portal.add_argument("--step", required=True)
    portal.add_argument("--status", required=True, choices=sorted(PORTAL_STEP_STATUSES))
    portal.add_argument("--error", action="append")
    portal.add_argument("--journal-url")
    portal.add_argument("--draft-id")
    portal.set_defaults(func=command_record_portal_check)
    proof = commands.add_parser("record-proof-check")
    proof.add_argument("path")
    proof.add_argument("--state", required=True, choices=sorted(PROOF_STATES))
    proof.add_argument("--text-check", required=True, choices=sorted(PROOF_TEXT_CHECKS))
    proof.add_argument("--visual-check", required=True, choices=sorted(PROOF_VISUAL_CHECKS))
    proof.add_argument("--agent-observation", required=True, choices=sorted(AGENT_OBSERVATIONS))
    proof.add_argument("--evidence-source")
    proof.add_argument("--checked-at")
    proof.set_defaults(func=command_record_proof_check)
    returned = commands.add_parser("record-return")
    returned.add_argument("path")
    returned.add_argument("--return-id", required=True)
    returned.add_argument("--state", required=True, choices=sorted(RETURN_EVENT_STATES))
    returned.add_argument("--reason")
    returned.add_argument("--resolution")
    returned.add_argument("--evidence")
    returned.add_argument("--recorded-at")
    returned.set_defaults(func=command_record_return)
    submission_result = commands.add_parser("record-submission-result")
    submission_result.add_argument("path")
    submission_result.add_argument("--state", required=True, choices=sorted(FINAL_SUBMISSION_STATES))
    submission_result.add_argument("--evidence-source", choices=sorted(SUBMISSION_EVIDENCE_SOURCES))
    submission_result.add_argument("--agent-observation", required=True, choices=sorted(AGENT_OBSERVATIONS))
    submission_result.add_argument("--recorded-at")
    submission_result.add_argument("--manuscript-id")
    submission_result.add_argument("--receipt-reference")
    submission_result.set_defaults(func=command_record_submission_result)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=command_validate)
    preflight = commands.add_parser("preflight-display-items")
    preflight.add_argument("path")
    preflight.set_defaults(func=command_preflight_display_items)
    summary = commands.add_parser("summary")
    summary.add_argument("path")
    summary.set_defaults(func=command_summary)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init" or args.command.startswith("record-"):
            path = Path(args.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with exclusive_lock(path.with_name(path.name + ".lock")):
                return args.func(args)
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"invalid submission packet: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
