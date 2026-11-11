#!/usr/bin/env python3
"""Copy release-approved RW skills from the workspace source tree."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path


try:
    from .package_safety import no_symlink, regular_files, skill_names, publish_directory
except ImportError:
    from package_safety import no_symlink, regular_files, skill_names, publish_directory


SYNTHETIC_NOTICE = "> 公开案例使用合成或占位输入，不来自任何个人研究项目。"


def sanitize_public_skill(skill: Path) -> None:
    atoms_path = skill / "references" / "atoms.jsonl"
    if atoms_path.is_file():
        atoms: list[str] = []
        for line in atoms_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            record.pop("original", None)
            atoms.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        atoms_path.write_text("\n".join(atoms) + "\n", encoding="utf-8")

    contracts_path = skill / "references" / "behavior-tests.json"
    if contracts_path.is_file():
        contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
        if not isinstance(contracts, list) or not contracts:
            raise ValueError(f"invalid behavior contracts: {contracts_path}")
        for contract in contracts:
            if not isinstance(contract, dict) or contract.get("fixture_kind") != "synthetic":
                raise ValueError(f"public sync requires reviewed synthetic fixtures: {contracts_path}")
        contracts_path.write_text(json.dumps(contracts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cases_path = skill / "references" / "cases.md"
    if cases_path.is_file():
        text = cases_path.read_text(encoding="utf-8")
        if SYNTHETIC_NOTICE not in text:
            raise ValueError(f"public sync requires a reviewed synthetic case notice: {cases_path}")


def sync(plugin_root: Path, source_root: Path, only: list[str], dry_run: bool = False, prune: bool = False) -> dict:
    manifest = json.loads((plugin_root / "manifest.json").read_text(encoding="utf-8"))
    release_skills = skill_names(manifest)
    target_root = plugin_root / "skills"
    no_symlink(target_root)
    no_symlink(source_root)
    if target_root.exists():
        regular_files(target_root)
    if source_root.resolve() == target_root.resolve() or source_root.resolve().is_relative_to(target_root.resolve()):
        raise ValueError("source root overlaps target root")
    requested = set(only)
    unknown = sorted(requested - set(release_skills))
    if unknown:
        raise ValueError(f"--only contains skills outside manifest: {', '.join(unknown)}")
    if requested and prune:
        raise ValueError("--prune must not be combined with --only")
    selected = [name for name in release_skills if not requested or name in requested]
    delete = [p.name for p in target_root.iterdir() if p.is_dir() and p.name not in release_skills] if prune and target_root.is_dir() else []
    for name in selected:
        source = source_root / name
        regular_files(source)
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"missing source skill: {source}")
    plan = {"dry_run": dry_run, "source_root": str(source_root), "target_root": str(target_root), "delete": delete, "copy": selected}
    # Sanitize and validate every selected source in staging, even for dry runs.
    with tempfile.TemporaryDirectory(prefix=".sync-", dir=plugin_root) as temporary:
        staged = Path(temporary) / "skills"
        if target_root.exists():
            shutil.copytree(target_root, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        else:
            staged.mkdir()
        for name in delete + selected:
            old = staged / name
            if old.exists():
                if not old.is_dir():
                    raise ValueError(f"skill target is not a directory: {old}")
                shutil.rmtree(old)
        for name in selected:
            shutil.copytree(source_root / name, staged / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            sanitize_public_skill(staged / name)
        if not dry_run:
            publish_directory(staged, target_root)
    return plan if dry_run else {**plan, "copied": selected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prune", action="store_true", help="explicitly remove target directories outside the manifest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        plan = sync(root, args.source_root or root.parents[1] / "skills", args.only, args.dry_run, args.prune)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"failures": [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
