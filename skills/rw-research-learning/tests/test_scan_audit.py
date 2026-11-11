#!/usr/bin/env python3
"""Local temporary fixtures for index failure, privacy, and schema regressions."""
import copy
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("learning_audit", ROOT / "scripts/research_learning_scan.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class ScanAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.corpus = self.root / "research"
        self.corpus.mkdir()
        self.state = self.root / "state"
        self.connection = p.connect_database(self.state)
        self.addCleanup(self.connection.close)

    def scan(self, run="one", *, size=10000, chars=1000, root=None):
        return p.scan_root(self.connection, root or self.corpus, run, size, chars)

    def rows(self):
        return self.connection.execute("SELECT * FROM documents ORDER BY path").fetchall()

    def test_inaccessible_walk_retains_but_hides_stale_text_and_retries(self):
        (self.corpus / "note.md").write_text("Synthetic evidence")
        self.scan()
        def inaccessible(root, errors):
            errors.append({"path": str(root), "error": "synthetic PermissionError"})
            return iter(())
        with patch.object(p, "iter_files", inaccessible):
            counts, _ = self.scan("two")
        self.assertEqual(counts["deleted"], 0)
        self.assertEqual(counts["retained_unverified"], 1)
        row = self.rows()[0]
        self.assertEqual(row["text"], "Synthetic evidence")
        self.assertEqual(row["extraction_status"], "unreadable")
        self.assertEqual(self.scan("three")[0]["changed"], 1)
        self.assertEqual(self.rows()[0]["extraction_status"], "indexed")

    def test_true_deletion_and_parent_child_scope_changes_are_reconciled(self):
        child = self.corpus / "child"
        child.mkdir()
        note = child / "note.md"
        note.write_text("Synthetic")
        self.scan(root=child)
        note.unlink()
        counts, _ = self.scan("two")
        self.assertEqual(counts["deleted"], 1)
        self.assertEqual(self.rows(), [])

    def test_limits_reextract_unchanged_files(self):
        (self.corpus / "note.md").write_text("abcdefghij")
        self.scan(chars=4)
        self.assertEqual(self.rows()[0]["text"], "abcd")
        self.scan("two", chars=100)
        self.assertEqual(self.rows()[0]["text"], "abcdefghij")
        self.scan("three", chars=100, size=2)
        self.assertEqual(self.rows()[0]["text"], "")
        self.assertEqual(self.rows()[0]["extraction_status"], "too_large")

    def test_changed_ctime_detects_content_even_with_restored_size_and_mtime(self):
        note = self.corpus / "note.md"
        note.write_text("before")
        self.scan()
        before = note.stat()
        note.write_text("change")
        os.utime(note, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.scan("two")
        self.assertEqual(self.rows()[0]["text"], "change")

    def test_retry_unavailable_extractor_without_file_metadata_change(self):
        (self.corpus / "note.md").write_text("Synthetic")
        with patch.object(p, "extract_text", return_value=("", "unsupported", "synthetic unavailable extractor")):
            self.scan()
        self.scan("two")
        self.assertEqual(self.rows()[0]["extraction_status"], "indexed")

    def test_sensitive_policy_is_applied_before_cache_reuse(self):
        note = self.corpus / "note.md"
        note.write_text("Synthetic private fixture")
        self.scan()
        with patch.object(p, "sensitive_file", return_value=True):
            self.scan("two")
        self.assertEqual(self.rows()[0]["text"], "")
        self.assertEqual(self.rows()[0]["extraction_status"], "sensitive")

    def test_explicit_sensitive_directory_root_is_never_extracted(self):
        sensitive = self.corpus / "credentials"
        sensitive.mkdir()
        (sensitive / "harmless-name.json").write_text('{"synthetic_secret": "fixture"}')
        self.scan(root=sensitive)
        self.assertEqual(self.rows()[0]["extraction_status"], "sensitive")
        self.assertEqual(self.rows()[0]["text"], "")

    def test_index_own_state_is_excluded_even_with_nonstandard_name(self):
        (self.state / "profile.json").write_text('{"synthetic": "private"}')
        (self.root / "note.md").write_text("Synthetic research")
        self.scan(root=self.root)
        self.assertTrue(self.rows())
        self.assertFalse(any(Path(row["path"]).is_relative_to(self.state.resolve()) for row in self.rows()))

    def test_regular_file_only_and_symlinks_are_skipped(self):
        (self.corpus / "linked.md").symlink_to(self.root / "outside.md")
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.corpus / "pipe.txt")
        self.scan()
        self.assertEqual(self.rows(), [])

    def test_utf16_text_and_broken_office_xml(self):
        (self.corpus / "unicode.txt").write_text("Synthetic research", encoding="utf-16")
        with zipfile.ZipFile(self.corpus / "broken.docx", "w") as archive:
            archive.writestr("word/document.xml", "<broken>")
        self.scan()
        statuses = {Path(row["path"]).name: row["extraction_status"] for row in self.rows()}
        self.assertEqual(statuses, {"unicode.txt": "indexed", "broken.docx": "unreadable"})

    def test_truncation_preserves_multibyte_unicode(self):
        for encoding in ["utf-8", "utf-16"]:
            path = self.corpus / "unicode.txt"
            path.write_text("研究内容" * 10, encoding=encoding)
            text, status, _ = p.extract_text(path, 3)
            self.assertEqual(text, "研究内")
            self.assertEqual(status, "partial")

    def test_expanded_office_size_limit_is_enforced(self):
        file = self.corpus / "large.docx"
        with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", "<root>" + "x" * 100 + "</root>")
        with patch.object(p, "MAX_OFFICE_XML_BYTES", 64):
            text, status, reason = p.extract_text(file, 1000)
        self.assertEqual(status, "unreadable")
        self.assertIn("bounded", reason)

    def test_foreign_database_and_hardlinked_input_are_not_modified(self):
        for hardlink in [False, True]:
            state = self.root / ("linked-state" if hardlink else "foreign-state")
            state.mkdir()
            original = self.corpus / ("original.sqlite" if hardlink else "other.sqlite")
            connection = sqlite3.connect(original)
            connection.execute("CREATE TABLE important (value TEXT)")
            connection.execute("INSERT INTO important VALUES ('synthetic original')")
            connection.commit()
            connection.close()
            if hardlink:
                os.link(original, state / "index.sqlite")
            else:
                (state / "index.sqlite").write_bytes(original.read_bytes())
                original = state / "index.sqlite"
            before = original.read_bytes()
            mode = original.stat().st_mode
            with self.assertRaises(ValueError):
                p.connect_database(state)
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(original.stat().st_mode, mode)
            connection = sqlite3.connect(original)
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("important",)])
            connection.close()

    def test_read_commands_do_not_create_missing_index(self):
        for command in [["stats"], ["query", "--topic", "synthetic"], ["discover"]]:
            missing = self.root / "missing-state"
            result = subprocess.run([sys.executable, p.__file__, *command, "--state-dir", str(missing)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())
            self.assertNotIn("Traceback", result.stderr)

    def test_nonpositive_limits_fail_before_state_creation(self):
        for flag in ["--max-file-bytes", "--max-text-chars"]:
            missing = self.root / "negative-state"
            result = subprocess.run([sys.executable, p.__file__, "scan", "--root", str(self.corpus), "--state-dir", str(missing), flag, "0"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())

    def test_concurrent_cli_scans_keep_manifest_at_latest_committed_run(self):
        (self.corpus / "note.md").write_text("Synthetic evidence")
        command = [sys.executable, p.__file__, "scan", "--root", str(self.corpus), "--state-dir", str(self.state)]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        manifest = json.loads((self.state / "scan-manifest.json").read_text())
        latest = self.connection.execute("SELECT run_id FROM scan_runs ORDER BY completed_at DESC LIMIT 1").fetchone()[0]
        self.assertEqual(manifest["run_id"], latest)
        self.assertEqual(len(self.rows()), 1)

    def test_manifest_is_private_and_reports_incomplete_extraction(self):
        self.connection.close()
        (self.corpus / "broken.docx").write_bytes(b"broken")
        result = subprocess.run([sys.executable, p.__file__, "scan", "--root", str(self.corpus), "--state-dir", str(self.state)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((self.state / "scan-manifest.json").read_text())
        self.assertFalse(manifest["complete"])
        self.assertEqual(manifest["visibility"], "private_local")
        if os.name == "posix":
            self.assertEqual((self.state / "index.sqlite").stat().st_mode & 0o777, 0o600)


class ProfileAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "assets/profile-template.json").read_text())

    def capability(self, kind="unknown", status="applied"):
        return dict(name="Synthetic method", judgment="Synthetic judgment", confidence="medium", status=status, evidence=[dict(path="fixture.md", locator="section:SYN", reason="Synthetic evidence", source_kind=kind, authorship_confidence="medium", currentness="current")])

    def test_strict_profile_json_rejects_duplicates_and_nonfinite_numbers(self):
        for value in ['{"x": 1, "x": 2}', '{"n": NaN}', '{"n": Infinity}', '{"n": 1e999}']:
            with self.assertRaises(ValueError):
                p.strict_json_loads(value)
        self.data["extension"] = float("nan")
        self.assertTrue(p.validate_profile(self.data))

    def test_unknown_or_external_origin_cannot_prove_application_or_articulation(self):
        for kind in ["unknown", "external_reference", "downloaded_tool", "ai_assisted"]:
            for status in ["applied", "articulated"]:
                self.data["capabilities"] = [self.capability(kind, status)]
                self.assertTrue(p.validate_profile(self.data), (kind, status))
        self.data["capabilities"] = [self.capability("user_output")]
        self.assertEqual(p.validate_profile(self.data), [])

    def test_ai_assisted_requires_explicit_user_role(self):
        self.data["capabilities"] = [self.capability("ai_assisted")]
        self.data["capabilities"][0]["evidence"][0]["user_role"] = "User performed the synthetic analysis"
        self.assertEqual(p.validate_profile(self.data), [])

    def test_skip_basics_requires_supported_named_capability(self):
        self.data["learning_start"]["skipped_basics"] = ["Synthetic method"]
        self.data["capabilities"] = [self.capability("user_output", "exposed")]
        self.assertTrue(p.validate_profile(self.data))
        self.data["capabilities"][0]["status"] = "applied"
        self.assertEqual(p.validate_profile(self.data), [])

    def test_invalid_enum_and_array_types_never_crash(self):
        for key in ["schema_version", "scope", "conflicts", "unknowns", "user_corrections"]:
            data = copy.deepcopy(self.data)
            data[key] = [] if key in ["schema_version", "scope"] else {}
            self.assertTrue(p.validate_profile(data))
        self.data["capabilities"] = [self.capability()]
        for key in ["status", "confidence"]:
            data = copy.deepcopy(self.data)
            data["capabilities"][0][key] = []
            self.assertTrue(p.validate_profile(data))
        self.data["scan_summary"]["files_seen"] = True
        self.assertTrue(p.validate_profile(self.data))


if __name__ == "__main__":
    unittest.main()
