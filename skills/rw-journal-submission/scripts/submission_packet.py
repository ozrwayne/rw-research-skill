#!/usr/bin/env python3
"""Create, validate, and record on-device submission packets."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rw-journal-submission/submission-packet/v1"
FIELD_STATUSES = {"confirmed", "missing", "needs_author_confirmation", "not_applicable"}
PORTAL_STEP_STATUSES = {"complete", "incomplete", "unverified"}
FINAL_SUBMISSION_STATES = {"not_submitted", "awaiting_human_submit", "submitted", "unverified"}
SUBMISSION_EVIDENCE_SOURCES = {"user_confirmation", "platform_receipt"}
AGENT_OBSERVATIONS = {"not_observed", "observed"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("submission packet root must be an object")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


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
    if status not in FIELD_STATUSES:
        errors.append(f"{prefix}.status must be one of: {', '.join(sorted(FIELD_STATUSES))}")


def default_final_submission() -> dict[str, Any]:
    return {"state": "not_submitted", "evidence": None, "agent_observation": "not_observed"}


def validate_final_submission(portal: dict[str, Any], errors: list[str]) -> None:
    final_submission = portal.get("final_submission")
    if final_submission is None:
        return
    if not isinstance(final_submission, dict):
        errors.append("portal.final_submission must be an object")
        return
    state = final_submission.get("state")
    if state not in FINAL_SUBMISSION_STATES:
        errors.append("portal.final_submission.state is invalid")
    observation = final_submission.get("agent_observation")
    if observation not in AGENT_OBSERVATIONS:
        errors.append("portal.final_submission.agent_observation is invalid")
    evidence = final_submission.get("evidence")
    if state == "submitted" and not isinstance(evidence, dict):
        errors.append("portal.final_submission.evidence is required when state is submitted")
        return
    if evidence is None:
        return
    if not isinstance(evidence, dict):
        errors.append("portal.final_submission.evidence must be an object or null")
        return
    source = evidence.get("source")
    if source not in SUBMISSION_EVIDENCE_SOURCES:
        errors.append("portal.final_submission.evidence.source is invalid")
    require_string(evidence, "recorded_at", errors)
    for field in ["manuscript_id", "receipt_reference"]:
        value = evidence.get(field, "")
        if not isinstance(value, str):
            errors.append(f"portal.final_submission.evidence.{field} must be a string")
    if source == "user_confirmation" and observation != "not_observed":
        errors.append("user_confirmation requires agent_observation not_observed")
    if source == "platform_receipt" and observation != "observed":
        errors.append("platform_receipt requires agent_observation observed")


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version", "submission_id", "created_at", "updated_at", "manuscript", "target",
        "materials", "authors", "declarations", "reviewers", "portal", "gaps", "audit_log",
    ]
    for field in required:
        if field not in data:
            errors.append(f"missing top-level field: {field}")
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    require_string(data, "submission_id", errors)
    for field in ["manuscript", "target", "portal"]:
        if not isinstance(data[field], dict):
            errors.append(f"{field} must be an object")
    for field in ["materials", "authors", "declarations", "reviewers", "gaps", "audit_log"]:
        if not isinstance(data[field], list):
            errors.append(f"{field} must be an array")
    if errors:
        return errors

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
            elif value.get("status") not in FIELD_STATUSES:
                errors.append(f"{prefix}.{field}.status is invalid")

    portal = data["portal"]
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
            if step.get("status") not in PORTAL_STEP_STATUSES:
                errors.append(f"{prefix}.status is invalid")
            if "errors" in step and (not isinstance(step["errors"], list) or not all(isinstance(value, str) for value in step["errors"])):
                errors.append(f"{prefix}.errors must be an array of strings")
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
        "portal": {
            "system": args.platform,
            "journal_url": "",
            "draft_id": "",
            "checked_at": "",
            "steps": [],
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
    data["audit_log"].append({"at": timestamp, "action": "portal_checked", "target_id": args.step, "status": args.status})
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 2
    atomic_write(path, data)
    print(f"recorded {args.step}")
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
    data["portal"]["final_submission"] = final_submission
    data["updated_at"] = timestamp
    data["audit_log"].append({
        "at": timestamp,
        "action": "submission_result_recorded",
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
    summary = commands.add_parser("summary")
    summary.add_argument("path")
    summary.set_defaults(func=command_summary)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
