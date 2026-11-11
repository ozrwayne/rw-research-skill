#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT = Path(__file__).with_name("passport.py")
SPEC = importlib.util.spec_from_file_location("rw_research_passport", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load passport.py")
passport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(passport)


class PassportCredentialTests(unittest.TestCase):
    def init_passport(self, root: Path) -> Path:
        path = root / "passport.json"
        result = passport.command_init(Namespace(
            path=str(path), project_id="PROJECT-001", title="Project", stage="question", force=False,
        ))
        self.assertEqual(result, 0)
        return path

    def record_credential(self, path: Path) -> int:
        return passport.command_record_credential(Namespace(
            path=str(path), credential_id="RCRED-001", decision_id="DEC-001",
            statement="Use the agreed research scope.", status="confirmed",
            session_id="SESSION-001", record_pointer="notes:SESSION-001",
            settled_by=["human:HUMAN-ID", "agent:RESEARCH-01"], authority="human_confirmed",
            basis="reasoning", scope="PROJECT-001", evidence_id=[], unknown_id=[], supersedes=None,
            reason="meeting decision recorded",
        ))

    def test_init_contains_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            data = passport.load(path)
            self.assertEqual(data["credentials"], [])
            self.assertEqual(passport.validate(data), [])

    def test_record_credential_adds_decision_hash_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            self.assertEqual(self.record_credential(path), 0)
            data = passport.load(path)
            self.assertEqual(data["decisions"][0]["credential_id"], "RCRED-001")
            self.assertEqual(data["credentials"][0]["authority"], "human_confirmed")
            self.assertTrue(data["credentials"][0]["content_hash"].startswith("sha256:"))
            self.assertEqual(data["audit_log"][-1]["action"], "research_credential_recorded")
            self.assertEqual(passport.validate(data), [])

    def test_changed_credential_fails_hash_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            self.assertEqual(self.record_credential(path), 0)
            data = passport.load(path)
            changed = copy.deepcopy(data)
            changed["credentials"][0]["scope"] = "OTHER-PROJECT"
            errors = passport.validate(changed)
            self.assertIn("credentials[0].content_hash does not match credential content", errors)

    def test_missing_superseded_credential_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            self.assertEqual(self.record_credential(path), 0)
            data = passport.load(path)
            data["credentials"][0]["supersedes"] = "RCRED-MISSING"
            data["credentials"][0]["content_hash"] = passport.credential_hash(data["credentials"][0])
            errors = passport.validate(data)
            self.assertIn("credentials[0].supersedes references missing credential: RCRED-MISSING", errors)

    def test_legacy_passport_without_credentials_remains_valid(self) -> None:
        template = json.loads((SCRIPT.parents[1] / "assets" / "passport-template.json").read_text(encoding="utf-8"))
        template.pop("credentials")
        self.assertEqual(passport.validate(template), [])

    def test_human_confirmation_requires_human_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            args = Namespace(
                path=str(path), credential_id="RCRED-001", decision_id="DEC-001",
                statement="Use the agreed research scope.", status="confirmed",
                session_id="SESSION-001", record_pointer="notes:SESSION-001",
                settled_by=["agent:RESEARCH-01"], authority="human_confirmed",
                basis="reasoning", scope="PROJECT-001", evidence_id=[], unknown_id=[], supersedes=None,
                reason="meeting decision recorded",
            )
            self.assertEqual(passport.command_record_credential(args), 2)
            self.assertEqual(passport.load(path)["credentials"], [])

    def test_agent_consensus_accepts_agent_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            args = Namespace(
                path=str(path), credential_id="RCRED-001", decision_id="DEC-001",
                statement="Use the shared extraction rule.", status="confirmed",
                session_id="SESSION-001", record_pointer="conversation:SESSION-001",
                settled_by=["agent:RESEARCH-01", "agent:RESEARCH-02"], authority="agent_consensus",
                basis="reasoning", scope="extraction", evidence_id=[], unknown_id=[], supersedes=None,
                reason="agent discussion recorded",
            )
            self.assertEqual(passport.command_record_credential(args), 0)
            self.assertEqual(passport.validate(passport.load(path)), [])

    def test_evidence_basis_requires_evidence_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_passport(Path(temp))
            args = Namespace(
                path=str(path), credential_id="RCRED-001", decision_id="DEC-001",
                statement="Use the reported estimate.", status="confirmed",
                session_id="SESSION-001", record_pointer="notes:SESSION-001",
                settled_by=["human:HUMAN-ID"], authority="human_confirmed",
                basis="evidence", scope="analysis", evidence_id=[], unknown_id=[], supersedes=None,
                reason="evidence decision recorded",
            )
            self.assertEqual(passport.command_record_credential(args), 2)
            self.assertEqual(passport.load(path)["credentials"], [])


if __name__ == "__main__":
    unittest.main()
