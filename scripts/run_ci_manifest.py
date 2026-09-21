#!/usr/bin/env python3
"""Run the repository checks declared in ci/manifest.json."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "ci" / "manifest.json"
CHECK_ID = re.compile(r"[a-z0-9][a-z0-9-]*$")


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "rw-ci-manifest/v1":
        raise ValueError("unsupported CI manifest schema_version")
    checks = manifest.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("CI manifest checks must be a non-empty list")
    seen: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ValueError(f"checks[{index}] must be an object")
        check_id = check.get("id")
        if not isinstance(check_id, str) or not CHECK_ID.fullmatch(check_id):
            raise ValueError(f"checks[{index}].id is invalid")
        if check_id in seen:
            raise ValueError(f"duplicate check id: {check_id}")
        seen.add(check_id)
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            raise ValueError(f"{check_id}: argv must be a non-empty string list")
        if not isinstance(check.get("required"), bool):
            raise ValueError(f"{check_id}: required must be boolean")
    return manifest


def select_checks(manifest: dict, selected: list[str]) -> list[dict]:
    checks = manifest["checks"]
    if not selected:
        return checks
    known = {check["id"] for check in checks}
    unknown = sorted(set(selected) - known)
    if unknown:
        raise ValueError(f"unknown check id: {', '.join(unknown)}")
    wanted = set(selected)
    return [check for check in checks if check["id"] in wanted]


def render_argv(argv: list[str]) -> list[str]:
    return [sys.executable if item == "{python}" else item for item in argv]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = load_manifest(args.manifest)
        checks = select_checks(manifest, args.only)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"failures": [str(error)]}, ensure_ascii=False, indent=2))
        return 2

    if args.list:
        print(json.dumps({"checks": checks}, ensure_ascii=False, indent=2))
        return 0

    results: list[dict] = []
    for check in checks:
        argv = render_argv(check["argv"])
        print(f"\n[ci:{check['id']}] {check.get('description', '')}", flush=True)
        started = time.monotonic()
        error = None
        try:
            completed = subprocess.run(argv, cwd=ROOT, timeout=600)
            returncode = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            returncode = 1
            error = f"{type(exc).__name__}: {exc}"
            print(error, file=sys.stderr)
        duration = round(time.monotonic() - started, 3)
        results.append(
            {
                "id": check["id"],
                "required": check["required"],
                "returncode": returncode,
                "duration_seconds": duration,
                "status": "passed" if returncode == 0 else "failed",
                "error": error,
            }
        )

    failed_required = [result["id"] for result in results if result["required"] and result["returncode"]]
    summary = {
        "schema_version": manifest["schema_version"],
        "passed": len([result for result in results if result["status"] == "passed"]),
        "failed": len([result for result in results if result["status"] == "failed"]),
        "failed_required": failed_required,
        "results": results,
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(f"\n{rendered}")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if failed_required else 0


if __name__ == "__main__":
    raise SystemExit(main())
