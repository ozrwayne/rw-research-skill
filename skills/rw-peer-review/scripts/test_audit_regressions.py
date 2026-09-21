"""Adversarial synthetic regression tests; no model or Skill workflow calls."""
import copy
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
import test_evidence_credentials as evidence_fixture
credentials = evidence_fixture.credentials
import test_review_ledger as ledger_fixture
ledger = ledger_fixture.ledger


class EvidenceAuditRegression(unittest.TestCase):
    init_store = evidence_fixture.EvidenceCredentialTests.init_store
    add = evidence_fixture.EvidenceCredentialTests.add
    link = evidence_fixture.EvidenceCredentialTests.link
    set_status = evidence_fixture.EvidenceCredentialTests.set_status
    verified_fixture = evidence_fixture.EvidenceCredentialTests.verified_fixture
    def fixture(self, root):
        path = self.verified_fixture(root)
        store = credentials.load(path)
        _, pack, _ = credentials.build_pack(store, pack_id="PACK", finding_id="FIND", target_ids=["EV-TABLE"])
        return path, store, pack

    def test_pack_rehashed_forged_text_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            pack["credentials"][0]["text"] = "fabricated clinical effect"
            pack["pack_hash"] = credentials.pack_hash(pack)
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_pack_current_source_bytes_rechecked(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            (Path(d) / "manuscript.pdf").write_bytes(b"changed source")
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_pack_removed_sources_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            pack["sources"] = []
            pack["pack_hash"] = credentials.pack_hash(pack)
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_pack_missing_required_credential_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            pack["credentials"] = [x for x in pack["credentials"] if x["id"] != "EV-FOOTNOTE"]
            pack["credential_ids"].remove("EV-FOOTNOTE")
            pack["pack_hash"] = credentials.pack_hash(pack)
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_empty_pack_targets_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, _ = self.fixture(Path(d))
            self.assertEqual(credentials.build_pack(store, pack_id="PACK", finding_id="F", target_ids=[])[0], "BLOCK")

    def test_nonfinite_bbox_rejected(self):
        with self.assertRaises(ValueError):
            credentials.parse_bbox("nan,0,1,2")

    def test_long_dependency_graph_without_recursion_failure(self):
        graph = {str(i): [str(i + 1)] for i in range(2000)}
        self.assertIsNone(credentials.find_cycle(graph))

    def test_pack_output_cannot_replace_store(self):
        with tempfile.TemporaryDirectory() as d:
            path, _, _ = self.fixture(Path(d))
            before = path.read_bytes()
            args = Namespace(path=str(path), pack_id="PACK", finding_id="FIND", credential_id=["EV-TABLE"], no_adjacent=False, no_parent=False, max_credentials=40, max_estimated_tokens=20000, output=str(path), force=True)
            self.assertEqual(credentials.command_pack(args), 2)
            self.assertEqual(path.read_bytes(), before)

    def test_empty_context_ledger_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path, _, _ = self.fixture(Path(d))
            ledger_path = Path(d) / "ledger.json"
            ledger_path.write_text(json.dumps({"review_id": "RVW-001", "findings": []}))
            self.assertNotEqual(credentials.command_validate_ledger(Namespace(path=str(path), ledger=str(ledger_path), pack_dir=d)), 0)

    def test_source_without_coverage_dependencies_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.init_store(Path(d))
            self.add(path, "S", "source", status="verified")
            self.assertEqual(credentials.gate_sources(credentials.load(path))[0], "BLOCK")

    def test_pack_context_dependencies_included(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, _ = self.fixture(Path(d))
            by_id = credentials.index_credentials(store)
            extra = copy.deepcopy(by_id["EV-FOOTNOTE"])
            extra["id"] = "EXTRA"
            extra["content_hash"] = credentials.credential_hash(extra)
            store["credentials"].append(extra)
            by_id["EV-PREV"]["required_dependencies"] = ["EXTRA"]
            by_id["EV-PREV"]["content_hash"] = credentials.credential_hash(by_id["EV-PREV"])
            status, pack, _ = credentials.build_pack(store, pack_id="P", finding_id="F", target_ids=["EV-TABLE"])
            self.assertEqual(status, "PASS")
            self.assertIn("EXTRA", pack["credential_ids"])

    def test_pack_duplicated_credential_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            pack["credentials"].append(copy.deepcopy(pack["credentials"][0]))
            pack["credential_ids"].append(pack["credential_ids"][0])
            pack["pack_hash"] = credentials.pack_hash(pack)
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_direct_store_tampering_rejected_in_pack_validation(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, pack = self.fixture(Path(d))
            store["credentials"][1]["text"] = "tampered store content"
            self.assertTrue(credentials.validate_pack(pack, store))

    def test_declared_token_budget_cannot_be_nan_or_boolean(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, _ = self.fixture(Path(d))
            for value in [float('nan'), True, -1, 0, '20']:
                self.assertEqual(credentials.build_pack(store, pack_id="P", finding_id="F", target_ids=["EV-TABLE"], max_estimated_tokens=value)[0], "BLOCK")

    def test_duplicate_context_pack_id_blocks_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path, _, pack = self.fixture(root)
            packs=root/'packs';packs.mkdir()
            for name in ['a.json','b.json']:
                credentials.atomic_write(packs/name,pack)
            ledger_path=root/'ledger.json'
            ledger_path.write_text(json.dumps({'review_id':'RVW-001','findings':[{'id':'FIND','context_pack_id':'PACK','evidence_credential_ids':['EV-TABLE']}]}))
            self.assertEqual(credentials.command_validate_ledger(Namespace(path=str(path),ledger=str(ledger_path),pack_dir=str(packs))),2)

    def test_strict_json_rejects_overflow_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'store.json'
            for value in ['{"x": 1e999}', '{"x": 1, "x": 2}']:
                path.write_text(value)
                with self.assertRaises(ValueError): credentials.load(path)


class LedgerAuditRegression(unittest.TestCase):
    open_review = ledger_fixture.ReviewLedgerTests.open_review
    add_finding = ledger_fixture.ReviewLedgerTests.add_finding
    settle = ledger_fixture.ReviewLedgerTests.settle
    def settled_fixture(self, root):
        path = self.open_review(root)
        self.add_finding(path, status="sustained", resolution_note="Synthetic decision")
        self.settle(path)
        return path

    def test_empty_ledger_gate_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.open_review(Path(d))
            self.assertNotEqual(ledger.command_gate(Namespace(path=str(path))), 0)

    def test_current_credential_snapshot_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.settled_fixture(Path(d))
            data = ledger.load(path)
            data["findings"][0]["resolution_note"] = "Changed decision"
            self.assertTrue(ledger.validate(data))

    def test_cross_finding_credential_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.settled_fixture(Path(d))
            self.add_finding(path, id="FIND-002", status="sustained", resolution_note="Other decision")
            data = ledger.load(path)
            data["findings"][1]["credential_id"] = "RVCRED-001"
            self.assertTrue(ledger.validate(data))

    def test_malformed_enums_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            data = ledger.load(self.open_review(Path(d)))
            data["stage"] = []
            self.assertTrue(ledger.validate(data))

    def test_single_agent_is_not_agent_consensus(self):
        with tempfile.TemporaryDirectory() as d:
            path=self.open_review(Path(d))
            self.add_finding(path,status='sustained',resolution_note='decision')
            self.assertEqual(self.settle(path,authority='agent_consensus',settled_by=['agent:METHOD']),2)

    def test_changed_finding_text_invalidates_current_ruling(self):
        with tempfile.TemporaryDirectory() as d:
            data=ledger.load(self.settled_fixture(Path(d)))
            data['findings'][0]['problem']='A materially different finding'
            self.assertTrue(ledger.validate(data))


class JudgmentAuditRegression(unittest.TestCase):
    def test_duplicate_cases_do_not_establish_independence(self):
        import test_judgment_learning as fixture
        with tempfile.TemporaryDirectory() as d:
            helper=fixture.JudgmentLearningTests()
            path=helper.initialized(Path(d))
            data=helper.complete_guided(fixture.judgment.load(path))
            data['novice_support']['independent_case_records']=[{'case_id':'SAME','study_type':'cohort','problem_type':'estimand','status':'pass','assessed_by':'human:R'}]*2
            data['novice_support']['mastery_decision']='meets_predeclared_standard'
            self.assertNotEqual(fixture.judgment.mastery(data)[0],'PASS')

    def test_guided_example_must_differ_from_baseline(self):
        import test_judgment_learning as fixture
        with tempfile.TemporaryDirectory() as d:
            helper=fixture.JudgmentLearningTests();path=helper.initialized(Path(d))
            data=helper.complete_guided(fixture.judgment.load(path))
            data['novice_support']['worked_example']['case_id']=data['novice_support']['baseline_case']['case_id']
            self.assertEqual(fixture.judgment.readiness(data,'synthesis')[0],'BLOCK')


if __name__ == "__main__":
    unittest.main()
