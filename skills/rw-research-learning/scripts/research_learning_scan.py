#!/usr/bin/env python3
"""Build and query a local, incremental index for RW Research Learning."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import html
import json
import math
import os
import re
import sqlite3
import stat as stat_module
import tempfile
import sys
import zipfile
from contextlib import contextmanager
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


SCHEMA_VERSION = "rw-research-learning-index/v2"
PROFILE_SCHEMA_VERSION = "rw-research-learning/v2"
LEGACY_PROFILE_SCHEMA_VERSION = "rw-research-learning/v1"
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 500_000
EXTRACTION_POLICY_VERSION = "audit-v3"
MAX_OFFICE_XML_BYTES = 32 * 1024 * 1024
INDEX_APPLICATION_ID = 0x52574C49  # RWLI
TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".html", ".htm", ".json", ".jsonl",
    ".csv", ".tsv", ".yaml", ".yml", ".xml", ".rst", ".tex",
}
OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
PDF_EXTENSION = ".pdf"
SKIP_DIRECTORY_NAMES = {
    ".git", ".hg", ".svn", ".rw-research", "node_modules", "vendor",
    ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "dist", "build", "target", "coverage", ".cache",
    ".trash", ".trashes",
    "secrets", "credentials", "private-keys", "private_keys",
}
HOME_LEVEL_SKIP_DIRECTORY_NAMES = {"library", "applications", "system"}
SENSITIVE_EXTENSIONS = {
    ".pem", ".key", ".p12", ".pfx", ".kdbx", ".keystore", ".mobileprovision",
}
SENSITIVE_NAMES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
    "credentials.json", "secrets.json", "secrets.yaml", "secrets.yml",
    "secret.txt", "passwords.txt", "passwords.csv", "passwords.json",
    "auth.json", "tokens.json",
}
SUPPORTED_PROFILE_STATUSES = {"applied", "articulated", "exposed", "no_evidence"}
SUPPORTED_CONFIDENCE = {"high", "medium", "low"}
SUPPORTED_MODES = {"folder", "current", "user"}
SUPPORTED_SOURCE_KINDS = {
    "user_output", "process_record", "collaborative_output", "ai_assisted",
    "external_reference", "downloaded_tool", "unknown",
}
SUPPORTED_CURRENTNESS = {"current", "historical", "reference", "unknown"}
SUPPORTED_ARTIFACT_TYPES = {
    "document", "worksheet", "decision_register", "analysis_plan",
    "coding_exercise", "evidence_map", "model_input_table", "other",
}
RESEARCH_PATH_TERMS = {
    "research", "phd", "thesis", "paper", "papers", "literature", "study",
    "studies", "methods", "methodology", "evidence", "科研", "研究", "论文",
    "文献", "博士", "方法", "证据",
}


class ExtractorUnavailable(RuntimeError):
    """Raised when an optional extractor is not installed."""


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def is_filesystem_root(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == Path(resolved.anchor)


def resolve_roots(mode: str, supplied: list[Path]) -> list[Path]:
    if mode not in tuple(SUPPORTED_MODES):
        raise ValueError(f"unsupported mode: {mode}")
    if supplied:
        roots = supplied
    elif mode == "current":
        roots = [Path.cwd()]
    elif mode == "user":
        roots = [Path.home()]
    else:
        raise ValueError("folder mode requires at least one --root")

    candidates: list[Path] = []
    seen: set[str] = set()
    for raw in roots:
        root = raw.expanduser().resolve()
        if is_filesystem_root(root):
            raise ValueError(f"refusing filesystem root: {root}")
        if not root.exists():
            raise ValueError(f"root does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"root is not a directory: {root}")
        key = str(root)
        if key not in seen:
            candidates.append(root)
            seen.add(key)
    resolved_roots: list[Path] = []
    for root in sorted(candidates, key=lambda item: (len(item.parts), str(item))):
        if any(root == parent or root.is_relative_to(parent) for parent in resolved_roots):
            continue
        resolved_roots.append(root)
    return resolved_roots


def sensitive_file(path: Path) -> bool:
    name = path.name.lower()
    if any(part.lower() in {"secrets", "credentials", "private-keys", "private_keys", ".ssh", ".aws", ".gnupg"} for part in path.parts[:-1]):
        return True
    if name in SENSITIVE_NAMES or name.startswith(".env."):
        return True
    if path.suffix.lower() in SENSITIVE_EXTENSIONS:
        return True
    if path.stem.lower() in {"secret", "secrets", "token", "tokens", "password", "passwords", "auth"}:
        return True
    return any(marker in name for marker in ("credential", "private-key", "private_key", "api-key", "api_key"))


def should_skip_directory(name: str, current: Path | None = None, root: Path | None = None) -> bool:
    lower = name.lower()
    if lower in SKIP_DIRECTORY_NAMES or name.startswith("."):
        return True
    return bool(
        current is not None
        and root is not None
        and root == Path.home().resolve()
        and current.resolve() == root
        and lower in HOME_LEVEL_SKIP_DIRECTORY_NAMES
    )


def strip_markup(text: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def decode_bytes(data: bytes, *, truncated: bool = False) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return codecs.getincrementaldecoder("utf-16")().decode(data, final=not truncated)
    if b"\x00" in data[:4096]:
        raise ValueError("binary content")
    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            return codecs.getincrementaldecoder(encoding)().decode(data, final=not truncated)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_plain(path: Path, max_chars: int) -> tuple[str, bool]:
    byte_limit = max_chars * 4 + 4  # Reserve enough bytes for a BOM and complete first character.
    with path.open("rb") as handle:
        data = handle.read(byte_limit + 1)
    text = decode_bytes(data, truncated=len(data) > byte_limit)
    if path.suffix.lower() in {".html", ".htm", ".xml"}:
        text = strip_markup(text)
    partial = len(text) > max_chars or len(data) > byte_limit
    return text[:max_chars], partial


def xml_text(blob: bytes) -> str:
    root = ElementTree.fromstring(blob)
    values: list[str] = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in {"t", "v"} and node.text:
            values.append(node.text)
        elif tag in {"p", "tr", "row"}:
            values.append("\n")
    return " ".join(values).replace(" \n ", "\n")


def extract_office(path: Path, max_chars: int) -> tuple[str, bool]:
    ext = path.suffix.lower()
    patterns = {
        ".docx": ("word/document.xml", "word/header", "word/footer"),
        ".pptx": ("ppt/slides/slide", "ppt/notesSlides/notesSlide"),
        ".xlsx": ("xl/sharedStrings.xml", "xl/worksheets/sheet"),
    }[ext]
    parts: list[str] = []
    total = 0
    partial = False
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name for name in archive.namelist()
            if name.endswith(".xml") and any(name.startswith(prefix) for prefix in patterns)
        )
        if any(archive.getinfo(name).file_size > MAX_OFFICE_XML_BYTES for name in names) or sum(archive.getinfo(name).file_size for name in names) > MAX_OFFICE_XML_BYTES * 2:
            raise ValueError("Office XML exceeds the bounded extraction limit")
        for name in names:
            value = xml_text(archive.read(name))
            remaining = max_chars - total
            if remaining <= 0:
                partial = True
                break
            parts.append(value[:remaining])
            total += min(len(value), remaining)
            if len(value) > remaining:
                partial = True
                break
    joined = "\n".join(part for part in parts if part.strip())
    return joined[:max_chars], partial or len(joined) > max_chars


def extract_pdf(path: Path, max_chars: int) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise ExtractorUnavailable("PDF parser unavailable") from exc
    reader = PdfReader(str(path))
    parts: list[str] = []
    total = 0
    partial = False
    for page in reader.pages:
        value = page.extract_text() or ""
        remaining = max_chars - total
        if remaining <= 0:
            partial = True
            break
        parts.append(value[:remaining])
        total += min(len(value), remaining)
        if len(value) > remaining:
            partial = True
            break
    joined = "\n".join(parts)
    return joined[:max_chars], partial or len(joined) > max_chars


def extract_text(path: Path, max_chars: int) -> tuple[str, str, str]:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS:
            text, partial = extract_plain(path, max_chars)
        elif ext in OFFICE_EXTENSIONS:
            text, partial = extract_office(path, max_chars)
        elif ext == PDF_EXTENSION:
            text, partial = extract_pdf(path, max_chars)
        else:
            return "", "unsupported", "no packaged extractor"
    except ExtractorUnavailable as exc:
        return "", "unsupported", str(exc)
    except Exception as exc:  # one malformed file must not stop the scan
        detail = f"{type(exc).__name__}: {exc}"[:500]
        return "", "unreadable", detail

    normalized = text.replace("\x00", "").strip()
    if not normalized:
        return "", "unsupported", "no extractable text"
    return normalized, "partial" if partial else "indexed", ""


def verify_existing_database(database: Path) -> None:
    """Reject foreign or aliased files before any migration, chmod, or WAL write."""
    if not database.is_file():
        raise ValueError("index path must be a regular database file")
    if database.stat().st_nlink > 1:
        raise ValueError("index database must not have multiple hard links")
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        if application_id not in (0, INDEX_APPLICATION_ID):
            raise ValueError("existing database belongs to another application")
        objects = dict(connection.execute("SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
        if any(objects.get(name) != "table" for name in ("documents", "scan_runs")):
            raise ValueError("existing database does not contain index tables")
        if application_id == 0 and any(kind == "table" and name not in ("documents", "scan_runs") for name, kind in objects.items()):
            raise ValueError("legacy database contains unrelated tables")
        required_columns = {
            "documents": {"path", "root", "title", "extension", "size", "mtime_ns", "content_hash", "text", "extraction_status", "detail", "last_seen", "updated_at"},
            "scan_runs": {"run_id", "started_at", "completed_at", "mode", "roots_json", "summary_json"},
        }
        for table, required in required_columns.items():
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not required.issubset(columns):
                raise ValueError("existing database is not a compatible research learning index")
    finally:
        connection.close()


def connect_database(state_dir: Path, *, readonly: bool = False) -> sqlite3.Connection:
    database = state_dir / "index.sqlite"
    if database.is_symlink():
        raise ValueError("index database must not be a symbolic link")
    if database.exists():
        verify_existing_database(database)
    if readonly:
        if not database.is_file():
            raise ValueError("index does not exist; run scan before querying")
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(database)
    database.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA application_id={INDEX_APPLICATION_ID}")
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS documents (
            path TEXT PRIMARY KEY,
            root TEXT NOT NULL,
            title TEXT NOT NULL,
            extension TEXT NOT NULL,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            text TEXT NOT NULL,
            extraction_status TEXT NOT NULL,
            detail TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_documents_root ON documents(root);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(extraction_status);
        CREATE TABLE IF NOT EXISTS scan_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            mode TEXT NOT NULL,
            roots_json TEXT NOT NULL,
            summary_json TEXT
        );
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    if "ctime_ns" not in columns:
        connection.execute("ALTER TABLE documents ADD COLUMN ctime_ns INTEGER NOT NULL DEFAULT 0")
    if "policy_fingerprint" not in columns:
        connection.execute("ALTER TABLE documents ADD COLUMN policy_fingerprint TEXT NOT NULL DEFAULT ''")
    connection.commit()
    return connection


def iter_files(root: Path, errors: list[dict[str, str]]) -> Iterable[Path]:
    def on_error(error: OSError) -> None:
        errors.append(
            {
                "path": str(error.filename or root),
                "kind": "directory",
                "error": f"{type(error).__name__}: {error}",
            }
        )

    for current, directories, files in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if not should_skip_directory(name, Path(current), root)
            and not (Path(current) / name).is_symlink()
        )
        for name in sorted(files):
            path = Path(current) / name
            if not path.is_symlink():
                yield path


def file_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def path_keyword_hits(path: Path) -> list[str]:
    lowered = str(path).lower()
    return sorted(term for term in RESEARCH_PATH_TERMS if term in lowered)


def discover_candidate_roots(
    roots: list[Path], max_depth: int, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Rank likely research/content roots from metadata only; never read file contents."""
    candidates: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    extractable = TEXT_EXTENSIONS | OFFICE_EXTENSIONS | {PDF_EXTENSION}
    for root in roots:
        for path in iter_files(root, errors):
            if sensitive_file(path):
                continue
            try:
                stat = path.stat()
                relative = path.relative_to(root)
            except (OSError, ValueError):
                continue
            directories = relative.parts[:-1]
            depths = range(1, min(len(directories), max_depth) + 1) if directories else [0]
            for depth in depths:
                candidate = root if depth == 0 else root.joinpath(*directories[:depth])
                key = str(candidate)
                candidate_label = candidate.relative_to(root) if candidate != root else Path(candidate.name)
                item = candidates.setdefault(
                    key,
                    {
                        "root": key,
                        "files": 0,
                        "extractable": 0,
                        "office_or_pdf": 0,
                        "latest_mtime_ns": 0,
                        "keyword_hits": path_keyword_hits(candidate_label),
                    },
                )
                item["files"] += 1
                if path.suffix.lower() in extractable:
                    item["extractable"] += 1
                if path.suffix.lower() in OFFICE_EXTENSIONS | {PDF_EXTENSION}:
                    item["office_or_pdf"] += 1
                item["latest_mtime_ns"] = max(item["latest_mtime_ns"], stat.st_mtime_ns)
    ranked: list[dict[str, Any]] = []
    for item in candidates.values():
        if item["extractable"] == 0:
            continue
        item["score"] = (
            item["extractable"] * 2
            + item["office_or_pdf"] * 2
            + len(item["keyword_hits"]) * 20
        )
        ranked.append(item)
    ranked.sort(
        key=lambda item: (item["score"], item["latest_mtime_ns"], item["root"]),
        reverse=True,
    )
    return ranked[:limit], errors[:100]


def command_landscape(args: argparse.Namespace) -> int:
    try:
        roots = resolve_roots(args.mode, args.root)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    candidates, errors = discover_candidate_roots(roots, args.max_depth, args.limit)
    emit(
        {
            "mode": args.mode,
            "discovery_roots": [str(root) for root in roots],
            "content_extracted": False,
            "candidates": candidates,
            "unreadable_directories": errors,
        }
    )
    return 0


def scan_root(
    connection: sqlite3.Connection,
    root: Path,
    run_id: str,
    max_file_bytes: int,
    max_text_chars: int,
) -> tuple[Counter[str], list[dict[str, str]]]:
    counts: Counter[str] = Counter()
    unreadable_paths: list[dict[str, str]] = []
    if max_file_bytes <= 0 or max_text_chars <= 0:
        raise ValueError("scan limits must be positive integers")
    root = root.resolve()
    root_text = str(root)
    database_path = Path(connection.execute("PRAGMA database_list").fetchone()[2]).resolve()
    state_dir = database_path.parent
    policy_fingerprint = file_hash(json.dumps([EXTRACTION_POLICY_VERSION, max_file_bytes, max_text_chars,
                                              sorted(SENSITIVE_NAMES), sorted(SENSITIVE_EXTENSIONS)]))
    for path in iter_files(root, unreadable_paths):
        if path == state_dir or path.is_relative_to(state_dir):
            continue
        counts["files_seen"] += 1
        path_text = str(path.absolute())
        try:
            stat = path.lstat()
            if not stat_module.S_ISREG(stat.st_mode):
                counts["non_regular"] += 1
                continue
        except OSError as exc:
            counts["unreadable"] += 1
            unreadable_paths.append({"path": path_text, "kind": "file", "error": f"{type(exc).__name__}: {exc}"})
            continue

        previous = connection.execute(
            "SELECT size, mtime_ns, ctime_ns, policy_fingerprint, extraction_status FROM documents WHERE path = ?",
            (path_text,),
        ).fetchone()
        if (previous and not sensitive_file(path)
                and previous["size"] == stat.st_size and previous["mtime_ns"] == stat.st_mtime_ns
                and previous["ctime_ns"] == stat.st_ctime_ns
                and previous["policy_fingerprint"] == policy_fingerprint
                and previous["extraction_status"] in ("indexed", "partial", "too_large")):
            connection.execute(
                "UPDATE documents SET last_seen = ?, root = ? WHERE path = ?",
                (run_id, root_text, path_text),
            )
            counts["unchanged"] += 1
            counts[previous["extraction_status"]] += 1
            continue

        if sensitive_file(path):
            text, status, detail = "", "sensitive", "excluded by filename or extension"
        elif stat.st_size > max_file_bytes:
            text, status, detail = "", "too_large", f"larger than {max_file_bytes} bytes"
        else:
            text, status, detail = extract_text(path, max_text_chars)

        connection.execute(
            """
            INSERT INTO documents (
                path, root, title, extension, size, mtime_ns, content_hash, text,
                extraction_status, detail, last_seen, updated_at, ctime_ns, policy_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                root = excluded.root,
                title = excluded.title,
                extension = excluded.extension,
                size = excluded.size,
                mtime_ns = excluded.mtime_ns,
                content_hash = excluded.content_hash,
                text = excluded.text,
                extraction_status = excluded.extraction_status,
                detail = excluded.detail,
                last_seen = excluded.last_seen,
                updated_at = excluded.updated_at,
                ctime_ns = excluded.ctime_ns,
                policy_fingerprint = excluded.policy_fingerprint
            """,
            (
                path_text, root_text, path.stem, path.suffix.lower(), stat.st_size,
                stat.st_mtime_ns, file_hash(text) if text else "", text, status,
                detail, run_id, utc_now(), stat.st_ctime_ns, policy_fingerprint,
            ),
        )
        counts[status] += 1
        counts["changed"] += 1

    # A failed walk/stat is not evidence of deletion. Retain text for recovery,
    # but mark unseen rows unreadable so queries cannot report stale observations.
    prefix = root_text.rstrip(os.sep) + os.sep
    if unreadable_paths:
        retained = connection.execute(
            "UPDATE documents SET extraction_status = 'unreadable', detail = ? WHERE (root = ? OR substr(path, 1, ?) = ?) AND last_seen != ?",
            ("not observed during incomplete scan; previous text retained", root_text, len(prefix), prefix, run_id),
        ).rowcount
        counts["retained_unverified"] += max(0, retained)
        counts["deleted"] += 0
    else:
        deleted = connection.execute(
            "DELETE FROM documents WHERE (root = ? OR substr(path, 1, ?) = ?) AND last_seen != ?",
            (root_text, len(prefix), prefix, run_id),
        ).rowcount
        counts["deleted"] += max(0, deleted)
    counts["unreadable_directories"] += sum(item.get("kind", "directory") == "directory" for item in unreadable_paths)
    return counts, unreadable_paths[:100]


def _command_scan_locked(args: argparse.Namespace) -> int:
    try:
        roots = resolve_roots(args.mode, args.root)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    if args.max_file_bytes <= 0 or args.max_text_chars <= 0:
        emit({"ok": False, "error": "scan limits must be positive integers"})
        return 2
    state_dir = args.state_dir.expanduser().resolve()
    if any(root == state_dir or root.is_relative_to(state_dir) for root in roots):
        emit({"ok": False, "error": "state-dir must not equal or contain a content root"})
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    started_at = utc_now()
    connection = connect_database(state_dir)
    connection.execute(
        "INSERT INTO scan_runs (run_id, started_at, mode, roots_json) VALUES (?, ?, ?, ?)",
        (run_id, started_at, args.mode, json.dumps([str(root) for root in roots], ensure_ascii=False)),
    )
    total: Counter[str] = Counter()
    root_summaries: list[dict[str, Any]] = []
    try:
        for root in roots:
            counts, unreadable_paths = scan_root(
                connection, root, run_id, args.max_file_bytes, args.max_text_chars
            )
            total.update(counts)
            root_summaries.append(
                {"root": str(root), **dict(counts), "unreadable_paths": unreadable_paths}
            )
        summary = {
            "schema_version": SCHEMA_VERSION,
            "visibility": "private_local",
            "complete": not bool(total["unreadable_directories"] or total["retained_unverified"] or total["unreadable"]),
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": utc_now(),
            "mode": args.mode,
            "roots": [str(root) for root in roots],
            "state_dir": str(state_dir),
            "totals": dict(total),
            "root_summaries": root_summaries,
        }
        connection.execute(
            "UPDATE scan_runs SET completed_at = ?, summary_json = ? WHERE run_id = ?",
            (summary["completed_at"], json.dumps(summary, ensure_ascii=False), run_id),
        )
        connection.commit()
        descriptor, temporary = tempfile.mkstemp(prefix=".scan-manifest-", dir=state_dir)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
            os.replace(temporary, state_dir / "scan-manifest.json")
        finally:
            Path(temporary).unlink(missing_ok=True)
        emit(summary)
        return 0
    finally:
        connection.close()


def command_scan(args: argparse.Namespace) -> int:
    # Hold the lock through schema migration, DB commit, and manifest replacement.
    try:
        roots = resolve_roots(args.mode, args.root)
        if args.max_file_bytes <= 0 or args.max_text_chars <= 0:
            raise ValueError("scan limits must be positive integers")
        state_dir = args.state_dir.expanduser().resolve()
        if any(root == state_dir or root.is_relative_to(state_dir) for root in roots):
            raise ValueError("state-dir must not equal or contain a content root")
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_lock(state_dir / ".scan.lock"):
        return _command_scan_locked(args)


def query_terms(topic: str) -> list[str]:
    topic = topic.strip().lower()
    if not topic:
        return []
    pieces = [piece for piece in re.split(r"[\s,;|/，；]+", topic) if len(piece) >= 2]
    values = [topic]
    for piece in pieces:
        if piece not in values:
            values.append(piece)
    return values[:12]


def make_snippet(text: str, terms: list[str], width: int = 420) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    position = min(positions) if positions else 0
    start = max(0, position - width // 3)
    end = min(len(text), start + width)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    return ("…" if start else "") + snippet + ("…" if end < len(text) else "")


def command_query(args: argparse.Namespace) -> int:
    terms = query_terms(args.topic)
    if not terms:
        emit({"ok": False, "error": "query requires a non-empty --topic"})
        return 2
    connection = connect_database(args.state_dir.expanduser().resolve(), readonly=True)
    rows = connection.execute(
        """
        SELECT path, title, extension, size, mtime_ns, text, extraction_status
        FROM documents
        WHERE extraction_status IN ('indexed', 'partial') AND text != ''
        """
    )
    matches: list[dict[str, Any]] = []
    for row in rows:
        title = row["title"].lower()
        path = row["path"].lower()
        text = row["text"]
        lower_text = text.lower()
        occurrences = sum(min(lower_text.count(term), 20) for term in terms)
        score = occurrences + sum(8 for term in terms if term in title) + sum(3 for term in terms if term in path)
        if score <= 0:
            continue
        matches.append(
            {
                "path": row["path"],
                "title": row["title"],
                "extension": row["extension"],
                "size": row["size"],
                "mtime_ns": row["mtime_ns"],
                "extraction_status": row["extraction_status"],
                "score": score,
                "snippet": make_snippet(text, terms),
            }
        )
    connection.close()
    matches.sort(key=lambda item: (item["score"], item["mtime_ns"]), reverse=True)
    emit({"topic": args.topic, "terms": terms, "count": len(matches), "matches": matches[: args.limit]})
    return 0


def command_discover(args: argparse.Namespace) -> int:
    connection = connect_database(args.state_dir.expanduser().resolve(), readonly=True)
    rows = connection.execute(
        """
        SELECT path, root, title, extension, size, mtime_ns, text, extraction_status
        FROM documents
        ORDER BY mtime_ns DESC
        """
    ).fetchall()
    extensions: Counter[str] = Counter()
    folders: Counter[str] = Counter()
    headings: Counter[str] = Counter()
    recent: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    for row in rows:
        statuses[row["extraction_status"]] += 1
        extensions[row["extension"] or "[no extension]"] += 1
        path = Path(row["path"])
        root = Path(row["root"])
        try:
            relative = path.relative_to(root)
            parts = relative.parts[:-1]
            if parts:
                folders["/".join(parts[:2])] += 1
        except ValueError:
            pass
        if len(recent) < args.limit and row["extraction_status"] in {"indexed", "partial"}:
            recent.append({"path": row["path"], "title": row["title"], "mtime_ns": row["mtime_ns"]})
        if row["extension"] in {".md", ".markdown"}:
            for heading in re.findall(r"(?m)^#{1,3}\s+(.{3,100})$", row["text"][:100_000]):
                cleaned = re.sub(r"\s+", " ", heading).strip()
                if cleaned:
                    headings[cleaned] += 1
    connection.close()
    emit(
        {
            "documents": len(rows),
            "statuses": statuses.most_common(),
            "extensions": extensions.most_common(args.limit),
            "folders": folders.most_common(args.limit),
            "headings": headings.most_common(args.limit),
            "recent_documents": recent,
        }
    )
    return 0


def command_stats(args: argparse.Namespace) -> int:
    connection = connect_database(args.state_dir.expanduser().resolve(), readonly=True)
    status_rows = connection.execute(
        "SELECT extraction_status, COUNT(*) AS count FROM documents GROUP BY extraction_status ORDER BY count DESC"
    ).fetchall()
    root_rows = connection.execute(
        "SELECT root, COUNT(*) AS count FROM documents GROUP BY root ORDER BY count DESC"
    ).fetchall()
    last_run = connection.execute(
        "SELECT run_id, started_at, completed_at, mode, roots_json FROM scan_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    connection.close()
    emit(
        {
            "statuses": [{"status": row["extraction_status"], "count": row["count"]} for row in status_rows],
            "roots": [{"root": row["root"], "count": row["count"]} for row in root_rows],
            "last_run": dict(last_run) if last_run else None,
        }
    )
    return 0


def validate_profile(data: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(data, dict):
        return ["profile must be a JSON object"]
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError):
        return ["profile must contain only finite JSON-compatible values"]
    schema_version = data.get("schema_version")
    if schema_version not in (PROFILE_SCHEMA_VERSION, LEGACY_PROFILE_SCHEMA_VERSION):
        failures.append(
            f"schema_version must be {PROFILE_SCHEMA_VERSION} or {LEGACY_PROFILE_SCHEMA_VERSION}"
        )
    required = {
        "generated_at", "topic", "scope", "scan_summary", "capabilities",
        "conflicts", "unknowns", "learning_start", "user_corrections", "updated_at",
    }
    if schema_version == PROFILE_SCHEMA_VERSION:
        required.add("visibility")
    failures.extend(f"missing field: {key}" for key in sorted(required - data.keys()))
    for field in ["generated_at", "topic", "updated_at"]:
        if not isinstance(data.get(field), str):
            failures.append(f"{field} must be a string")
    for field in ["conflicts", "unknowns", "user_corrections"]:
        if not isinstance(data.get(field), list):
            failures.append(f"{field} must be an array")
    scope = data.get("scope")
    if not isinstance(scope, dict) or scope.get("mode") not in tuple(SUPPORTED_MODES) or not isinstance(scope.get("roots"), list):
        failures.append("scope must contain a supported mode and roots list")
    elif schema_version == PROFILE_SCHEMA_VERSION:
        if not isinstance(scope.get("discovery_roots"), list) or not isinstance(scope.get("manifest"), str):
            failures.append("v2 scope requires discovery_roots and manifest")
    if isinstance(scope, dict):
        for field in ["roots", "discovery_roots"] if schema_version == PROFILE_SCHEMA_VERSION else ["roots"]:
            values = scope.get(field)
            if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
                failures.append(f"scope.{field} must be an array of non-empty paths")
    if schema_version == PROFILE_SCHEMA_VERSION and data.get("visibility") != "private_local":
        failures.append("v2 visibility must be private_local")
    scan_summary = data.get("scan_summary")
    if not isinstance(scan_summary, dict):
        failures.append("scan_summary must be an object")
    elif schema_version == PROFILE_SCHEMA_VERSION:
        summary_fields = {
            "files_seen", "indexed", "partial", "unsupported", "too_large",
            "sensitive", "unreadable", "unchanged", "changed", "deleted",
        }
        for key in sorted(summary_fields):
            if type(scan_summary.get(key)) is not int or scan_summary.get(key, -1) < 0:
                failures.append(f"scan_summary.{key} must be a non-negative integer")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list):
        failures.append("capabilities must be a list")
    else:
        for index, capability in enumerate(capabilities):
            label = f"capabilities[{index}]"
            if not isinstance(capability, dict):
                failures.append(f"{label} must be an object")
                continue
            for field in ["name", "judgment"]:
                if not isinstance(capability.get(field), str) or not capability[field].strip():
                    failures.append(f"{label}.{field} must be a non-empty string")
            status = capability.get("status")
            if status not in tuple(SUPPORTED_PROFILE_STATUSES):
                failures.append(f"{label}.status is invalid")
            if capability.get("confidence") not in tuple(SUPPORTED_CONFIDENCE):
                failures.append(f"{label}.confidence is invalid")
            evidence = capability.get("evidence")
            if not isinstance(evidence, list):
                failures.append(f"{label}.evidence must be a list")
            elif status != "no_evidence" and not evidence:
                failures.append(f"{label} requires evidence")
            else:
                for evidence_index, item in enumerate(evidence or []):
                    if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("path", "locator", "reason")):
                        failures.append(f"{label}.evidence[{evidence_index}] is incomplete")
                        continue
                    if schema_version == PROFILE_SCHEMA_VERSION:
                        if item.get("source_kind") not in tuple(SUPPORTED_SOURCE_KINDS):
                            failures.append(f"{label}.evidence[{evidence_index}].source_kind is invalid")
                        if item.get("authorship_confidence") not in tuple(SUPPORTED_CONFIDENCE):
                            failures.append(f"{label}.evidence[{evidence_index}].authorship_confidence is invalid")
                        if item.get("currentness") not in tuple(SUPPORTED_CURRENTNESS):
                            failures.append(f"{label}.evidence[{evidence_index}].currentness is invalid")
                if (
                    schema_version == PROFILE_SCHEMA_VERSION
                    and status in ("applied", "articulated")
                    and evidence
                    and not any(
                        isinstance(item, dict)
                        and (item.get("source_kind") in ("user_output", "process_record", "collaborative_output")
                             or item.get("source_kind") == "ai_assisted" and isinstance(item.get("user_role"), str) and item["user_role"].strip())
                        and item.get("authorship_confidence") in ("high", "medium")
                        for item in evidence
                    )
                ):
                    failures.append(f"{label}.{status} requires user-role evidence")
    learning_start = data.get("learning_start")
    learning_fields = (
        ("goal", "reason", "skipped_basics", "first_artifact", "artifact_type", "next_skill")
        if schema_version == PROFILE_SCHEMA_VERSION
        else ("goal", "reason", "skipped_basics", "first_document", "next_skill")
    )
    if not isinstance(learning_start, dict) or not all(key in learning_start for key in learning_fields):
        failures.append("learning_start is incomplete")
    elif schema_version == PROFILE_SCHEMA_VERSION and learning_start.get("artifact_type") not in tuple(SUPPORTED_ARTIFACT_TYPES):
        failures.append("learning_start.artifact_type is invalid")
    if isinstance(learning_start, dict):
        for field in learning_fields:
            value = learning_start.get(field)
            if field == "skipped_basics":
                if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                    failures.append("learning_start.skipped_basics must be an array of non-empty strings")
                elif schema_version == PROFILE_SCHEMA_VERSION and isinstance(capabilities, list):
                    supported = set()
                    for capability in capabilities:
                        if not isinstance(capability, dict) or not isinstance(capability.get("name"), str):
                            continue
                        evidence = capability.get("evidence", [])
                        paths = {item["path"] for item in evidence if isinstance(item, dict) and isinstance(item.get("path"), str)} if isinstance(evidence, list) else set()
                        if capability.get("status") == "applied" or capability.get("status") == "articulated" and len(paths) >= 2:
                            supported.add(capability["name"])
                    for item in value:
                        if item not in supported:
                            failures.append(f"skipped basic lacks applied or multisource articulated support: {item}")
            elif not isinstance(value, str):
                failures.append(f"learning_start.{field} must be a string")
    return failures


def command_validate_profile(args: argparse.Namespace) -> int:
    try:
        data = strict_json_loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        emit({"valid": False, "failures": [f"cannot read profile: {exc}"]})
        return 1
    failures = validate_profile(data)
    emit({"valid": not failures, "failures": failures})
    return 1 if failures else 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="build or update a content index")
    scan.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="current")
    scan.add_argument("--root", type=Path, action="append", default=[])
    scan.add_argument("--state-dir", type=Path, required=True)
    scan.add_argument("--max-file-bytes", type=positive_int, default=DEFAULT_MAX_FILE_BYTES)
    scan.add_argument("--max-text-chars", type=positive_int, default=DEFAULT_MAX_TEXT_CHARS)
    scan.set_defaults(func=command_scan)

    landscape = subparsers.add_parser(
        "landscape", help="rank candidate content roots from metadata without extracting content"
    )
    landscape.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="current")
    landscape.add_argument("--root", type=Path, action="append", default=[])
    landscape.add_argument("--max-depth", type=positive_int, default=4)
    landscape.add_argument("--limit", type=positive_int, default=30)
    landscape.set_defaults(func=command_landscape)

    query = subparsers.add_parser("query", help="search indexed content for a topic")
    query.add_argument("--state-dir", type=Path, required=True)
    query.add_argument("--topic", required=True)
    query.add_argument("--limit", type=positive_int, default=20)
    query.set_defaults(func=command_query)

    discover = subparsers.add_parser("discover", help="inspect indexed folders, headings, and recent documents")
    discover.add_argument("--state-dir", type=Path, required=True)
    discover.add_argument("--limit", type=positive_int, default=20)
    discover.set_defaults(func=command_discover)

    stats = subparsers.add_parser("stats", help="show index coverage and last scan")
    stats.add_argument("--state-dir", type=Path, required=True)
    stats.set_defaults(func=command_stats)

    validate = subparsers.add_parser("validate-profile", help="validate a research learning profile")
    validate.add_argument("profile", type=Path)
    validate.set_defaults(func=command_validate_profile)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        emit({"ok": False, "error": "scan interrupted"})
        return 130
    except (OSError, sqlite3.Error, ValueError) as exc:
        emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
