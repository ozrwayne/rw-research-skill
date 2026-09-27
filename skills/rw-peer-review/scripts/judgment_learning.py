#!/usr/bin/env python3
"""Create and validate RW Peer Review judgment-learning sidecar files."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rw-peer-review-judgment-learning/v1"
MODES = {"guided", "full", "abbreviated", "off"}
CONFIDENCE = {"high", "medium", "low", "unknown"}
CHALLENGE_TARGETS = {"data", "measurement", "analysis", "estimand", "reporting", "interpretation"}
VERIFICATION_STATES = {"verified", "not_verified", "not_applicable"}
RESPONSE_STATES = {"yes", "partial", "no", "unclear"}
DISPOSITIONS = {"sustained", "narrowed", "withdrawn", "answered", "deferred", "needs_input"}
TRANSFER_STATES = {"not_run", "passed", "needs_practice"}
CLEANLINESS_STATES = {"not_run", "passed", "failed"}
EXPERIENCE_STATES = {"none", "some", "experienced", "unknown"}
BASELINE_STATES = {"not_run", "completed"}
COMPETENCY_STATES = {"pass", "needs_work", "not_checked"}
CASE_ASSESSMENT_STATES = {"pass", "needs_work"}
MASTERY_DECISIONS = {"not_assessed", "needs_practice", "meets_predeclared_standard"}
GUIDED_CARD_FIELDS = {
    "claim", "evidence_location", "study_design", "research_object",
    "estimand_or_target_effect", "issue_type", "publication_impact",
    "proposed_fix", "change_evidence",
}
QUALITY_FIELDS = {
    "research_question_importance", "originality", "method_strengths_weaknesses",
    "presentation_reporting", "interpretation", "constructiveness", "substantiation",
}
VERIFICATION_FIELDS = {
    "main_text", "supplement", "author_explanation", "statistical_principle",
    "research_object_and_estimand",
}
RESPONSE_FIELDS = {
    "response_mentioned", "response_hits_issue", "response_is_sufficient",
    "body_still_needs_reporting",
}


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
        raise ValueError("judgment-learning root must be an object")
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


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not all(is_non_empty_string(item) for item in value):
        errors.append(f"{field} must be an array of non-empty strings")


def require_object(data: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


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
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for field in ["review_id", "finding_id", "updated_at"]:
        if not is_non_empty_string(data.get(field)):
            errors.append(f"{field} must be a non-empty string")
    if data.get("mode") not in MODES:
        errors.append("mode is invalid")

    novice = require_object(data, "novice_support", errors)
    if novice.get("experience_declared") not in EXPERIENCE_STATES:
        errors.append("novice_support.experience_declared is invalid")
    baseline = require_object(novice, "baseline_case", errors)
    for field in ["case_id", "user_answer"]:
        if field not in baseline or not isinstance(baseline.get(field), str):
            errors.append(f"novice_support.baseline_case.{field} must be a string")
    if baseline.get("status") not in BASELINE_STATES:
        errors.append("novice_support.baseline_case.status is invalid")
    worked = require_object(novice, "worked_example", errors)
    if "case_id" not in worked or not isinstance(worked.get("case_id"), str):
        errors.append("novice_support.worked_example.case_id must be a string")
    if not isinstance(worked.get("completed"), bool):
        errors.append("novice_support.worked_example.completed must be boolean")
    card = require_object(novice, "guided_review_card", errors)
    for field in sorted(GUIDED_CARD_FIELDS):
        if field not in card or not isinstance(card.get(field), str):
            errors.append(f"novice_support.guided_review_card.{field} must be a string")
    feedback = require_object(novice, "feedback", errors)
    for field in ["missed_evidence", "overreach", "severity_notes", "next_practice"]:
        if field not in feedback or not isinstance(feedback.get(field), list) or not all(
            isinstance(item, str) for item in feedback.get(field, [])
        ):
            errors.append(f"novice_support.feedback.{field} must be an array of strings")
    quality = require_object(novice, "review_quality_check", errors)
    for field in sorted(QUALITY_FIELDS):
        if quality.get(field) not in COMPETENCY_STATES:
            errors.append(f"novice_support.review_quality_check.{field} is invalid")
    if not isinstance(novice.get("critical_miss"), bool):
        errors.append("novice_support.critical_miss must be boolean")
    standard = require_object(novice, "assessment_standard", errors)
    for field in ["name", "source"]:
        if field not in standard or not isinstance(standard.get(field), str):
            errors.append(f"novice_support.assessment_standard.{field} must be a string")
    required_cases = standard.get("required_independent_cases")
    if not isinstance(required_cases, int) or isinstance(required_cases, bool) or required_cases < 0:
        errors.append("novice_support.assessment_standard.required_independent_cases must be a non-negative integer")
    case_records = novice.get("independent_case_records")
    if not isinstance(case_records, list):
        errors.append("novice_support.independent_case_records must be an array")
    else:
        case_ids = [record.get("case_id") for record in case_records if isinstance(record, dict) and isinstance(record.get("case_id"), str)]
        if len(case_ids) != len(set(case_ids)):
            errors.append("novice_support.independent_case_records contains duplicate case_id")
        for index, record in enumerate(case_records):
            prefix = f"novice_support.independent_case_records[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ["case_id", "study_type", "problem_type", "assessed_by"]:
                if not is_non_empty_string(record.get(field)):
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if record.get("status") not in CASE_ASSESSMENT_STATES:
                errors.append(f"{prefix}.status is invalid")
    if "assessed_by" not in novice or not isinstance(novice.get("assessed_by"), str):
        errors.append("novice_support.assessed_by must be a string")
    if novice.get("mastery_decision") not in MASTERY_DECISIONS:
        errors.append("novice_support.mastery_decision is invalid")

    issue = require_object(data, "machine_issue_map", errors)
    for field in ["claim", "research_object", "estimand_or_target_effect"]:
        if field not in issue or not isinstance(issue.get(field), str):
            errors.append(f"machine_issue_map.{field} must be a string")
    for field in ["evidence_locations", "unknowns"]:
        if field not in issue:
            errors.append(f"machine_issue_map missing field: {field}")
        elif not isinstance(issue[field], list) or not all(isinstance(item, str) for item in issue[field]):
            errors.append(f"machine_issue_map.{field} must be an array of strings")

    initial = require_object(data, "user_initial_judgment", errors)
    if "statement" not in initial or not isinstance(initial.get("statement"), str):
        errors.append("user_initial_judgment.statement must be a string")
    for field in ["basis", "uncertainties"]:
        if field not in initial or not isinstance(initial.get(field), list) or not all(
            isinstance(item, str) for item in initial.get(field, [])
        ):
            errors.append(f"user_initial_judgment.{field} must be an array of strings")
    if initial.get("confidence") not in CONFIDENCE:
        errors.append("user_initial_judgment.confidence is invalid")

    challenge = require_object(data, "strongest_challenge", errors)
    if "statement" not in challenge or not isinstance(challenge.get("statement"), str):
        errors.append("strongest_challenge.statement must be a string")
    if challenge.get("target") not in CHALLENGE_TARGETS:
        errors.append("strongest_challenge.target is invalid")
    if "evidence" not in challenge or not isinstance(challenge.get("evidence"), list) or not all(
        isinstance(item, str) for item in challenge.get("evidence", [])
    ):
        errors.append("strongest_challenge.evidence must be an array of strings")

    response = require_object(data, "strongest_response", errors)
    if "statement" not in response or not isinstance(response.get("statement"), str):
        errors.append("strongest_response.statement must be a string")
    if "source" not in response or not isinstance(response.get("source"), list) or not all(
        isinstance(item, str) for item in response.get("source", [])
    ):
        errors.append("strongest_response.source must be an array of strings")
    if not isinstance(response.get("author_or_user_supplied"), bool):
        errors.append("strongest_response.author_or_user_supplied must be boolean")

    verification = require_object(data, "verification", errors)
    for field in sorted(VERIFICATION_FIELDS):
        if verification.get(field) not in VERIFICATION_STATES:
            errors.append(f"verification.{field} is invalid")
    for field in sorted(RESPONSE_FIELDS):
        if verification.get(field) not in RESPONSE_STATES:
            errors.append(f"verification.{field} is invalid")

    if "concepts_used" not in data:
        errors.append("missing field: concepts_used")
    elif not isinstance(data["concepts_used"], list) or not all(isinstance(item, str) for item in data["concepts_used"]):
        errors.append("concepts_used must be an array of strings")

    final = require_object(data, "user_final_judgment", errors)
    if "statement" not in final or not isinstance(final.get("statement"), str):
        errors.append("user_final_judgment.statement must be a string")
    if final.get("disposition") not in DISPOSITIONS:
        errors.append("user_final_judgment.disposition is invalid")
    if final.get("confidence") not in CONFIDENCE:
        errors.append("user_final_judgment.confidence is invalid")
    for field in ["basis", "remaining_uncertainties", "changed_by_evidence"]:
        if field not in final or not isinstance(final.get(field), list) or not all(
            isinstance(item, str) for item in final.get(field, [])
        ):
            errors.append(f"user_final_judgment.{field} must be an array of strings")

    transfer = require_object(data, "transfer_check", errors)
    for field in ["case_id", "user_answer", "feedback"]:
        if field not in transfer or not isinstance(transfer.get(field), str):
            errors.append(f"transfer_check.{field} must be a string")
    if transfer.get("status") not in TRANSFER_STATES:
        errors.append("transfer_check.status is invalid")

    boundary = require_object(data, "delivery_boundary", errors)
    if not isinstance(boundary.get("internal_fields_excluded"), bool):
        errors.append("delivery_boundary.internal_fields_excluded must be boolean")
    if boundary.get("cleanliness_check") not in CLEANLINESS_STATES:
        errors.append("delivery_boundary.cleanliness_check is invalid")

    if (
        verification.get("response_is_sufficient") == "yes"
        and verification.get("body_still_needs_reporting") == "yes"
        and final.get("disposition") in {"answered", "withdrawn"}
    ):
        errors.append(
            "user_final_judgment.disposition cannot be answered or withdrawn when body_still_needs_reporting is yes"
        )
    return errors


def readiness(data: dict[str, Any], stage: str) -> tuple[str, list[str]]:
    errors = validate(data)
    if errors:
        return "BLOCK", errors
    if stage not in ("synthesis", "delivery"):
        return "BLOCK", ["invalid readiness stage"]
    if data["mode"] == "off":
        return "REVIEW", ["mode is off; judgment learning was explicitly skipped"]

    reasons: list[str] = []
    issue = data["machine_issue_map"]
    initial = data["user_initial_judgment"]
    challenge = data["strongest_challenge"]
    response = data["strongest_response"]
    verification = data["verification"]
    final = data["user_final_judgment"]

    if data["mode"] == "guided":
        novice = data["novice_support"]
        baseline = novice["baseline_case"]
        worked = novice["worked_example"]
        card = novice["guided_review_card"]
        if baseline["status"] != "completed" or not is_non_empty_string(baseline["user_answer"]):
            reasons.append("guided mode requires a completed baseline answer")
        if not worked["completed"] or not is_non_empty_string(worked["case_id"]):
            reasons.append("guided mode requires a completed worked example")
        if worked["case_id"] and worked["case_id"] == baseline["case_id"]:
            reasons.append("guided worked example must differ from baseline case")
        if data["finding_id"] in (worked["case_id"], baseline["case_id"]):
            reasons.append("guided examples must differ from the current finding")
        for field in sorted(GUIDED_CARD_FIELDS):
            if not is_non_empty_string(card[field]):
                reasons.append(f"novice_support.guided_review_card.{field} is empty")

    if not is_non_empty_string(issue["claim"]):
        reasons.append("machine_issue_map.claim is empty")
    if not issue["evidence_locations"]:
        reasons.append("machine_issue_map.evidence_locations is empty")
    if not is_non_empty_string(initial["statement"]):
        reasons.append("user_initial_judgment.statement is empty")
    if not initial["basis"]:
        reasons.append("user_initial_judgment.basis is empty")
    if not is_non_empty_string(challenge["statement"]):
        reasons.append("strongest_challenge.statement is empty")
    if not is_non_empty_string(response["statement"]):
        reasons.append("strongest_response.statement is empty")
    for field in sorted(VERIFICATION_FIELDS):
        if verification[field] == "not_verified":
            reasons.append(f"verification.{field} is not_verified")
    if not is_non_empty_string(final["statement"]):
        reasons.append("user_final_judgment.statement is empty")
    if not final["basis"]:
        reasons.append("user_final_judgment.basis is empty")
    if final["disposition"] == "needs_input":
        reasons.append("user_final_judgment.disposition is needs_input")

    if stage == "delivery":
        boundary = data["delivery_boundary"]
        if not boundary["internal_fields_excluded"]:
            reasons.append("delivery_boundary.internal_fields_excluded is false")
        if boundary["cleanliness_check"] != "passed":
            reasons.append("delivery_boundary.cleanliness_check is not passed")

    if reasons:
        return "BLOCK", reasons
    if data["transfer_check"]["status"] == "needs_practice":
        return "REVIEW", ["transfer_check.status is needs_practice"]
    return "PASS", []


def mastery(data: dict[str, Any]) -> tuple[str, list[str]]:
    errors = validate(data)
    if errors:
        return "BLOCK", errors
    if data["mode"] == "off":
        return "REVIEW", ["mode is off; mastery was not assessed"]
    novice = data["novice_support"]
    reasons: list[str] = []
    standard = novice["assessment_standard"]
    if not is_non_empty_string(standard["name"]):
        reasons.append("novice_support.assessment_standard.name is empty")
    if not is_non_empty_string(standard["source"]):
        reasons.append("novice_support.assessment_standard.source is empty")
    required_cases = standard["required_independent_cases"]
    if required_cases < 1:
        reasons.append("novice_support.assessment_standard.required_independent_cases is below 1")
    for field in sorted(QUALITY_FIELDS):
        if novice["review_quality_check"][field] != "pass":
            reasons.append(f"novice_support.review_quality_check.{field} is not pass")
    if novice["critical_miss"]:
        reasons.append("novice_support.critical_miss is true")
    passed_cases = sum(1 for item in novice["independent_case_records"] if item["status"] == "pass")
    if passed_cases < required_cases:
        reasons.append("novice_support.independent_case_records do not meet the predeclared requirement")
    if not is_non_empty_string(novice["assessed_by"]):
        reasons.append("novice_support.assessed_by is empty")
    if novice["mastery_decision"] != "meets_predeclared_standard":
        reasons.append("novice_support.mastery_decision is not meets_predeclared_standard")
    if reasons:
        return "REVIEW", reasons
    return "PASS", []


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"BLOCK: {path} already exists; use --force to replace")
        return 2
    template_path = Path(__file__).parents[1] / "assets" / "judgment-learning-template.json"
    data = json.loads(template_path.read_text(encoding="utf-8"))
    data["review_id"] = args.review_id
    data["finding_id"] = args.finding_id
    data["mode"] = args.mode
    data["updated_at"] = now()
    atomic_write(path, data)
    print(f"PASS: created {path}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    try:
        errors = validate(load(Path(args.path)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    if errors:
        print("BLOCK")
        for error in errors:
            print(f"- {error}")
        return 2
    print("PASS")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    try:
        data = load(Path(args.path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    errors = validate(data)
    if errors:
        print(json.dumps({"validation_errors": errors}, ensure_ascii=False))
        return 2
    payload = {
        "review_id": data.get("review_id"),
        "finding_id": data.get("finding_id"),
        "mode": data.get("mode"),
        "experience_declared": data.get("novice_support", {}).get("experience_declared"),
        "review_quality_check": data.get("novice_support", {}).get("review_quality_check"),
        "critical_miss": data.get("novice_support", {}).get("critical_miss"),
        "assessment_standard": data.get("novice_support", {}).get("assessment_standard"),
        "independent_case_records": data.get("novice_support", {}).get("independent_case_records"),
        "mastery_decision": data.get("novice_support", {}).get("mastery_decision"),
        "initial_recorded": bool(data.get("user_initial_judgment", {}).get("statement")),
        "verification": data.get("verification"),
        "final_disposition": data.get("user_final_judgment", {}).get("disposition"),
        "transfer_status": data.get("transfer_check", {}).get("status"),
        "cleanliness_check": data.get("delivery_boundary", {}).get("cleanliness_check"),
        "validation_errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if errors else 0


def command_ready(args: argparse.Namespace) -> int:
    try:
        status, reasons = readiness(load(Path(args.path)), args.stage)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    print(status)
    for reason in reasons:
        print(f"- {reason}")
    return {"PASS": 0, "REVIEW": 1, "BLOCK": 2}[status]


def command_mastery(args: argparse.Namespace) -> int:
    try:
        status, reasons = mastery(load(Path(args.path)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    print(status)
    for reason in reasons:
        print(f"- {reason}")
    return {"PASS": 0, "REVIEW": 1, "BLOCK": 2}[status]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("path")
    init_parser.add_argument("--review-id", required=True)
    init_parser.add_argument("--finding-id", required=True)
    init_parser.add_argument("--mode", choices=sorted(MODES), default="full")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=command_validate)

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("path")
    summary_parser.set_defaults(func=command_summary)

    ready_parser = subparsers.add_parser("ready")
    ready_parser.add_argument("path")
    ready_parser.add_argument("--stage", choices=["synthesis", "delivery"], default="synthesis")
    ready_parser.set_defaults(func=command_ready)

    mastery_parser = subparsers.add_parser("mastery")
    mastery_parser.add_argument("path")
    mastery_parser.set_defaults(func=command_mastery)
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
