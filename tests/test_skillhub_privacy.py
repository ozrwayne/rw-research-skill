import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_skillhub_release import public_atoms, public_text
from scripts.check_public_privacy import scan_file, skillhub_source_failures
from scripts.package_safety import PRIVACY_TERMS_ENV, load_privacy_terms


class SkillHubPrivacyTests(unittest.TestCase):
    def source_failures(self, knowledge, source="packaged_method"):
        with tempfile.TemporaryDirectory() as temporary_directory:
            skill = Path(temporary_directory).resolve() / "rw-test"
            references = skill / "references"
            references.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Test\n", encoding="utf-8")
            record = {
                "id": "TEST-001",
                "knowledge": knowledge,
                "source": source,
                "source_kind": "packaged_method",
            }
            (references / "atoms.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            return skillhub_source_failures(skill)

    def test_privacy_check_uses_skillhub_source_validation(self):
        # A visibility label is not evidence of a leak. Use actual private
        # provenance for the rejection regression instead.
        failures = self.source_failures("Derived from user-provided-supervisor-feedback-2026-07-14.")
        self.assertEqual(len(failures), 1)
        self.assertIn("private marker remains", failures[0])

    def test_local_runtime_and_visibility_labels_are_not_redacted(self):
        text = 'audit_scope="local_author_year_syntax_only"; visibility="private_local"; local file processing'
        self.assertEqual(public_text(text, Path("fixture.py")), text)
        self.assertEqual(self.source_failures(text), [])

    def test_private_user_paths_are_still_rejected(self):
        paths = (
            "/Users/EXAMPLE/research/private.md",
            "/home/EXAMPLE/research/private.md",
            "/Volumes/PRIVATE/research/private.md",
            "C:/Users/EXAMPLE/research/private.md",
            r"C:\Users\EXAMPLE\research\private.md",
        )
        for text in paths:
            with self.subTest(path=text):
                failures = self.source_failures(text)
                self.assertEqual(len(failures), 1)
                self.assertIn("private marker remains", failures[0])

    def test_private_provenance_not_ordinary_local_terms_is_rejected(self):
        for source in (
            "local_design_2026-07-13",
            "user_decision_2026-07-13_and_local_design",
            "user_preference_and_local_design_2026-07-13",
            "user-provided-supervisor-feedback-2026-07-14",
        ):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "private marker remains"):
                public_text("Knowledge copied from " + source, Path("fixture.md"))

    def test_private_source_field_still_uses_public_provenance_label(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "atoms.jsonl"
            path.write_text(json.dumps({
                "id": "TEST-001",
                "knowledge": "visibility remains private_local",
                "source": "local_design_2026-07-13",
                "source_kind": "packaged_method",
            }) + "\n", encoding="utf-8")
            record = json.loads(public_atoms(path))
        self.assertEqual(record["source"], "packaged_internal_rule")
        self.assertEqual(record["knowledge"], "visibility remains private_local")


class PrivacyTermsFileTests(unittest.TestCase):
    def terms_file(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "terms.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def public_failures(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "public.md"
            path.write_text(text, encoding="utf-8")
            failures = []
            scan_file(path, "public.md", failures)
            return failures

    def test_without_variable_only_generic_rules_run(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_privacy_terms(), (None, None))
            self.assertEqual(public_text("Written by Exampleauthor.", Path("fixture.md")), "Written by Exampleauthor.")

    def test_listed_term_is_rejected_in_skill_source(self):
        name = self.terms_file("# fixture list\nskills:exampleauthor\n")
        with patch.dict(os.environ, {PRIVACY_TERMS_ENV: name}):
            with self.assertRaisesRegex(ValueError, "private marker remains"):
                public_text("Written by Exampleauthor.", Path("fixture.md"))

    def test_unprefixed_term_is_rejected_in_public_files(self):
        name = self.terms_file("exampletopic\n")
        with patch.dict(os.environ, {PRIVACY_TERMS_ENV: name}):
            failures = self.public_failures("A study of ExampleTopic.")
        self.assertTrue(any("personal term" in item for item in failures))

    def test_skills_only_term_is_not_applied_to_public_files(self):
        name = self.terms_file("skills:exampleauthor\n")
        with patch.dict(os.environ, {PRIVACY_TERMS_ENV: name}):
            self.assertEqual(self.public_failures("Written by Exampleauthor."), [])

    def test_empty_term_list_fails_closed(self):
        name = self.terms_file("# only a comment\n\n")
        with patch.dict(os.environ, {PRIVACY_TERMS_ENV: name}):
            with self.assertRaisesRegex(ValueError, "empty term list"):
                load_privacy_terms()


if __name__ == "__main__":
    unittest.main()
