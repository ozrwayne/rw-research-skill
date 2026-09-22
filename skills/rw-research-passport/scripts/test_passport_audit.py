#!/usr/bin/env python3
"""Negative regression tests for state and credential integrity; synthetic only."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import passport as p


class PassportAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "passport.json"
        self.assertEqual(p.command_init(Namespace(path=str(self.path), project_id="SYN", title="Synthetic", stage="question", force=False)), 0)

    def args(self, **values):
        args = dict(path=str(self.path), credential_id="C1", decision_id="D1", statement="Synthetic choice", status="confirmed", session_id="S1", record_pointer="notes:S1", settled_by=["human:SYN"], authority="human_confirmed", basis="reasoning", scope="SYN", evidence_id=[], unknown_id=[], supersedes=None, reason="synthetic test")
        args.update(values)
        return Namespace(**args)

    def material(self, **values):
        args = dict(path=str(self.path), id="M1", type="paper", title="Synthetic material", source_pointer="notes:M1", status="verified", content_sha256=None, supersedes_id=None, reason="synthetic revision")
        args.update(values)
        return Namespace(**args)

    def test_strict_json_and_nonfinite_write_preserve_previous_state(self):
        for value in ['{"x": 1, "x": 2}', '{"n": NaN}', '{"n": Infinity}', '{"n": 1e999}']:
            candidate = self.path.parent / "malformed.json"
            candidate.write_text(value)
            with self.assertRaises(ValueError):
                p.load(candidate)
        before = self.path.read_bytes()
        data = p.load(self.path)
        data["extension"] = float("nan")
        self.assertTrue(p.validate(data))
        with self.assertRaises(ValueError):
            p.atomic_write(self.path, data)
        self.assertEqual(self.path.read_bytes(), before)

    def test_live_decision_must_match_immutable_snapshot(self):
        self.assertEqual(p.command_record_credential(self.args()), 0)
        data = p.load(self.path)
        for field, value in [("statement", "Replaced claim"), ("status", "rejected"), ("basis", "delegated_choice"), ("evidence_ids", ["MISSING"])]:
            changed = copy.deepcopy(data)
            changed["decisions"][0][field] = value
            self.assertTrue(p.validate(changed), field)

    def test_invalid_confirmers_do_not_mutate_file(self):
        for values in [dict(settled_by=["human:"]), dict(settled_by=["human:  "]), dict(settled_by=["agent:A"], authority="agent_consensus"), dict(settled_by=["human:A", "human:A"])]:
            before = self.path.read_bytes()
            self.assertEqual(p.command_record_credential(self.args(**values)), 2)
            self.assertEqual(before, self.path.read_bytes())

    def test_self_supersession_and_orphan_reciprocal_link_fail(self):
        p.command_record_credential(self.args())
        data = p.load(self.path)
        data["credentials"][0]["supersedes"] = "C1"
        data["credentials"][0]["content_hash"] = p.credential_hash(data["credentials"][0])
        self.assertTrue(any("cycle" in item for item in p.validate(data)))
        data = p.load(self.path)
        data["decisions"][0].pop("credential_id")
        self.assertTrue(any("reciprocal" in item for item in p.validate(data)))

    def test_supersession_preserves_old_credential_and_invalidates_decision(self):
        p.command_record_credential(self.args())
        credential = p.load(self.path)["credentials"][0]
        self.assertEqual(p.command_record_credential(self.args(credential_id="C2", decision_id="D2", supersedes="C1", statement="Revised choice")), 0)
        data = p.load(self.path)
        self.assertEqual(data["credentials"][0], credential)
        self.assertEqual(data["decisions"][0]["status"], "superseded")
        self.assertEqual(p.validate(data), [])

    def test_material_revision_invalidates_dependent_confirmed_decision_and_handoff(self):
        p.command_add_material(self.material())
        p.command_record_credential(self.args(basis="evidence", evidence_id=["M1"]))
        data = p.load(self.path)
        data["handoffs"] = [dict(id="H1", from_stage="question", to_stage="discovery", material_ids=["M1"], status="prepared", recorded_at=p.now())]
        p.atomic_write(self.path, data)
        self.assertEqual(p.command_add_material(self.material(id="M2", supersedes_id="M1")), 0)
        data = p.load(self.path)
        self.assertEqual([item["status"] for item in data["materials"]], ["superseded", "verified"])
        self.assertEqual(data["decisions"][0]["status"], "superseded")
        self.assertEqual(data["handoffs"][0]["status"], "rejected")
        self.assertEqual(p.validate(data), [])

    def test_historical_superseded_material_accepts_one_successor_only(self):
        self.assertEqual(p.command_add_material(self.material(status="superseded")), 0)
        self.assertEqual(p.command_add_material(self.material(id="M2", supersedes_id="M1", status="raw")), 0)
        data = p.load(self.path)
        self.assertEqual(data["materials"][0]["status"], "superseded")
        self.assertEqual(data["materials"][1]["supersedes_id"], "M1")
        self.assertTrue(any(entry["action"] == "material_history_linked" for entry in data["audit_log"]))
        before = self.path.read_bytes()
        self.assertEqual(p.command_add_material(self.material(id="M3", supersedes_id="M1")), 2)
        self.assertEqual(self.path.read_bytes(), before)
        branch = copy.deepcopy(data)
        branch["materials"].append(dict(branch["materials"][1], id="M3"))
        self.assertTrue(any("branches from" in error for error in p.validate(branch)))
        # A later version may supersede the actual chain tail, not branch M1.
        self.assertEqual(p.command_add_material(self.material(id="M3", supersedes_id="M2")), 0)
        self.assertEqual(p.validate(p.load(self.path)), [])

    def test_malformed_json_types_return_validation_errors(self):
        p.command_add_material(self.material())
        p.command_record_credential(self.args())
        baseline = p.load(self.path)
        mutations = [((), "stage"), (("materials", 0), "status"), (("credentials", 0), "authority"), (("credentials", 0), "basis"), (("credentials", 0), "decision_id"), (("decisions", 0), "credential_id")]
        for keys, field in mutations:
            for value in [["unexpected"], {"unexpected": True}]:
                data = copy.deepcopy(baseline)
                node = data
                for key in keys:
                    node = node[key]
                node[field] = value
                self.assertTrue(p.validate(data), (keys, field, value))
        self.assertTrue(p.validate([]))

    def test_scalar_required_fields_and_timestamps_fail(self):
        data = p.load(self.path)
        for field in ["title", "updated_at"]:
            changed = copy.deepcopy(data)
            changed[field] = ""
            self.assertTrue(p.validate(changed))
        data["unknowns"] = [{"id": [], "question": None, "status": "open"}]
        self.assertTrue(p.validate(data))

    def test_cli_concurrent_writers_preserve_both_materials(self):
        script = Path(p.__file__)
        commands = [[sys.executable, str(script), "add-material", str(self.path), "--id", ident, "--type", "paper", "--title", "Synthetic", "--source-pointer", "notes:SYN"] for ident in ["M1", "M2"]]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(len(p.load(self.path)["materials"]), 2)

    def test_invalid_existing_document_and_missing_cli_do_not_crash(self):
        self.path.write_text('{"materials": null}')
        before = self.path.read_bytes()
        self.assertEqual(p.command_add_material(self.material()), 2)
        self.assertEqual(self.path.read_bytes(), before)
        process = subprocess.run([sys.executable, p.__file__, "summary", str(self.path.parent / "missing.json")], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn("Traceback", process.stderr)


if __name__ == "__main__":
    unittest.main()
