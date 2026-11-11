#!/usr/bin/env python3
"""Validate and build the rwskill plugin zip."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


try:
    from .check_repository import run_json_check
    from .package_safety import load_metadata, no_symlink, regular_files, atomic_zip
except ImportError:
    from check_repository import run_json_check
    from package_safety import load_metadata, no_symlink, regular_files, atomic_zip


def frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"\A---\nname:\s*([^\n]+)\n", text)
    if not match:
        raise ValueError(f"invalid frontmatter: {path}")
    return match.group(1).strip()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest, version = load_metadata(root)
    for directory in ("skills", "docs", ".codex-plugin"):
        regular_files(root / directory)
    repository_check = subprocess.run(
        [sys.executable, str(root / "scripts" / "check_repository.py")],
        capture_output=True,
        text=True,
    )
    if repository_check.returncode:
        print(repository_check.stdout, end="")
        print(repository_check.stderr, end="")
        raise SystemExit("repository check failed")
    failures: list[str] = []
    release_skills = list(dict.fromkeys(manifest["skills"]))
    for name in release_skills:
        skill = root / "skills" / name
        required = [skill / "SKILL.md", skill / "agents/openai.yaml"]
        if any(not path.is_file() or path.stat().st_size == 0 for path in required):
            failures.append(f"{name}: missing required file")
            continue
        if frontmatter_name(skill / "SKILL.md") != name:
            failures.append(f"{name}: frontmatter name mismatch")
        if "TODO" in (skill / "SKILL.md").read_text(encoding="utf-8"):
            failures.append(f"{name}: TODO remains")
    if failures:
        print(json.dumps({"failures": failures}, ensure_ascii=False, indent=2))
        return 1

    for name in release_skills:
        check_failures = []
        skill_root = root / "skills" / name
        self_check = skill_root / "scripts/self_check.py"
        if self_check.is_file():
            result = run_json_check([sys.executable, str(self_check)], name, check_failures, allow_legacy_self_check=True)
            if result.get("standalone") is False:
                check_failures.append(f"{name}: standalone is false")
        else:
            tests = sorted((skill_root / "scripts").glob("test_*.py")) + sorted((skill_root / "tests").glob("test_*.py"))
            if not tests:
                check_failures.append(f"{name}: neither self_check nor deterministic tests found")
            else:
                count = 0
                for directory in ("scripts", "tests"):
                    if not any(path.parent.name == directory for path in tests):
                        continue
                    try:
                        completed = subprocess.run(
                            [sys.executable, "-m", "unittest", "discover", "-s", str(skill_root / directory), "-p", "test_*.py"],
                            capture_output=True, text=True, timeout=120,
                        )
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        check_failures.append(f"{name}: {directory} tests failed to run: {exc}")
                        continue
                    output = completed.stdout + completed.stderr
                    count += sum(int(value) for value in re.findall(r"^Ran (\d+) tests?", output, re.MULTILINE))
                    if completed.returncode:
                        check_failures.append(f"{name}: {directory} tests failed: {output[-1200:]}")
                if count == 0:
                    check_failures.append(f"{name}: deterministic test suite collected no tests")
        if check_failures:
            print(json.dumps({"failures": check_failures}, ensure_ascii=False, indent=2))
            return 1

    package_name = manifest["name"]
    output = root / "dist" / f"{package_name}-{version}.zip"
    include_roots = [root / ".codex-plugin", root / "skills", root / "docs"]
    include_files = [root / "README.md", root / "LICENSE", root / "VERSION", root / "manifest.json"]
    members = [(path, (Path(package_name) / path.relative_to(root)).as_posix())
               for base in include_roots for path in regular_files(base)]
    members.extend((path, f"{package_name}/{path.name}") for path in include_files)
    atomic_zip(output, members)
    print(json.dumps({"version": version, "skills": len(release_skills), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
