"""Persistence invariants; these do not simulate model routing or human consent."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/rw-research-passport/scripts/passport.py"


class MaterialHandoffTests(unittest.TestCase):
    def test_save_source_preserves_bytes_and_does_not_accept_advice(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source = folder / "revision.txt"
            original = b"Reviewer suggests separating the chapters.\n"
            source.write_bytes(original)
            digest = hashlib.sha256(original).hexdigest()
            passport = folder / "passport.json"

            def cli(*args):
                return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                      capture_output=True, text=True)

            result = cli("init", passport, "--project-id", "TEST-HANDOFF", "--title", "Isolated test")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            args = ("add-material", passport, "--id", "MAT-SOURCE", "--type", "supervisor_revision",
                    "--title", "Unaccepted advice source", "--source-pointer", source,
                    "--status", "raw", "--content-sha256", digest)
            result = cli(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(passport.read_text())
            self.assertEqual(payload["decisions"], [])
            self.assertEqual(payload["credentials"], [])
            self.assertEqual(len(payload["materials"]), 1)
            self.assertEqual(payload["materials"][0]["content_sha256"], digest)
            self.assertTrue(payload["audit_log"])
            before = passport.read_bytes()
            self.assertNotEqual(cli(*args).returncode, 0)
            self.assertEqual(passport.read_bytes(), before)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(cli("validate", passport).returncode, 0)

    def test_handoff_scenarios_remain_unexecuted_contracts(self):
        path = ROOT / "skills/rw-research-router/references/behavior-tests.json"
        cases = [c for c in json.loads(path.read_text()) if c.get("gate") == "task_handoff_v1"]
        self.assertEqual(len(cases), 8)
        for case in cases:
            self.assertEqual(case["execution_status"], "not_run")
            self.assertEqual(case["fixture_kind"], "synthetic")
            self.assertTrue(case["must_do"])
            self.assertTrue(case["must_not"])


if __name__ == "__main__":
    unittest.main()
