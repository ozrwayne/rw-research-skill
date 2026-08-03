#!/usr/bin/env python3
"""Exercise the public submission-packet commands with synthetic data."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "submission_packet.py"


class SubmissionPacketTest(unittest.TestCase):
    def test_init_validate_and_portal_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            packet = Path(temporary_directory) / "packet.json"
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-001", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            recorded = subprocess.run(
                ["python3", str(SCRIPT), "record-portal-check", str(packet), "--system", "ScholarOne", "--step", "Authors & Institutions", "--status", "incomplete", "--error", "Corresponding author is required"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            validated = subprocess.run(["python3", str(SCRIPT), "validate", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            summary = subprocess.run(["python3", str(SCRIPT), "summary", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_data = json.loads(summary.stdout)
            self.assertEqual(summary_data["incomplete_portal_steps"], ["Authors & Institutions"])
            self.assertEqual(summary_data["final_submission"]["state"], "not_submitted")

    def test_record_user_confirmed_submission_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            packet = Path(temporary_directory) / "packet.json"
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-002", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            missing_evidence = subprocess.run(
                ["python3", str(SCRIPT), "record-submission-result", str(packet), "--state", "submitted", "--agent-observation", "not_observed"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(missing_evidence.returncode, 0)
            recorded = subprocess.run(
                ["python3", str(SCRIPT), "record-submission-result", str(packet), "--state", "submitted", "--evidence-source", "user_confirmation", "--agent-observation", "not_observed", "--recorded-at", "2026-08-03T01:30:00Z"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            payload = json.loads(packet.read_text(encoding="utf-8"))
            self.assertEqual(payload["portal"]["final_submission"]["state"], "submitted")
            self.assertEqual(payload["portal"]["final_submission"]["evidence"]["source"], "user_confirmation")
            self.assertEqual(payload["portal"]["final_submission"]["agent_observation"], "not_observed")
            self.assertEqual(payload["audit_log"][-1]["action"], "submission_result_recorded")
            self.assertEqual(payload["updated_at"], "2026-08-03T01:30:00Z")

    def test_record_platform_receipt_submission_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            packet = Path(temporary_directory) / "packet.json"
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-003", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            recorded = subprocess.run(
                ["python3", str(SCRIPT), "record-submission-result", str(packet), "--state", "submitted", "--evidence-source", "platform_receipt", "--agent-observation", "observed", "--manuscript-id", "SYN-003-2026", "--recorded-at", "2026-08-03T01:31:00Z"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            summary = subprocess.run(["python3", str(SCRIPT), "summary", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(summary.returncode, 0, summary.stderr)
            final_submission = json.loads(summary.stdout)["final_submission"]
            self.assertEqual(final_submission["evidence"]["manuscript_id"], "SYN-003-2026")
            self.assertEqual(final_submission["agent_observation"], "observed")


if __name__ == "__main__":
    unittest.main()
