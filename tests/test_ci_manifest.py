import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_ci_manifest import DEFAULT_MANIFEST, load_manifest, render_argv, select_checks


class CIManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(DEFAULT_MANIFEST)

    def test_current_manifest_has_one_source_of_ci_checks(self):
        self.assertEqual(
            [check["id"] for check in self.manifest["checks"]],
            ["repository", "deterministic-tests", "full-release", "skillhub-release"],
        )

    def test_python_placeholder_uses_current_interpreter(self):
        self.assertEqual(render_argv(["{python}", "script.py"])[0], sys.executable)

    def test_unknown_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown check id"):
            select_checks(self.manifest, ["missing"])

    def test_duplicate_check_id_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["checks"].append(copy.deepcopy(manifest["checks"][0]))
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "ci-manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate check id"):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
