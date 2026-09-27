import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_skillhub_release import public_atoms, public_text
from scripts.check_public_privacy import skillhub_source_failures


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


if __name__ == "__main__":
    unittest.main()
