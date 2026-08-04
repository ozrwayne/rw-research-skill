#!/usr/bin/env python3
"""Exercise the public submission-packet commands with synthetic data."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "submission_packet.py"


def write_docx(path: Path, text: str, *, include_table: bool = False) -> None:
    table = "<w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>" if include_table else ""
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p>{table}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


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

    def test_display_preflight_rejects_embedded_main_table_then_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            packet = directory / "packet.json"
            main = directory / "main.docx"
            figure = directory / "figure-1.pdf"
            table = directory / "table-1.docx"
            write_docx(main, "See Figure 1 and Table 1.", include_table=True)
            figure.write_bytes(b"synthetic figure")
            write_docx(table, "Table 1")
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-004", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            payload = json.loads(packet.read_text(encoding="utf-8"))
            payload["materials"] = [
                {"id": "main", "status": "confirmed", "path": str(main)},
                {"id": "figure-1-file", "status": "confirmed", "path": str(figure)},
                {"id": "table-1-file", "status": "confirmed", "path": str(table)},
            ]
            payload["display_policy"] = {
                "separate_files_required": True,
                "numbering_policy": "separate_sequences",
                "main_manuscript_embeds": "forbidden",
                "main_material_id": "main",
            }
            payload["display_items"] = [
                {"id": "figure-1", "kind": "figure", "number": 1, "body_reference": "Figure 1", "material_id": "figure-1-file", "upload_order": 2, "status": "confirmed"},
                {"id": "table-1", "kind": "table", "number": 1, "body_reference": "Table 1", "material_id": "table-1-file", "upload_order": 3, "status": "confirmed"},
            ]
            packet.write_text(json.dumps(payload), encoding="utf-8")
            failed = subprocess.run(["python3", str(SCRIPT), "preflight-display-items", str(packet)], text=True, capture_output=True, check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("embedded tables", failed.stdout)
            write_docx(main, "See Figure 1 and Table 1.")
            passed = subprocess.run(["python3", str(SCRIPT), "preflight-display-items", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(json.loads(passed.stdout)["main_manuscript"]["tables"], 0)

    def test_display_numbering_proof_and_return_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            packet = Path(temporary_directory) / "packet.json"
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-005", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            payload = json.loads(packet.read_text(encoding="utf-8"))
            payload["materials"] = [
                {"id": "figure-1-file", "status": "confirmed"},
                {"id": "table-file", "status": "confirmed"},
                {"id": "figure-3-file", "status": "confirmed"},
            ]
            payload["display_policy"]["separate_files_required"] = True
            payload["display_policy"]["main_manuscript_embeds"] = "forbidden"
            payload["display_items"] = [
                {"id": "figure-1", "kind": "figure", "number": 1, "body_reference": "Figure 1", "material_id": "figure-1-file", "upload_order": 2, "status": "confirmed"},
                {"id": "table-2", "kind": "table", "number": 2, "body_reference": "Table 2", "material_id": "table-file", "upload_order": 3, "status": "confirmed"},
                {"id": "figure-3", "kind": "figure", "number": 3, "body_reference": "Figure 3", "material_id": "figure-3-file", "upload_order": 4, "status": "confirmed"},
            ]
            packet.write_text(json.dumps(payload), encoding="utf-8")
            invalid = subprocess.run(["python3", str(SCRIPT), "validate", str(packet)], text=True, capture_output=True, check=False)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("table numbers must be consecutive from 1", invalid.stdout)
            self.assertIn("figure numbers must be consecutive from 1", invalid.stdout)
            payload["display_items"][1]["id"] = "table-1"
            payload["display_items"][1]["number"] = 1
            payload["display_items"][1]["body_reference"] = "Table 1"
            payload["display_items"][2]["id"] = "figure-2"
            payload["display_items"][2]["number"] = 2
            payload["display_items"][2]["body_reference"] = "Figure 2"
            packet.write_text(json.dumps(payload), encoding="utf-8")
            proof = subprocess.run(
                ["python3", str(SCRIPT), "record-proof-check", str(packet), "--state", "opened", "--text-check", "not_available", "--visual-check", "needs_human_visual_check", "--agent-observation", "observed"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proof.returncode, 0, proof.stderr)
            returned = subprocess.run(
                ["python3", str(SCRIPT), "record-return", str(packet), "--return-id", "return-1", "--state", "returned", "--reason", "Upload figures and tables separately"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(returned.returncode, 0, returned.stderr)
            resolved = subprocess.run(
                ["python3", str(SCRIPT), "record-return", str(packet), "--return-id", "return-1", "--state", "resolved", "--resolution", "Replaced the main file and standalone files"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(resolved.returncode, 0, resolved.stderr)
            summary = subprocess.run(["python3", str(SCRIPT), "summary", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_data = json.loads(summary.stdout)
            self.assertEqual(summary_data["proof"]["visual_check"], "needs_human_visual_check")
            self.assertEqual(summary_data["return_events"][0]["state"], "resolved")

    def test_legacy_v1_packet_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            packet = Path(temporary_directory) / "packet.json"
            init = subprocess.run(
                ["python3", str(SCRIPT), "init", str(packet), "--submission-id", "SYN-006", "--title", "Synthetic review", "--journal", "Synthetic Journal", "--platform", "ScholarOne"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(init.returncode, 0, init.stderr)
            payload = json.loads(packet.read_text(encoding="utf-8"))
            payload["schema_version"] = "rw-journal-submission/submission-packet/v1"
            payload.pop("display_policy")
            payload.pop("display_items")
            payload["portal"].pop("proof")
            payload["portal"].pop("return_events")
            packet.write_text(json.dumps(payload), encoding="utf-8")
            validated = subprocess.run(["python3", str(SCRIPT), "validate", str(packet)], text=True, capture_output=True, check=False)
            self.assertEqual(validated.returncode, 0, validated.stderr)


if __name__ == "__main__":
    unittest.main()
