"""Fail-closed local packaging primitives (no network or model calls)."""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path

NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,127}\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z")


def safe_name(value, label="name") -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def no_symlink(path: Path) -> None:
    # Resolve only after examining each component, including the output parent.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"symlink is not allowed: {part}")


def regular_files(root: Path) -> list[Path]:
    no_symlink(root)
    if not root.is_dir():
        raise ValueError(f"missing directory: {root}")
    files = []
    for path in sorted(root.rglob("*")):
        no_symlink(path)
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"non-regular package file: {path}")
        if "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != ".DS_Store":
            files.append(path)
    return files


def load_metadata(root: Path) -> tuple[dict, str]:
    for relative in ("manifest.json", "VERSION", ".codex-plugin/plugin.json"):
        no_symlink(root / relative)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not isinstance(manifest, dict) or not isinstance(plugin, dict):
        raise ValueError("package metadata must contain JSON objects")
    safe_name(manifest.get("name"), "package name")
    if not VERSION.fullmatch(version):
        raise ValueError("invalid release version")
    if manifest.get("version") != version or plugin.get("version") != version:
        raise ValueError("VERSION, manifest.json, and plugin.json do not match")
    skill_names(manifest)
    return manifest, version


def skill_names(manifest: dict) -> list[str]:
    names = manifest.get("skills")
    if not isinstance(names, list) or not names:
        raise ValueError("manifest skills must be a non-empty list")
    for name in names:
        safe_name(name, "skill name")
    if len(names) != len(set(names)):
        raise ValueError("manifest contains duplicate Skill names")
    return names


def publish_directory(staged: Path, target: Path) -> None:
    """Two renames with rollback; old data survives validation/copy failures.

    This is exception-safe, not a multi-file power-loss transaction. A crash
    between renames may leave a .previous-* directory for manual recovery.
    """
    no_symlink(target)
    backup = None
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"target is not a directory: {target}")
        backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.previous-", dir=target.parent))
        backup.rmdir()
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except BaseException:
        if backup is not None:
            os.replace(backup, target)
        raise
    if backup is not None:
        import shutil
        shutil.rmtree(backup)


def atomic_zip(output: Path, members: list[tuple[Path, str]]) -> None:
    no_symlink(output)
    names = set()
    for source, name in members:
        no_symlink(source)
        if not source.is_file() or not stat.S_ISREG(source.stat().st_mode):
            raise ValueError(f"non-regular archive source: {source}")
        if "\\" in name or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/")) or name in names:
            raise ValueError(f"unsafe or duplicate archive member: {name}")
        names.add(name)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, name in members:
                archive.write(source, name)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
