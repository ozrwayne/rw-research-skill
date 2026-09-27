from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "rw-claim-audit" / "scripts" / "claim_audit.py"


class ClaimAuditCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def test_verdict_gate_and_document_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            document = root / "manuscript.md"
            audit = root / "claim-audit.json"
            document.write_text("The reported value was 18%.\n", encoding="utf-8")
            self.assertEqual(0, self.run_cli("init", str(audit), "--document-id", "DOC-1", "--document-path", str(document)).returncode)
            self.assertEqual(0, self.run_cli("add-claim", str(audit), "--id", "CLM-1", "--text", "The reported value was 18%.", "--location", "Results, paragraph 1", "--claim-type", "quantitative").returncode)
            snapshot = root / "source.txt"
            snapshot.write_text("The reported value was 18%.", encoding="utf-8")
            updated = self.run_cli(
                "set-verdict", str(audit), "--claim-id", "CLM-1", "--verdict", "VERIFIED",
                "--source-id", "SRC-1", "--source-pointer", str(snapshot), "--locator", "p. 4, Results",
                "--support-note", "Value and population match.",
            )
            self.assertEqual(0, updated.returncode, updated.stdout + updated.stderr)
            self.assertEqual(0, self.run_cli("gate", str(audit)).returncode)
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual("VERIFIED", payload["claims"][0]["verdict"])
            document.write_text("The reported value was 20%.\n", encoding="utf-8")
            drifted = self.run_cli("validate", str(audit))
            self.assertEqual(2, drifted.returncode)
            self.assertIn("document_hash does not match", drifted.stdout)


if __name__ == "__main__":
    unittest.main()
