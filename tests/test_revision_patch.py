from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "rw-revision-patch" / "scripts" / "revision_patch.py"


class RevisionPatchCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def test_one_of_five_blocks_and_stale_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "draft.md"
            anchored = root / "draft.anchored.md"
            manifest_path = root / "draft.manifest.json"
            patch_path = root / "revision.patch.json"
            revised = root / "draft.revised.md"
            report_path = root / "revision.report.json"
            source.write_text("\n\n".join(f"Paragraph {index}." for index in range(1, 6)) + "\n", encoding="utf-8")
            anchored_result = self.run_cli("anchor", str(source), "--output", str(anchored), "--manifest", str(manifest_path))
            self.assertEqual(0, anchored_result.returncode, anchored_result.stdout + anchored_result.stderr)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            patch = {
                "schema_version": "rw-revision-patch/v1",
                "base_document_hash": manifest["base_document_hash"],
                "operations": [{
                    "op": "replace",
                    "block_id": "B0003",
                    "expected_hash": manifest["blocks"][2]["block_hash"],
                    "new_text": "Paragraph 3 revised.",
                    "reason": "Approved correction.",
                    "issue_ids": ["ISSUE-1"],
                }],
            }
            patch_path.write_text(json.dumps(patch), encoding="utf-8")
            applied = self.run_cli("apply", str(anchored), "--manifest", str(manifest_path), "--patch", str(patch_path), "--confirm-patch-sha256", hashlib.sha256(patch_path.read_bytes()).hexdigest(), "--output", str(revised), "--report", str(report_path))
            self.assertEqual(0, applied.returncode, applied.stdout + applied.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(1, report["changed_blocks"])
            self.assertEqual(4, report["preserved_blocks"])
            self.assertEqual(0.8, report["preserved_ratio"])
            anchored.write_text(anchored.read_text(encoding="utf-8") + "\nChanged after approval.\n", encoding="utf-8")
            stale = self.run_cli("check", str(anchored), "--manifest", str(manifest_path), "--patch", str(patch_path))
            self.assertEqual(2, stale.returncode)
            self.assertIn("base_document_hash does not match", stale.stdout)


if __name__ == "__main__":
    unittest.main()
