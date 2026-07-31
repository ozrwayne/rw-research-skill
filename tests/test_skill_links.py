import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.check_skill_links import validate_skill_links


ROOT = Path(__file__).resolve().parents[1]
MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


class SkillLinkTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_current_structured_handoffs_are_in_manifest(self):
        self.assertEqual(validate_skill_links(self.manifest), [])

    def test_unknown_handoff_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills_root = root / "skills" / "example"
            skills_root.mkdir(parents=True)
            (skills_root / "cases.md").write_text("- 下一步：rw-not-in-package。\n", encoding="utf-8")
            failures = validate_skill_links(manifest, root)
        self.assertTrue(any("rw-not-in-package" in failure for failure in failures))

    def test_unknown_expected_next_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills_root = root / "skills" / "example"
            skills_root.mkdir(parents=True)
            (skills_root / "behavior-tests.json").write_text(
                json.dumps([{"expected_next": ["rw-not-in-package"]}]),
                encoding="utf-8",
            )
            failures = validate_skill_links(manifest, root)
        self.assertTrue(any("rw-not-in-package" in failure for failure in failures))

    def test_mmd_file_matches_the_markdown_mermaid_block(self):
        markdown = (ROOT / "docs" / "skill-link-map.md").read_text(encoding="utf-8")
        mmd = (ROOT / "docs" / "skill-link-map.mmd").read_text(encoding="utf-8")
        match = MERMAID_BLOCK.search(markdown)
        self.assertIsNotNone(match, "docs/skill-link-map.md must contain a ```mermaid block")
        self.assertEqual(
            match.group(1).strip(),
            mmd.strip(),
            "docs/skill-link-map.mmd has drifted from the mermaid block in docs/skill-link-map.md",
        )


if __name__ == "__main__":
    unittest.main()
