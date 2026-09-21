#!/usr/bin/env python3
"""Synthetic-only negative checks for submission evidence and local preflight."""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from test_submission_packet import write_docx

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("packet_audit", ROOT / "scripts/submission_packet.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class SubmissionAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "packet.json"
        self.data = json.loads((ROOT / "assets/submission-packet-template.json").read_text())
        p.atomic_write(self.path, self.data)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, p.__file__, *args], capture_output=True, text=True, cwd=self.root)

    def test_strict_json_and_nonfinite_write_preserve_previous_state(self):
        for value in ['{"x": 1, "x": 2}', '{"n": NaN}', '{"n": Infinity}', '{"n": 1e999}']:
            candidate = self.root / "malformed.json"
            candidate.write_text(value)
            with self.assertRaises(ValueError):
                p.load(candidate)
        before = self.path.read_bytes()
        self.data["extension"] = float("nan")
        self.assertTrue(p.validate(self.data))
        with self.assertRaises(ValueError):
            p.atomic_write(self.path, self.data)
        self.assertEqual(self.path.read_bytes(), before)

    def test_platform_receipt_requires_actual_locator(self):
        self.data["portal"]["final_submission"] = dict(state="submitted", agent_observation="observed", evidence=dict(source="platform_receipt", recorded_at=p.now(), manuscript_id="", receipt_reference=""))
        self.assertTrue(any("requires manuscript_id" in item for item in p.validate(self.data)))
        self.data["portal"]["final_submission"]["evidence"]["receipt_reference"] = "receipt:SYN"
        self.assertEqual(p.validate(self.data), [])

    def test_non_submitted_state_cannot_retain_submission_evidence(self):
        self.data["portal"]["final_submission"] = dict(state="not_submitted", agent_observation="observed", evidence=dict(source="platform_receipt", recorded_at=p.now(), manuscript_id="SYN", receipt_reference=""))
        self.assertTrue(p.validate(self.data))

    def test_verified_proof_requires_consistent_observation_and_evidence(self):
        valid = dict(state="reviewed", text_check="passed", visual_check="agent_verified", checked_at=p.now(), evidence_source="proof:SYN", agent_observation="observed")
        for field, value in [("state", "not_generated"), ("text_check", "failed"), ("agent_observation", "not_observed"), ("evidence_source", ""), ("checked_at", "not-a-date")]:
            self.data["portal"]["proof"] = dict(valid, **{field: value})
            self.assertTrue(p.validate(self.data), field)
        self.data["portal"]["proof"] = valid
        self.assertEqual(p.validate(self.data), [])

    def test_complete_portal_step_cannot_keep_errors_or_duplicate_names(self):
        self.data["portal"]["steps"] = [dict(name="Authors", status="complete", errors=["Missing author"])]
        self.assertTrue(p.validate(self.data))
        self.data["portal"]["steps"] = [dict(name="Authors", status="complete", errors=[])] * 2
        self.assertTrue(p.validate(self.data))

    def test_confirmed_author_fields_require_values(self):
        self.data["authors"] = [dict(id="A", name="Synthetic", status="confirmed", email={"status": "confirmed"}, corresponding_author=dict(status="confirmed", value="yes"), credit_roles=dict(status="confirmed", value=[]))]
        errors = p.validate(self.data)
        self.assertEqual(len(errors), 3, errors)

    def test_return_resolve_requires_chronology_and_is_not_rewritable(self):
        result = self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "returned", "--reason", "Synthetic correction", "--recorded-at", "2026-01-02T00:00:00Z")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before = self.path.read_bytes()
        result = self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "resolved", "--resolution", "Synthetic fix", "--evidence", "portal-save:SYN", "--recorded-at", "2026-01-01T00:00:00Z")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.path.read_bytes(), before)
        result = self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "resolved", "--resolution", "Synthetic fix", "--evidence", "portal-save:SYN")
        self.assertEqual(result.returncode, 0)
        data = p.load(self.path)
        self.assertEqual(data["audit_log"][-1]["previous"]["state"], "returned")
        before = self.path.read_bytes()
        result = self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "resolved", "--resolution", "Overwrite")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_resolved_return_requires_saved_correction_evidence(self):
        self.assertEqual(self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "returned", "--reason", "Synthetic").returncode, 0)
        before = self.path.read_bytes()
        result = self.run_cli("record-return", str(self.path), "--return-id", "R", "--state", "resolved", "--resolution", "Claimed fixed")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, self.path.read_bytes())

    def test_result_history_preserves_prior_receipt(self):
        result = self.run_cli("record-submission-result", str(self.path), "--state", "submitted", "--evidence-source", "platform_receipt", "--agent-observation", "observed", "--receipt-reference", "receipt:SYN")
        self.assertEqual(result.returncode, 0)
        result = self.run_cli("record-submission-result", str(self.path), "--state", "submitted", "--evidence-source", "user_confirmation", "--agent-observation", "not_observed")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(p.load(self.path)["audit_log"][-1]["previous"]["evidence"]["receipt_reference"], "receipt:SYN")

    def display_fixture(self):
        write_docx(self.root / "main.docx", "See Figure 1.")
        (self.root / "figure.pdf").write_bytes(b"synthetic figure")
        self.data["materials"] = [dict(id="M", status="confirmed", path="main.docx"), dict(id="F", status="confirmed", path="figure.pdf")]
        self.data["display_policy"] = dict(separate_files_required=True, numbering_policy="separate_sequences", main_manuscript_embeds="forbidden", main_material_id="M")
        self.data["display_items"] = [dict(id="F1", kind="figure", number=1, body_reference="Figure 1", material_id="F", upload_order=2, status="confirmed")]

    def test_preflight_checks_main_hash_and_confirmed_status(self):
        self.display_fixture()
        self.assertEqual(p.display_preflight(self.data, self.root)[0], [])
        self.data["materials"][0]["sha256"] = "0" * 64
        self.assertTrue(any("main manuscript file hash" in item for item in p.display_preflight(self.data, self.root)[0]))
        self.data["materials"][0].pop("sha256")
        self.data["materials"][1]["status"] = "missing"
        self.assertTrue(any("must be confirmed" in item for item in p.display_preflight(self.data, self.root)[0]))

    def test_standalone_must_not_alias_main_and_boolean_number_fails(self):
        self.display_fixture()
        self.data["materials"][1]["path"] = "main.docx"
        self.assertTrue(any("distinct" in item for item in p.display_preflight(self.data, self.root)[0]))
        self.data["display_items"][0]["number"] = True
        self.assertTrue(p.validate(self.data))

    def test_hardlinked_main_is_not_a_distinct_standalone_file(self):
        self.display_fixture()
        alias = self.root / "main-alias.docx"
        os.link(self.root / "main.docx", alias)
        self.data["materials"][1]["path"] = alias.name
        self.assertTrue(any("hard link" in item for item in p.display_preflight(self.data, self.root)[0]))

    def test_relative_paths_and_split_word_runs(self):
        self.display_fixture()
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>See Fig</w:t></w:r><w:r><w:t>ure 1.</w:t></w:r></w:p></w:body></w:document>'
        with zipfile.ZipFile(self.root / "main.docx", "w") as archive:
            archive.writestr("word/document.xml", xml)
        p.atomic_write(self.path, self.data)
        result = subprocess.run([sys.executable, p.__file__, "preflight-display-items", str(self.path)], cwd=self.root.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_malformed_xml_is_reported_without_traceback(self):
        self.display_fixture()
        with zipfile.ZipFile(self.root / "main.docx", "w") as archive:
            archive.writestr("word/document.xml", "<broken>")
        p.atomic_write(self.path, self.data)
        result = self.run_cli("preflight-display-items", str(self.path))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_enum_values_and_missing_final_state_are_rejected(self):
        for keys, field in [((), "schema_version"), (("portal", "proof"), "state"), (("portal", "final_submission"), "state"), (("display_policy",), "numbering_policy")]:
            for value in [[], {}]:
                data = copy.deepcopy(self.data)
                node = data
                for key in keys:
                    node = node[key]
                node[field] = value
                self.assertTrue(p.validate(data))
        self.data["portal"].pop("final_submission")
        self.assertTrue(p.validate(self.data))


if __name__ == "__main__":
    unittest.main()
