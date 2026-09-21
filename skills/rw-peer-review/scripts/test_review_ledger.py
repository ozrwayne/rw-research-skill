#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT = Path(__file__).with_name("review_ledger.py")
SPEC = importlib.util.spec_from_file_location("rw_peer_review_ledger", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load review_ledger.py")
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class ReviewLedgerTests(unittest.TestCase):
    def open_review(self, root: Path, stage: str = "panel") -> Path:
        path = root / "review-ledger.json"
        self.assertEqual(ledger.command_init(Namespace(
            path=str(path), review_id="RVW-001", manuscript_id="MS-001",
            title="Salt substitution and CVD prevention", journal="BMJ Open",
            version="v1", pointer="path:manuscript.pdf", stage=stage, force=False,
        )), 0)
        self.assertEqual(ledger.command_add_reviewer(Namespace(
            path=str(path), id="agent:METHOD", role="method", model_family="claude",
            reason="method seat assigned",
        )), 0)
        self.assertEqual(ledger.command_add_source(Namespace(
            path=str(path), id="SRC-001", type="manuscript", title="Manuscript v1",
            pointer="path:manuscript.pdf", reason="manuscript registered",
        )), 0)
        return path

    def add_finding(self, path: Path, **overrides: object) -> int:
        args = {
            "path": str(path), "id": "FIND-001", "location": "Results, Table 2",
            "quote": "adherence improved by 15%",
            "problem": "表 2 报的是 12.8%，正文写成 15%。",
            "fix": "把正文数字改成 12.8%，或说明换算方式。",
            "publication_impact": "blocking", "status": "open", "evidence_id": ["SRC-001"],
            "raised_by": "agent:METHOD", "resolution_note": None, "reason": "finding recorded",
        }
        args.update(overrides)
        return ledger.command_add_finding(Namespace(**args))

    def settle(self, path: Path, **overrides: object) -> int:
        args = {
            "path": str(path), "credential_id": "RVCRED-001", "finding_id": "FIND-001",
            "session_id": "SESSION-001", "record_pointer": "notes:SESSION-001",
            "settled_by": ["human:AUTHOR-01"], "authority": "human_confirmed",
            "basis": "evidence", "scope": "RVW-001", "supersedes": None,
            "reason": "debate ruling recorded",
        }
        args.update(overrides)
        return ledger.command_record_credential(Namespace(**args))

    def test_init_creates_empty_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            data = ledger.load(path)
            self.assertEqual(data["schema_version"], "rw-peer-review/v1")
            self.assertEqual(data["findings"], [])
            self.assertEqual(ledger.validate(data), [])

    def test_finding_requires_registered_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path, raised_by="agent:UNKNOWN"), 2)
            self.assertEqual(ledger.load(path)["findings"], [])

    def test_finding_requires_registered_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path, evidence_id=["SRC-MISSING"]), 2)
            self.assertEqual(ledger.load(path)["findings"], [])

    def test_closed_status_requires_resolution_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="answered",
                resolution_note=None, evidence_id=[], reason="answered without a note",
            )), 2)
            self.assertEqual(ledger.load(path)["findings"][0]["status"], "open")

    def test_withdrawn_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path, evidence_id=[]), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="withdrawn",
                resolution_note="作者给出了换算过程。", evidence_id=[], reason="withdrawn without evidence",
            )), 2)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="withdrawn",
                resolution_note="作者给出了换算过程。", evidence_id=["SRC-001"], reason="withdrawn on evidence",
            )), 0)
            self.assertEqual(ledger.validate(ledger.load(path)), [])

    def test_credential_snapshots_finding_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="sustained",
                resolution_note="作者未提供换算依据，意见维持。", evidence_id=[], reason="ruling",
            )), 0)
            self.assertEqual(self.settle(path), 0)
            data = ledger.load(path)
            credential = data["credentials"][0]
            self.assertEqual(credential["finding_snapshot"]["status"], "sustained")
            self.assertTrue(credential["content_hash"].startswith("sha256:"))
            self.assertEqual(data["findings"][0]["credential_id"], "RVCRED-001")
            self.assertEqual(data["audit_log"][-1]["action"], "review_credential_recorded")
            self.assertEqual(ledger.validate(data), [])

    def test_finding_links_evidence_credentials_and_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(
                path,
                evidence_credential_id=["EV-TABLE-2", "EV-FOOTNOTE-2"],
                context_pack_id="PACK-FIND-001",
            ), 0)
            data = ledger.load(path)
            finding = data["findings"][0]
            self.assertEqual(finding["context_pack_id"], "PACK-FIND-001")
            self.assertEqual(finding["evidence_credential_ids"], ["EV-TABLE-2", "EV-FOOTNOTE-2"])
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="sustained",
                resolution_note="证据包支持该意见。", evidence_id=[], reason="ruling",
            )), 0)
            self.assertEqual(self.settle(path), 0)
            snapshot = ledger.load(path)["credentials"][0]["finding_snapshot"]
            self.assertEqual(snapshot["context_pack_id"], "PACK-FIND-001")
            self.assertEqual(snapshot["evidence_credential_ids"], ["EV-TABLE-2", "EV-FOOTNOTE-2"])

    def test_context_pack_and_evidence_credentials_must_be_paired(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(
                path,
                evidence_credential_id=["EV-TABLE-2"],
                context_pack_id=None,
            ), 2)

    def test_changed_credential_fails_hash_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="sustained",
                resolution_note="意见维持。", evidence_id=[], reason="ruling",
            )), 0)
            self.assertEqual(self.settle(path), 0)
            changed = copy.deepcopy(ledger.load(path))
            changed["credentials"][0]["scope"] = "OTHER-REVIEW"
            self.assertIn(
                "credentials[0].content_hash does not match credential content",
                ledger.validate(changed),
            )

    def test_advisory_credential_cannot_withdraw_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="withdrawn",
                resolution_note="作者补了换算过程。", evidence_id=["SRC-001"], reason="ruling",
            )), 0)
            self.assertEqual(self.settle(path, authority="advisory", settled_by=["agent:METHOD"]), 2)
            self.assertEqual(ledger.load(path)["credentials"], [])

    def test_human_confirmed_requires_human_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="sustained",
                resolution_note="意见维持。", evidence_id=[], reason="ruling",
            )), 0)
            self.assertEqual(self.settle(path, settled_by=["agent:METHOD"]), 2)
            self.assertEqual(ledger.load(path)["credentials"], [])

    def test_open_blocking_finding_blocks_synthesis_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            data = ledger.load(path)
            data["stage"] = "synthesis"
            self.assertIn(
                "findings[0] is open and blocking; stage synthesis is not allowed",
                ledger.validate(data),
            )

    def test_gate_reports_block_review_and_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.open_review(Path(temp))
            self.assertEqual(self.add_finding(path), 0)
            self.assertEqual(self.add_finding(path, id="FIND-002", publication_impact="non_blocking"), 0)
            self.assertEqual(ledger.command_gate(Namespace(path=str(path))), 2)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-001", status="sustained",
                resolution_note="意见维持。", evidence_id=[], reason="ruling",
            )), 0)
            self.assertEqual(ledger.command_gate(Namespace(path=str(path))), 1)
            self.assertEqual(ledger.command_set_finding_status(Namespace(
                path=str(path), finding_id="FIND-002", status="answered",
                resolution_note="作者已在讨论中说明。", evidence_id=[], reason="answered",
            )), 0)
            self.assertEqual(ledger.command_gate(Namespace(path=str(path))), 0)

    def test_template_matches_schema(self) -> None:
        template = json.loads(
            (SCRIPT.parents[1] / "assets" / "review-ledger-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(ledger.validate(template), [])


if __name__ == "__main__":
    unittest.main()
