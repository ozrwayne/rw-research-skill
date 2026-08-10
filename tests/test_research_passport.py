from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "rw-research-passport" / "scripts" / "passport.py"


class ResearchPassportCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False)

    def test_material_registration_and_missing_handoff_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            passport = Path(temp_dir) / "passport.json"
            self.assertEqual(0, self.run_cli("init", str(passport), "--project-id", "PROJECT-1", "--title", "Trial project").returncode)
            added = self.run_cli(
                "add-material", str(passport), "--id", "MAT-1", "--type", "paper",
                "--title", "Paper one", "--source-pointer", "doi:10.1000/example", "--status", "verified",
            )
            self.assertEqual(0, added.returncode, added.stdout + added.stderr)
            self.assertEqual(0, self.run_cli("validate", str(passport)).returncode)
            payload = json.loads(passport.read_text(encoding="utf-8"))
            payload["handoffs"].append({
                "id": "HANDOFF-1", "from_stage": "discovery", "to_stage": "extraction",
                "material_ids": ["MAT-MISSING"], "status": "prepared", "recorded_at": payload["updated_at"],
            })
            passport.write_text(json.dumps(payload), encoding="utf-8")
            invalid = self.run_cli("validate", str(passport))
            self.assertEqual(2, invalid.returncode)
            self.assertIn("references missing material", invalid.stdout)

    def test_material_hash_and_supersedes_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            passport = Path(temp_dir) / "passport.json"
            self.assertEqual(0, self.run_cli("init", str(passport), "--project-id", "PROJECT-2", "--title", "Version test").returncode)
            first = self.run_cli(
                "add-material", str(passport), "--id", "MAT-1", "--type", "paper",
                "--title", "Version one", "--source-pointer", "source:v1", "--status", "superseded",
                "--content-sha256", "a" * 64,
            )
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            second = self.run_cli(
                "add-material", str(passport), "--id", "MAT-2", "--type", "paper",
                "--title", "Version two", "--source-pointer", "source:v2", "--status", "raw",
                "--content-sha256", "b" * 64, "--supersedes-id", "MAT-1",
            )
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            payload = json.loads(passport.read_text(encoding="utf-8"))
            self.assertEqual("MAT-1", payload["materials"][1]["supersedes_id"])

            invalid = self.run_cli(
                "add-material", str(passport), "--id", "MAT-3", "--type", "paper",
                "--title", "Bad hash", "--source-pointer", "source:v3", "--content-sha256", "not-a-hash",
            )
            self.assertEqual(2, invalid.returncode)
            self.assertIn("64-character hexadecimal", invalid.stdout)

    def test_record_credential_and_detect_changed_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            passport = Path(temp_dir) / "passport.json"
            self.assertEqual(0, self.run_cli("init", str(passport), "--project-id", "PROJECT-3", "--title", "Credential test").returncode)
            recorded = self.run_cli(
                "record-credential", str(passport), "--credential-id", "RCRED-1",
                "--decision-id", "DEC-1", "--statement", "Use the agreed scope",
                "--status", "confirmed", "--session-id", "SESSION-1",
                "--record-pointer", "notes:SESSION-1", "--settled-by", "human:HUMAN-ID",
                "--authority", "human_confirmed", "--basis", "reasoning", "--scope", "PROJECT-3",
            )
            self.assertEqual(0, recorded.returncode, recorded.stdout + recorded.stderr)
            payload = json.loads(passport.read_text(encoding="utf-8"))
            self.assertEqual("RCRED-1", payload["decisions"][0]["credential_id"])
            self.assertTrue(payload["credentials"][0]["content_hash"].startswith("sha256:"))

            payload["credentials"][0]["scope"] = "OTHER-PROJECT"
            passport.write_text(json.dumps(payload), encoding="utf-8")
            invalid = self.run_cli("validate", str(passport))
            self.assertEqual(2, invalid.returncode)
            self.assertIn("content_hash does not match", invalid.stdout)

    def test_human_confirmation_requires_human_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            passport = Path(temp_dir) / "passport.json"
            self.assertEqual(0, self.run_cli("init", str(passport), "--project-id", "PROJECT-4", "--title", "Authority test").returncode)
            invalid = self.run_cli(
                "record-credential", str(passport), "--credential-id", "RCRED-1",
                "--decision-id", "DEC-1", "--statement", "Use the agreed scope",
                "--status", "confirmed", "--session-id", "SESSION-1",
                "--record-pointer", "notes:SESSION-1", "--settled-by", "agent:RESEARCH-1",
                "--authority", "human_confirmed", "--basis", "reasoning", "--scope", "PROJECT-4",
            )
            self.assertEqual(2, invalid.returncode)
            self.assertIn("human_confirmed requires a human: identifier", invalid.stdout)


if __name__ == "__main__":
    unittest.main()
