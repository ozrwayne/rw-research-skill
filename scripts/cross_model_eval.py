#!/usr/bin/env python3
"""Run paired, deterministic cross-model evaluations for RW Research Skill."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


try:
    from .package_safety import safe_name, no_symlink
except ImportError:
    from package_safety import safe_name, no_symlink


ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals" / "cross-model"
DEFAULT_FIXTURES = EVAL_ROOT / "fixtures.json"
DEFAULT_MODELS = EVAL_ROOT / "models.json"
CONTEXT_FILES = {
    "rw-claim-audit": ["SKILL.md", "references/method.md", "references/axioms.md", "references/verdicts.md"],
    "rw-revision-patch": ["SKILL.md", "references/method.md", "references/axioms.md", "references/patch-format.md"],
    "rw-research-passport": ["SKILL.md", "references/method.md", "references/axioms.md", "references/schema.md"],
    "rw-research-router": ["SKILL.md", "references/method.md", "references/axioms.md", "references/domain-guide.md"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def command_version(command: str) -> str:
    try:
        result = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15, check=False)
        return (result.stdout or result.stderr).strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return "unavailable"


def provider_preflight(models: list[dict[str, Any]]) -> dict[str, Any]:
    providers = {model.get("provider") for model in models}
    checks: dict[str, Any] = {}
    failures: list[str] = []
    if "codex" in providers:
        binary = shutil.which("codex")
        auth_file = Path.home() / ".codex" / "auth.json"
        ready = bool(binary and auth_file.is_file())
        checks["codex"] = {"binary": binary or "unavailable", "auth_file_present": auth_file.is_file(), "ready": ready}
        if not ready:
            failures.append("Codex CLI or ~/.codex/auth.json is unavailable")
    if "claude" in providers:
        binary = shutil.which("claude")
        logged_in = False
        auth_method = "none"
        detail = ""
        if binary:
            try:
                result = subprocess.run(
                    [binary, "auth", "status"], capture_output=True, text=True, timeout=15, check=False
                )
                detail = (result.stdout or result.stderr).strip()
                status = json.loads(result.stdout) if result.stdout.strip() else {}
                logged_in = bool(status.get("loggedIn"))
                auth_method = str(status.get("authMethod", "none"))
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                detail = f"{type(exc).__name__}: {exc}"
        ready = bool(binary and logged_in)
        checks["claude"] = {
            "binary": binary or "unavailable",
            "logged_in": logged_in,
            "auth_method": auth_method,
            "ready": ready,
            "detail": sanitized_stderr(detail),
        }
        if not ready:
            failures.append("Claude CLI is not logged in; run `claude auth login` once with the Claude subscription")
    return {"checks": checks, "failures": failures}


def git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() or "unknown"


def git_dirty() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    return bool(result.stdout.strip())


def build_skill_context(skill_name: str) -> str:
    if skill_name not in CONTEXT_FILES:
        raise ValueError(f"no context file list for {skill_name}")
    skill = ROOT / "skills" / skill_name
    parts: list[str] = []
    for relative in CONTEXT_FILES[skill_name]:
        path = skill / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        parts.append(f"## {relative}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) + "\n"


def build_prompt(fixture: dict[str, Any], condition: str) -> tuple[str, str]:
    context = build_skill_context(fixture["skill"]) if condition == "with_skill" else ""
    context_block = (
        "<skill_context>\n"
        "Use these instructions for the task. They are public method instructions, not evidence about the fixture.\n\n"
        f"{context}</skill_context>\n\n"
        if context
        else "No Skill instructions are supplied. Solve the task using your general reasoning.\n\n"
    )
    schema = json.dumps(fixture["schema"], ensure_ascii=False, separators=(",", ":"))
    prompt = (
        "You are taking part in a controlled evaluation. Do not use tools, browse, or inspect local files. "
        "Return one JSON object that matches the supplied schema. Do not use Markdown fences. "
        "Do not add fields that are not in the schema.\n\n"
        f"Condition: {condition}\n\n"
        f"{context_block}"
        f"<task>\n{fixture['task']}\n</task>\n\n"
        f"<response_schema>\n{schema}\n</response_schema>\n"
    )
    return prompt, context


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("model output does not contain a JSON object")


def validate_schema(value: Any, schema: dict[str, Any], path: str = "response") -> None:
    """Validate the finite schema vocabulary used by this repository, fail closed."""
    supported = {"type", "properties", "required", "additionalProperties", "items", "enum", "description"}
    if not isinstance(schema, dict) or set(schema) - supported:
        raise ValueError(f"{path}: unsupported schema keyword")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float), "null": type(None)}
    kind = schema.get("type")
    if kind not in types or not isinstance(value, types[kind]) or (kind in {"number", "integer"} and isinstance(value, bool)):
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value outside enum")
    if kind == "object":
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        extra = set(value) - set(properties)
        if missing or (schema.get("additionalProperties") is False and extra):
            raise ValueError(f"{path}: missing or extra fields")
        for key in set(value) & set(properties):
            validate_schema(value[key], properties[key], f"{path}.{key}")
    elif kind == "array":
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), f"{path}[{index}]")


def get_path(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def evaluate_check(actual: Any, operation: str, expected: Any) -> bool:
    if operation == "eq":
        return actual == expected
    if operation == "contains":
        if isinstance(actual, str):
            return str(expected).casefold() in actual.casefold()
        if isinstance(actual, list):
            return expected in actual
        return False
    if operation == "set_eq":
        return isinstance(actual, list) and set(actual) == set(expected)
    if operation == "min_length":
        return hasattr(actual, "__len__") and len(actual) >= int(expected)
    raise ValueError(f"unknown check operation: {operation}")


def score_response(response: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for check in checks:
        try:
            actual = get_path(response, check["path"])
            passed = evaluate_check(actual, check["op"], check.get("value"))
            error = None
        except (KeyError, TypeError, ValueError) as exc:
            actual = None
            passed = False
            error = str(exc)
        results.append({**check, "actual": actual, "passed": passed, "error": error})
    passed_count = sum(1 for item in results if item["passed"])
    return {
        "passed": bool(results) and passed_count == len(results),
        "score": passed_count / len(results) if results else 0.0,
        "passed_checks": passed_count,
        "total_checks": len(results),
        "checks": results,
    }


def sanitized_stderr(text: str) -> str:
    value = text[-2000:]
    value = value.replace(str(Path.home()), "<HOME>").replace(str(ROOT), "<REPO>")
    return value


def copy_codex_auth(temp_home: Path) -> None:
    source = Path.home() / ".codex" / "auth.json"
    if not source.is_file():
        raise FileNotFoundError("Codex auth.json is missing")
    destination = temp_home / ".codex" / "auth.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def run_codex(model: str, prompt: str, schema: dict[str, Any], timeout: int) -> dict[str, Any]:
    binary = shutil.which("codex")
    if not binary:
        raise FileNotFoundError("codex binary is unavailable")
    with tempfile.TemporaryDirectory(prefix="rw-cross-model-codex-") as temp_dir:
        temp = Path(temp_dir)
        temp_home = temp / "home"
        temp_home.mkdir()
        copy_codex_auth(temp_home)
        schema_path = temp / "schema.json"
        output_path = temp / "last-message.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["HOME"] = str(temp_home)
        env["CODEX_HOME"] = str(temp_home / ".codex")
        command = [
            binary, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model, "--json",
            "--output-schema", str(schema_path), "-o", str(output_path), prompt,
        ]
        started = time.monotonic()
        result = subprocess.run(
            command, cwd=temp, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        events: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        output = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
        if not output:
            output = "\n".join(
                str(event.get("item", {}).get("text", ""))
                for event in events
                if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message"
            )
        usage = next((event.get("usage", {}) for event in reversed(events) if event.get("type") == "turn.completed"), {})
        return {
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
            "output": output,
            "usage": usage,
            "cost_usd": None,
            "stderr": sanitized_stderr(result.stderr),
        }


def run_claude(model: str, prompt: str, schema: dict[str, Any], timeout: int) -> dict[str, Any]:
    binary = shutil.which("claude")
    if not binary:
        raise FileNotFoundError("claude binary is unavailable")
    with tempfile.TemporaryDirectory(prefix="rw-cross-model-claude-") as temp_dir:
        command = [
            binary, "-p", prompt, "--output-format", "json", "--model", model,
            "--tools", "", "--no-session-persistence", "--disable-slash-commands", "--no-chrome",
            "--system-prompt", "Follow the evaluation prompt. Use no tools. Return only schema-valid JSON.",
            "--json-schema", json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
        ]
        started = time.monotonic()
        result = subprocess.run(
            command, cwd=temp_dir, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        wrapper = json.loads(result.stdout) if result.stdout.strip() else {}
        output = wrapper.get("structured_output") or wrapper.get("result") or ""
        if isinstance(output, dict):
            output = json.dumps(output, ensure_ascii=False)
        return {
            "exit_code": result.returncode,
            "duration_ms": duration_ms,
            "output": str(output),
            "usage": wrapper.get("usage", {}),
            "cost_usd": wrapper.get("total_cost_usd"),
            "actual_models": sorted((wrapper.get("modelUsage") or {}).keys()),
            "stderr": sanitized_stderr(result.stderr),
        }


def run_one(spec: dict[str, Any], fixture: dict[str, Any], condition: str, repetition: int, timeout: int) -> dict[str, Any]:
    prompt, context = build_prompt(fixture, condition)
    started_at = utc_now()
    record: dict[str, Any] = {
        "model_id": spec["id"],
        "provider": spec["provider"],
        "requested_model": spec["model"],
        "fixture_id": fixture["id"],
        "skill": fixture["skill"],
        "condition": condition,
        "repetition": repetition,
        "started_at": started_at,
        "prompt_sha256": sha256_text(prompt),
        "skill_context_sha256": sha256_text(context) if context else None,
    }
    try:
        if spec["provider"] == "codex":
            execution = run_codex(spec["model"], prompt, fixture["schema"], timeout)
        elif spec["provider"] == "claude":
            execution = run_claude(spec["model"], prompt, fixture["schema"], timeout)
        else:
            raise ValueError(f"unsupported provider: {spec['provider']}")
        record["execution"] = execution
        if execution["exit_code"] != 0:
            raise RuntimeError(f"model process exited with {execution['exit_code']}")
        parsed = extract_json(execution["output"])
        validate_schema(parsed, fixture["schema"])
        record["response"] = parsed
        record["scoring"] = score_response(parsed, fixture["checks"])
        record["error"] = None
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        record.setdefault("execution", {})
        record["response"] = None
        record["scoring"] = {"passed": False, "score": 0.0, "passed_checks": 0, "total_checks": len(fixture["checks"]), "checks": []}
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def validate_inputs(fixtures: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if not isinstance(fixtures, list) or not fixtures or not all(isinstance(item, dict) for item in fixtures):
        return ["fixtures must be a non-empty object list"]
    if not isinstance(models, list) or not models or not all(isinstance(item, dict) for item in models):
        return ["models must be a non-empty object list"]
    valid_operations = {"eq", "contains", "set_eq", "min_length"}
    fixture_ids: set[str] = set()
    for fixture in fixtures:
        fixture_id = fixture.get("id")
        if not fixture.get("synthetic"):
            failures.append(f"fixture is not marked synthetic: {fixture_id}")
        if not str(fixture.get("suite_role", "")).startswith("held_out_"):
            failures.append(f"default fixture is not marked held out: {fixture_id}")
        if fixture_id in fixture_ids:
            failures.append(f"duplicate fixture id: {fixture_id}")
        fixture_ids.add(fixture_id)
        if fixture.get("skill") not in CONTEXT_FILES:
            failures.append(f"unsupported fixture skill: {fixture.get('skill')}")
        if not fixture.get("checks"):
            failures.append(f"fixture has no deterministic checks: {fixture_id}")
        schema = fixture.get("schema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = schema.get("required", []) if isinstance(schema, dict) else []
        if not isinstance(schema, dict) or schema.get("type") != "object" or not isinstance(properties, dict) or not isinstance(required, list):
            failures.append(f"fixture has invalid object schema: {fixture_id}")
        for check in fixture.get("checks", []):
            path = check.get("path", "")
            if check.get("op") not in valid_operations:
                failures.append(f"fixture has unsupported check operation: {fixture_id}")
            if path.split(".", 1)[0] not in required:
                failures.append(f"checked field is not required by schema: {fixture_id}:{path}")
    model_ids = [model.get("id") for model in models]
    if len(model_ids) != len(set(model_ids)):
        failures.append("duplicate model id")
    for model in models:
        if model.get("provider") not in {"codex", "claude"}:
            failures.append(f"unsupported model provider: {model.get('id')}")
    behavior_prompts: set[str] = set()
    for path in (ROOT / "skills").glob("*/references/behavior-tests.json"):
        for item in load_json(path):
            behavior_prompts.add(" ".join(str(item.get("prompt", "")).casefold().split()))
    for fixture in fixtures:
        normalized = " ".join(fixture["task"].casefold().split())
        if normalized in behavior_prompts:
            failures.append(f"fixture duplicates a published behavior prompt: {fixture['id']}")
    return failures


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    records = data.get("records", [])
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault((record["model_id"], record["condition"]), []).append(record)
    model_rows: list[dict[str, Any]] = []
    for (model_id, condition), items in sorted(grouped.items()):
        passed = sum(1 for item in items if item["scoring"]["passed"])
        durations = [item.get("execution", {}).get("duration_ms", 0) for item in items]
        costs = [item.get("execution", {}).get("cost_usd") for item in items]
        reported_costs = [value for value in costs if isinstance(value, (int, float))]
        model_rows.append({
            "model_id": model_id,
            "condition": condition,
            "passed": passed,
            "total": len(items),
            "pass_rate": passed / len(items) if items else 0.0,
            "mean_score": statistics.mean(item["scoring"]["score"] for item in items) if items else 0.0,
            "median_duration_ms": round(statistics.median(durations)) if durations else 0,
            "reported_cost_usd": round(sum(reported_costs), 6) if reported_costs else None,
            "errors": sum(1 for item in items if item.get("error")),
        })
    fixture_rows: list[dict[str, Any]] = []
    skill_records = [record for record in records if record["condition"] == "with_skill"]
    for fixture_id in sorted({record["fixture_id"] for record in skill_records}):
        items = [record for record in skill_records if record["fixture_id"] == fixture_id]
        passed = sum(1 for item in items if item["scoring"]["passed"])
        fixture_rows.append({"fixture_id": fixture_id, "passed": passed, "total": len(items), "pass_rate": passed / len(items) if items else 0.0})
    skill_items = [record for record in records if record["condition"] == "with_skill"]
    baseline_items = [record for record in records if record["condition"] == "without_skill"]
    skill_rate = sum(1 for item in skill_items if item["scoring"]["passed"]) / len(skill_items) if skill_items else 0.0
    baseline_rate = sum(1 for item in baseline_items if item["scoring"]["passed"]) / len(baseline_items) if baseline_items else 0.0
    providers = {record["provider"] for record in skill_items}
    models = {record["model_id"] for record in skill_items}
    skill_errors = sum(1 for item in skill_items if item.get("error"))
    minimum_fixture_rate = min((row["pass_rate"] for row in fixture_rows), default=0.0)
    expected_models = {model["id"] for model in data.get("models", [])}
    expected_fixtures = set(data.get("fixture_ids", []))
    repetitions = data.get("repetitions", 0)
    expected = {(model, fixture, condition, repetition)
                for model in expected_models for fixture in expected_fixtures
                for condition in ("with_skill", "without_skill")
                for repetition in range(1, repetitions + 1)}
    actual = [(item["model_id"], item["fixture_id"], item["condition"], item.get("repetition")) for item in records]
    matrix_complete = bool(expected) and len(actual) == len(expected) and set(actual) == expected and bool(data.get("finished_at"))
    eligible = matrix_complete and len(providers) >= 2 and len(models) >= 3
    verified = eligible and skill_errors == 0 and skill_rate >= 0.80 and minimum_fixture_rate >= 0.75
    return {
        "status": "CROSS_MODEL_VERIFIED" if verified else "CROSS_MODEL_NOT_VERIFIED",
        "matrix_complete": matrix_complete,
        "providers": sorted(providers),
        "models": sorted(models),
        "with_skill_pass_rate": skill_rate,
        "without_skill_pass_rate": baseline_rate,
        "paired_delta": skill_rate - baseline_rate,
        "minimum_fixture_pass_rate": minimum_fixture_rate,
        "skill_condition_errors": skill_errors,
        "model_results": model_rows,
        "fixture_results": fixture_rows,
    }


def summary_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    run_id = data.get("run_id", "unknown")
    lines = [
        f"# Cross-model validation: {run_id}", "",
        f"Status: `{summary['status']}`", "",
        f"Providers: {', '.join(summary['providers'])}",
        f"Models: {', '.join(summary['models'])}",
        f"With Skill pass rate: {summary['with_skill_pass_rate']:.1%}",
        f"Without Skill pass rate: {summary['without_skill_pass_rate']:.1%}",
        f"Paired delta: {summary['paired_delta']:+.1%}",
        f"Minimum fixture pass rate across models: {summary['minimum_fixture_pass_rate']:.1%}", "",
        "## Run record", "",
        f"Source revision: `{data.get('git_sha', 'unknown')}`",
        f"Worktree dirty at run start: `{data.get('git_worktree_dirty', 'not recorded')}`",
        f"Fixture file: `{data.get('fixtures_file', 'not recorded')}`",
        f"Fixture SHA-256: `{data.get('fixtures_sha256', 'not recorded')}`",
        f"Model-config SHA-256: `{data.get('models_sha256', 'not recorded')}`",
        f"CLI versions: `{json.dumps(data.get('cli_versions', {}), ensure_ascii=False, sort_keys=True)}`", "",
        "## Model results", "",
        "| Model | Condition | Passed | Pass rate | Mean check score | Median duration | Reported cost | Errors |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["model_results"]:
        reported_cost = f"${row['reported_cost_usd']:.4f}" if row["reported_cost_usd"] is not None else "not reported"
        lines.append(
            f"| {row['model_id']} | {row['condition']} | {row['passed']}/{row['total']} | "
            f"{row['pass_rate']:.1%} | {row['mean_score']:.1%} | {row['median_duration_ms']} ms | "
            f"{reported_cost} | {row['errors']} |"
        )
    lines.extend(["", "## Fixture consistency", "", "| Fixture | Passed models | Pass rate |", "| --- | ---: | ---: |"])
    for row in summary["fixture_results"]:
        lines.append(f"| {row['fixture_id']} | {row['passed']}/{row['total']} | {row['pass_rate']:.1%} |")
    actual_usage: dict[str, set[str]] = {}
    for record in data.get("records", []):
        models = record.get("execution", {}).get("actual_models", [])
        if models:
            actual_usage.setdefault(record["model_id"], set()).update(models)
    if actual_usage:
        lines.extend(["", "## Provider-reported model usage", ""])
        for model_id, actual_models in sorted(actual_usage.items()):
            lines.append(f"- {model_id}: {', '.join(sorted(actual_models))}")
    lines.extend([
        "", "## Boundary", "",
        "This result applies only to the recorded models, versions, fixtures, prompts, and run configuration. "
        "It does not prove improvement in real research outcomes or untested disciplines.", "",
    ])
    return "\n".join(lines)


def command_check(args: argparse.Namespace) -> int:
    fixtures = load_json(Path(args.fixtures))
    models = load_json(Path(args.models))
    failures = validate_inputs(fixtures, models)
    result = {"fixtures": len(fixtures), "models": len(models), "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failures else 0


def command_run(args: argparse.Namespace) -> int:
    try:
        safe_name(args.run_id, "run id")
        if min(args.repetitions, args.workers, args.timeout) < 1:
            raise ValueError("repetitions, workers, and timeout must be positive")
        no_symlink(EVAL_ROOT / "results" / args.run_id)
    except ValueError as exc:
        print(json.dumps({"failures": [str(exc)]}))
        return 2
    fixtures = load_json(Path(args.fixtures))
    models = load_json(Path(args.models))
    failures = validate_inputs(fixtures, models)
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
        return 2
    selected_models = [model for model in models if not args.model or model["id"] in args.model]
    selected_fixtures = [fixture for fixture in fixtures if not args.fixture or fixture["id"] in args.fixture]
    missing_models = sorted(set(args.model or []) - {model["id"] for model in selected_models})
    missing_fixtures = sorted(set(args.fixture or []) - {fixture["id"] for fixture in selected_fixtures})
    if missing_models or missing_fixtures:
        print(json.dumps({"missing_models": missing_models, "missing_fixtures": missing_fixtures}, indent=2))
        return 2
    preflight = provider_preflight(selected_models)
    if preflight["failures"]:
        print(json.dumps({"status": "PREFLIGHT_BLOCKED", **preflight}, ensure_ascii=False, indent=2))
        return 2
    combinations = [
        (model, fixture, condition, repetition)
        for repetition in range(1, args.repetitions + 1)
        for model in selected_models
        for fixture in selected_fixtures
        for condition in ("with_skill", "without_skill")
    ]
    random.Random(args.seed).shuffle(combinations)
    run_dir = EVAL_ROOT / "results" / args.run_id
    result_path = run_dir / "results.json"
    if run_dir.exists():
        print(f"refusing to overwrite existing run: {result_path}")
        return 2
    fixture_path = Path(args.fixtures)
    model_path = Path(args.models)
    data: dict[str, Any] = {
        "schema_version": 1,
        "run_id": args.run_id,
        "started_at": utc_now(),
        "finished_at": None,
        "git_sha": git_sha(),
        "git_worktree_dirty": git_dirty(),
        "seed": args.seed,
        "repetitions": args.repetitions,
        "fixtures_file": fixture_path.name,
        "fixtures_sha256": sha256_text(fixture_path.read_text(encoding="utf-8")),
        "models_file": model_path.name,
        "models_sha256": sha256_text(model_path.read_text(encoding="utf-8")),
        "cli_versions": {"codex": command_version("codex"), "claude": command_version("claude")},
        "models": selected_models,
        "fixture_ids": [fixture["id"] for fixture in selected_fixtures],
        "records": [],
    }
    lock = threading.Lock()
    atomic_json(result_path, data)

    def completed(record: dict[str, Any]) -> None:
        with lock:
            data["records"].append(record)
            data["records"].sort(key=lambda item: (item["model_id"], item["fixture_id"], item["condition"], item["repetition"]))
            atomic_json(result_path, data)
            status = "PASS" if record["scoring"]["passed"] else "FAIL"
            print(f"{status} {record['model_id']} {record['condition']} {record['fixture_id']} r{record['repetition']}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(run_one, model, fixture, condition, repetition, args.timeout): (model, fixture, condition, repetition)
            for model, fixture, condition, repetition in combinations
        }
        for future in concurrent.futures.as_completed(future_map):
            try:
                completed(future.result())
            except Exception as exc:
                model, fixture, condition, repetition = future_map[future]
                completed({
                    "model_id": model["id"], "provider": model["provider"], "requested_model": model["model"],
                    "fixture_id": fixture["id"], "skill": fixture["skill"], "condition": condition,
                    "repetition": repetition, "started_at": utc_now(), "prompt_sha256": None,
                    "skill_context_sha256": None, "execution": {}, "response": None,
                    "scoring": {"passed": False, "score": 0.0, "passed_checks": 0, "total_checks": len(fixture["checks"]), "checks": []},
                    "error": f"worker error: {exc}",
                })
    data["finished_at"] = utc_now()
    data["summary"] = summarize(data)
    atomic_json(result_path, data)
    (run_dir / "summary.md").write_text(summary_markdown(data), encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    return 0 if data["summary"]["status"] == "CROSS_MODEL_VERIFIED" else 1


def command_summarize(args: argparse.Namespace) -> int:
    path = Path(args.results)
    data = load_json(path)
    data["summary"] = summarize(data)
    atomic_json(path, data)
    markdown_path = path.parent / "summary.md"
    markdown_path.write_text(summary_markdown(data), encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    models = load_json(Path(args.models))
    selected = [model for model in models if not args.model or model["id"] in args.model]
    missing = sorted(set(args.model or []) - {model["id"] for model in selected})
    if missing:
        print(json.dumps({"missing_models": missing}, ensure_ascii=False, indent=2))
        return 2
    result = provider_preflight(selected)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failures"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    check.add_argument("--models", default=str(DEFAULT_MODELS))
    check.set_defaults(func=command_check)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--models", default=str(DEFAULT_MODELS))
    preflight.add_argument("--model", action="append")
    preflight.set_defaults(func=command_preflight)
    run = subparsers.add_parser("run")
    run.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    run.add_argument("--models", default=str(DEFAULT_MODELS))
    run.add_argument("--model", action="append")
    run.add_argument("--fixture", action="append")
    run.add_argument("--repetitions", type=int, default=1)
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--timeout", type=int, default=240)
    run.add_argument("--seed", type=int, default=20260720)
    run.add_argument("--run-id", required=True)
    run.set_defaults(func=command_run)
    summary = subparsers.add_parser("summarize")
    summary.add_argument("results")
    summary.set_defaults(func=command_summarize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
