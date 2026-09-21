from __future__ import annotations

import argparse
import copy
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import build_skillhub_release, check_repository, cross_model_eval
from scripts.check_public_privacy import scan_file
from scripts.package_safety import atomic_zip, load_metadata, publish_directory, regular_files, safe_name
from scripts.sync_from_workspace import SYNTHETIC_NOTICE, sanitize_public_skill, sync


class PackageSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)

    def write(self, relative, content="fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def sync_fixture(self, names=("rw-a", "rw-b")):
        plugin = self.root / "plugin"
        self.write("plugin/manifest.json", json.dumps({"skills": list(names)}))
        self.write("plugin/skills/rw-a/SKILL.md", "old")
        self.write("plugin/skills/rw-extra/SKILL.md", "keep")
        for name in names:
            self.write(f"source/{name}/SKILL.md", "new")
        return plugin, self.root / "source"

    def test_unsafe_names_rejected(self):
        for name in ("../rw-a", "/absolute", "a/b", "a\\b", ".", "a\n", "", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)

    def test_sync_missing_source_preserves_all_existing_data(self):
        plugin, source = self.sync_fixture()
        (source / "rw-b/SKILL.md").unlink()
        with self.assertRaises(ValueError):
            sync(plugin, source, [], prune=True)
        self.assertEqual((plugin / "skills/rw-a/SKILL.md").read_text(), "old")
        self.assertTrue((plugin / "skills/rw-extra/SKILL.md").exists())

    def test_sync_sanitization_failure_preserves_existing_data(self):
        plugin, source = self.sync_fixture()
        self.write("source/rw-b/references/atoms.jsonl", "not json")
        with self.assertRaises(ValueError):
            sync(plugin, source, [], prune=True)
        self.assertEqual((plugin / "skills/rw-a/SKILL.md").read_text(), "old")
        self.assertTrue((plugin / "skills/rw-extra/SKILL.md").exists())

    def test_sync_default_preserves_extra_and_only_preserves_other_skill(self):
        plugin, source = self.sync_fixture()
        sync(plugin, source, ["rw-a"])
        self.assertTrue((plugin / "skills/rw-extra/SKILL.md").exists())
        self.assertFalse((plugin / "skills/rw-b").exists())
        self.assertEqual((plugin / "skills/rw-a/SKILL.md").read_text(), "new")

    def test_sync_dry_run_validates_without_modification(self):
        plugin, source = self.sync_fixture()
        result = sync(plugin, source, [], dry_run=True, prune=True)
        self.assertEqual(result["delete"], ["rw-extra"])
        self.assertEqual((plugin / "skills/rw-a/SKILL.md").read_text(), "old")
        self.assertTrue((plugin / "skills/rw-extra/SKILL.md").exists())

    def test_sync_rejects_path_traversal_and_symlinks(self):
        plugin, source = self.sync_fixture()
        self.write("plugin/manifest.json", json.dumps({"skills": ["../source"]}))
        with self.assertRaises(ValueError):
            sync(plugin, source, [])
        self.write("plugin/manifest.json", json.dumps({"skills": ["rw-a"]}))
        (source / "rw-a/link").symlink_to(self.write("private.txt"))
        with self.assertRaises(ValueError):
            sync(plugin, source, [])

    def test_sanitizer_never_relabels_unreviewed_fixture(self):
        skill = self.root / "source/rw-a"
        contract = self.write("source/rw-a/references/behavior-tests.json", '[{"id":"fixture"}]')
        with self.assertRaisesRegex(ValueError, "reviewed synthetic"):
            sanitize_public_skill(skill)
        self.assertEqual(json.loads(contract.read_text()), [{"id": "fixture"}])

    def test_one_line_case_notice_fails_without_crash_or_relabel(self):
        self.write("source/rw-a/references/cases.md", "# Cases")
        with self.assertRaisesRegex(ValueError, "reviewed synthetic"):
            sanitize_public_skill(self.root / "source/rw-a")

    def test_publish_rollback_on_second_rename_failure(self):
        old = self.write("target/data", "old").parent
        staged = self.write("staged/data", "new").parent
        import os
        real_replace = os.replace
        def fail_staged(source, target):
            if Path(source) == staged:
                raise OSError("simulated publish failure")
            return real_replace(source, target)
        with patch("scripts.package_safety.os.replace", side_effect=fail_staged), self.assertRaises(OSError):
            publish_directory(staged, old)
        self.assertEqual((old / "data").read_text(), "old")

    def test_archive_rejects_symlink_and_path_traversal(self):
        source = self.write("source.txt")
        link = self.root / "link"
        link.symlink_to(source)
        for members in ([(link, "data")], [(source, "../data")], [(source, "a\\b")]):
            with self.subTest(members=members), self.assertRaises(ValueError):
                atomic_zip(self.root / "out.zip", members)
        self.assertFalse((self.root / "out.zip").exists())

    def test_archive_write_failure_keeps_previous_archive(self):
        source = self.write("source.txt")
        output = self.write("out.zip", "old archive")
        with patch.object(zipfile.ZipFile, "write", side_effect=OSError("write failed")), self.assertRaises(OSError):
            atomic_zip(output, [(source, "data")])
        self.assertEqual(output.read_text(), "old archive")

    def test_archive_output_parent_symlink_rejected(self):
        source = self.write("source.txt")
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "dist").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            atomic_zip(self.root / "dist/out.zip", [(source, "data")])
        self.assertEqual(list(outside.iterdir()), [])

    def test_privacy_decodes_all_json_values_and_keys(self):
        path = self.write("private.json", '{"note":"\\u002fUsers\\u002falice\\u002fprivate", "alice\\u0040example.com": "x"}')
        failures = []
        scan_file(path, "private.json", failures)
        self.assertTrue(any("macOS user path" in item for item in failures))
        self.assertTrue(any("email address" in item for item in failures))

    def test_privacy_no_suffix_bypass_and_binary_is_not_silent(self):
        path = self.write("fake.PNG", "Contact: alice@example.com")
        failures = []
        scan_file(path, path.name, failures)
        self.assertTrue(failures)
        path.write_bytes(b"\x89\xff")
        failures = []
        scan_file(path, path.name, failures)
        self.assertTrue(any("unscannable" in item for item in failures))

    def test_privacy_linux_windows_volume_and_encoded_paths(self):
        for text in ("/home/alice/secret", "C:/Users/alice/secret", "/Volumes/PRIVATE/secret", "%2FUsers%2Falice%2Fsecret"):
            with self.subTest(text=text):
                failures = []
                scan_file(self.write("data.txt", text), "data.txt", failures)
                self.assertTrue(failures)

    def test_repository_subcheck_cannot_hide_failure(self):
        for code, stdout in ((1, '{"failures": []}'), (0, "not json"), (0, "[]"), (0, '{"failures":["bad"]}')):
            with self.subTest(code=code, stdout=stdout):
                failures = []
                with patch("scripts.check_repository.subprocess.run", return_value=subprocess.CompletedProcess([], code, stdout, "error")):
                    check_repository.run_json_check(["fixture"], "fixture", failures)
                self.assertTrue(failures)

    def test_reviewed_synthetic_fixture_remains_valid(self):
        self.write("source/rw-a/references/behavior-tests.json", '[{"fixture_kind":"synthetic"}]')
        self.write("source/rw-a/references/cases.md", '# Cases\n\n' + SYNTHETIC_NOTICE)
        sanitize_public_skill(self.root / "source/rw-a")

    def test_compact_package_remaps_runnable_paths_and_reference_anchors(self):
        skill = self.root / "rw-a"
        self.write("rw-a/references/method.md", "Method")
        self.write("rw-a/scripts/run.py", "print('fixture')")
        self.write("rw-a/assets/template.json", "{}")
        text = "Read references/method.md\npython3 scripts/run.py assets/template.json\n- python3 scripts/self_check.py passed"
        compact = build_skillhub_release.compact_paths(text, skill)
        self.assertIn("modules/rw-a.md#ref-method-md", compact)
        self.assertIn("python3 tools/rw-a/run.py templates/rw-a/template.json", compact)
        self.assertNotIn("scripts/self_check.py", compact)

    def test_metadata_rejects_unsafe_package_name_and_version(self):
        self.write("manifest.json", json.dumps({"name": "../escape", "version": "1.0.0", "skills": ["rw-a"]}))
        self.write("VERSION", "1.0.0")
        self.write(".codex-plugin/plugin.json", '{"version":"1.0.0"}')
        with self.assertRaises(ValueError):
            load_metadata(self.root)
        self.write("manifest.json", json.dumps({"name": "rw-test", "version": "../bad", "skills": ["rw-a"]}))
        self.write("VERSION", "../bad")
        with self.assertRaises(ValueError):
            load_metadata(self.root)



class CrossModelIntegrityTests(unittest.TestCase):
    def matrix(self):
        models = [{"id": "a", "provider": "codex"}, {"id": "b", "provider": "codex"}, {"id": "c", "provider": "claude"}]
        records = [{"model_id": model["id"], "provider": model["provider"], "fixture_id": "fixture", "condition": condition,
                    "repetition": 1, "error": None, "scoring": {"passed": True, "score": 1.0}}
                   for model in models for condition in ("with_skill", "without_skill")]
        return {"models": models, "fixture_ids": ["fixture"], "repetitions": 1, "finished_at": "fixture-complete", "records": records}

    def test_complete_matrix_can_pass(self):
        self.assertEqual(cross_model_eval.summarize(self.matrix())["status"], "CROSS_MODEL_VERIFIED")

    def test_incomplete_or_duplicate_matrix_never_verified(self):
        for kind in ("missing_baseline", "unfinished", "duplicate", "missing_fixture"):
            data = self.matrix()
            if kind == "missing_baseline":
                data["records"] = [r for r in data["records"] if r["condition"] == "with_skill"]
            elif kind == "unfinished":
                data["finished_at"] = None
            elif kind == "duplicate":
                data["records"].append(data["records"][0])
            else:
                data["fixture_ids"].append("missing")
            with self.subTest(kind=kind):
                self.assertEqual(cross_model_eval.summarize(data)["status"], "CROSS_MODEL_NOT_VERIFIED")

    def test_empty_checks_do_not_pass(self):
        self.assertFalse(cross_model_eval.score_response({}, [])["passed"])
        self.assertTrue(cross_model_eval.validate_inputs([], []))

    def test_schema_missing_type_extra_fields_rejected(self):
        schema = {"type": "object", "properties": {"value": {"type": "number"}}, "required": ["value"], "additionalProperties": False}
        for value in ({}, {"value": True}, {"value": "1"}, {"value": 1, "extra": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cross_model_eval.validate_schema(value, schema)

    def test_run_path_escape_rejected_before_any_provider_access(self):
        args = argparse.Namespace(run_id="../escape", repetitions=1, workers=1, timeout=1)
        with patch.object(cross_model_eval, "provider_preflight", side_effect=AssertionError("provider accessed")):
            self.assertEqual(cross_model_eval.command_run(args), 2)
