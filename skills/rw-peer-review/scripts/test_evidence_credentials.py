#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).with_name("evidence_credentials.py")
SPEC = importlib.util.spec_from_file_location("rw_peer_review_evidence_credentials", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load evidence_credentials.py")
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)


class EvidenceCredentialTests(unittest.TestCase):
    def init_store(self, root: Path) -> Path:
        path = root / "evidence-credentials.json"
        self.assertEqual(credentials.command_init(Namespace(
            path=str(path), review_id="RVW-001", force=False,
        )), 0)
        return path

    def add(
        self, path: Path, identifier: str, kind: str, *, source_id: str | None = None,
        parent_id: str | None = None, previous_id: str | None = None,
        next_id: str | None = None, required: list[str] | None = None,
        status: str = "extracted", text: str = "evidence text",
    ) -> int:
        source_file: str | None = None
        if kind == "source":
            fixture = path.parent / "manuscript.pdf"
            fixture.write_bytes(b"synthetic manuscript fixture")
            source_file = str(fixture)
        return credentials.command_add(Namespace(
            path=str(path), id=identifier, kind=kind, source_id=source_id,
            parent_id=parent_id, previous_id=previous_id, next_id=next_id,
            required_dependency=required or [], optional_dependency=[], status=status,
            pointer="path:manuscript.pdf", page=1 if kind != "source" else None,
            bbox=None, text=text, text_file=None, metadata_file=None,
            source_file=source_file,
            reason="test credential",
        ))

    def link(self, path: Path, identifier: str, required: list[str]) -> int:
        return credentials.command_link(Namespace(
            path=str(path), id=identifier, required_dependency=required,
            optional_dependency=[], parent_id=None, previous_id=None, next_id=None,
            reason="test linkage",
        ))

    def set_status(self, path: Path, identifier: str, status: str, propagate: bool = True) -> int:
        return credentials.command_set_status(Namespace(
            path=str(path), id=identifier, status=status, reason="test status", propagate=propagate,
        ))

    def verified_fixture(self, root: Path) -> Path:
        path = self.init_store(root)
        self.assertEqual(self.add(path, "EV-SOURCE", "source"), 0)
        self.assertEqual(self.add(path, "EV-SECTION", "section", source_id="EV-SOURCE", text="Results"), 0)
        self.assertEqual(self.add(
            path, "EV-PREV", "paragraph", source_id="EV-SOURCE", parent_id="EV-SECTION",
            next_id=None, text="The analysis population included 98 participants.",
        ), 0)
        self.assertEqual(self.add(
            path, "EV-FOOTNOTE", "footnote", source_id="EV-SOURCE", parent_id="EV-SECTION",
            text="Denominator excludes two participants with missing outcome data.",
        ), 0)
        self.assertEqual(self.add(
            path, "EV-TABLE", "table", source_id="EV-SOURCE", parent_id="EV-SECTION",
            previous_id="EV-PREV", required=["EV-FOOTNOTE"], text="12/98 participants improved.",
        ), 0)
        for identifier in ["EV-SECTION", "EV-PREV", "EV-FOOTNOTE", "EV-TABLE"]:
            self.assertEqual(self.set_status(path, identifier, "verified"), 0)
        self.assertEqual(self.link(
            path, "EV-SOURCE", ["EV-SECTION", "EV-PREV", "EV-FOOTNOTE", "EV-TABLE"]
        ), 0)
        self.assertEqual(self.set_status(path, "EV-SOURCE", "verified"), 0)
        return path

    def test_template_matches_schema(self) -> None:
        template = json.loads(
            (SCRIPT.parents[1] / "assets" / "evidence-credential-store-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(credentials.validate(template), [])

    def test_verified_source_gate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            status, reasons = credentials.gate_sources(credentials.load(path), ["EV-SOURCE"])
            self.assertEqual(status, "PASS")
            self.assertEqual(reasons, [])

    def test_source_cannot_verify_before_required_children(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_store(Path(temp))
            self.assertEqual(self.add(path, "EV-SOURCE", "source"), 0)
            self.assertEqual(self.add(path, "EV-PAGE", "page", source_id="EV-SOURCE"), 0)
            self.assertEqual(self.link(path, "EV-SOURCE", ["EV-PAGE"]), 0)
            self.assertEqual(self.set_status(path, "EV-SOURCE", "verified"), 2)

    def test_required_dependency_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_store(Path(temp))
            self.assertEqual(self.add(path, "EV-SOURCE", "source"), 0)
            self.assertEqual(self.add(path, "EV-A", "paragraph", source_id="EV-SOURCE"), 0)
            self.assertEqual(self.add(
                path, "EV-B", "paragraph", source_id="EV-SOURCE", required=["EV-A"]
            ), 0)
            self.assertEqual(self.link(path, "EV-A", ["EV-B"]), 2)

    def test_parent_and_adjacent_links_cannot_cross_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.init_store(Path(temp))
            self.assertEqual(self.add(path, "EV-SOURCE-A", "source"), 0)
            second_source = path.parent / "second.pdf"
            second_source.write_bytes(b"second synthetic manuscript")
            self.assertEqual(credentials.command_add(Namespace(
                path=str(path), id="EV-SOURCE-B", kind="source", source_id=None,
                parent_id=None, previous_id=None, next_id=None, required_dependency=[],
                optional_dependency=[], status="extracted", pointer="path:second.pdf", page=None,
                bbox=None, text="", text_file=None, metadata_file=None,
                source_file=str(second_source), reason="second source",
            )), 0)
            self.assertEqual(self.add(
                path, "EV-P-A", "paragraph", source_id="EV-SOURCE-A",
                parent_id="EV-SOURCE-B",
            ), 2)

    def test_context_pack_contains_dependency_parent_and_adjacent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            status, pack, reasons = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=10,
            )
            self.assertEqual(status, "PASS")
            self.assertEqual(reasons, [])
            self.assertIsNotNone(pack)
            assert pack is not None
            self.assertEqual(
                set(pack["credential_ids"]), {"EV-TABLE", "EV-FOOTNOTE", "EV-SECTION", "EV-PREV"}
            )
            self.assertFalse(pack["selection"]["truncated"])
            self.assertGreater(pack["estimated_token_upper_bound"], 0)
            self.assertEqual(credentials.validate_pack(pack, credentials.load(path)), [])

    def test_pack_limit_blocks_without_truncating_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            status, pack, reasons = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=2,
            )
            self.assertEqual(status, "BLOCK")
            self.assertIsNone(pack)
            self.assertIn("split the Finding", reasons[0])

    def test_token_budget_blocks_without_truncating_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            status, pack, reasons = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=10, max_estimated_tokens=100,
            )
            self.assertEqual(status, "BLOCK")
            self.assertIsNone(pack)
            self.assertIn("estimated token upper bound", reasons[0])

    def test_invalidation_propagates_to_dependents_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            self.assertEqual(self.set_status(path, "EV-FOOTNOTE", "stale"), 0)
            data = credentials.load(path)
            by_id = credentials.index_credentials(data)
            self.assertEqual(by_id["EV-TABLE"]["status"], "stale")
            self.assertEqual(by_id["EV-SOURCE"]["status"], "stale")
            self.assertEqual(by_id["EV-PREV"]["status"], "verified")
            self.assertEqual(credentials.gate_sources(data, ["EV-SOURCE"])[0], "BLOCK")

    def test_old_pack_fails_after_store_status_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            status, pack, _ = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=10,
            )
            self.assertEqual(status, "PASS")
            assert pack is not None
            self.assertEqual(self.set_status(path, "EV-TABLE", "stale"), 0)
            errors = credentials.validate_pack(pack, credentials.load(path))
            self.assertTrue(any("is now stale" in error for error in errors))

    def test_source_file_change_blocks_gate_and_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.verified_fixture(root)
            (root / "manuscript.pdf").write_bytes(b"changed manuscript fixture")
            status, reasons = credentials.gate_sources(credentials.load(path), ["EV-SOURCE"])
            self.assertEqual(status, "BLOCK")
            self.assertTrue(any("file hash changed" in reason for reason in reasons))
            pack_status, pack, _ = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=10,
            )
            self.assertEqual(pack_status, "BLOCK")
            self.assertIsNone(pack)

    def test_changed_credential_content_fails_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.verified_fixture(Path(temp))
            data = copy.deepcopy(credentials.load(path))
            data["credentials"][2]["text"] = "changed text"
            self.assertTrue(any("content_hash does not match" in error for error in credentials.validate(data)))

    def test_ledger_context_is_review_then_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.verified_fixture(root)
            ledger_path = root / "review-ledger.json"
            pack_dir = root / "context-packs"
            pack_dir.mkdir()
            ledger = {"review_id": "RVW-001", "findings": [{"id": "FIND-001"}]}
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            args = Namespace(path=str(path), ledger=str(ledger_path), pack_dir=str(pack_dir))
            self.assertEqual(credentials.command_validate_ledger(args), 1)

            status, pack, _ = credentials.build_pack(
                credentials.load(path), pack_id="PACK-001", finding_id="FIND-001",
                target_ids=["EV-TABLE"], max_credentials=10,
            )
            self.assertEqual(status, "PASS")
            assert pack is not None
            credentials.atomic_write(pack_dir / "FIND-001.json", pack)
            ledger["findings"][0].update({
                "context_pack_id": "PACK-001",
                "evidence_credential_ids": ["EV-TABLE", "EV-FOOTNOTE"],
            })
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            self.assertEqual(credentials.command_validate_ledger(args), 0)

    def test_large_batch_import_keeps_pack_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.init_store(root)
            sample_size = 1000  # Regression sample only; this is not a Store capacity limit.
            source_file = root / "manuscript.pdf"
            source_file.write_bytes(b"synthetic large-batch fixture")
            children: list[dict[str, object]] = [
                {
                    "id": "EV-SECTION", "kind": "section", "source_id": "EV-SOURCE",
                    "status": "verified", "locator": {"pointer": "path:manuscript.pdf", "page": 1},
                    "text": "Results",
                },
                {
                    "id": "EV-FOOTNOTE", "kind": "footnote", "source_id": "EV-SOURCE",
                    "parent_id": "EV-SECTION", "status": "verified",
                    "locator": {"pointer": "path:manuscript.pdf", "page": 8},
                    "text": "Denominator excludes two participants.",
                },
                {
                    "id": "EV-TABLE", "kind": "table", "source_id": "EV-SOURCE",
                    "parent_id": "EV-SECTION", "required_dependencies": ["EV-FOOTNOTE"],
                    "status": "verified", "locator": {"pointer": "path:manuscript.pdf", "page": 8},
                    "text": "12/98 participants improved.",
                },
            ]
            children.extend({
                "id": f"EV-P-{index:04d}", "kind": "paragraph", "source_id": "EV-SOURCE",
                "status": "verified", "locator": {"pointer": "path:manuscript.pdf", "page": index // 20 + 1},
                "text": f"Synthetic paragraph {index}.",
            } for index in range(sample_size - 4))
            payload = {
                "credentials": [
                    {
                        "id": "EV-SOURCE", "kind": "source", "source_file": str(source_file),
                        "status": "verified", "locator": {"pointer": "path:manuscript.pdf"},
                        "required_dependencies": [item["id"] for item in children],
                    },
                    *children,
                ]
            }
            import_path = root / "batch.json"
            import_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(credentials.command_import(Namespace(
                path=str(path), input=str(import_path), reason="large batch regression fixture; not a product limit",
            )), 0)
            data = credentials.load(path)
            self.assertEqual(len(data["credentials"]), sample_size)
            status, pack, reasons = credentials.build_pack(
                data, pack_id="PACK-LARGE", finding_id="FIND-LARGE",
                target_ids=["EV-TABLE"], max_credentials=10,
            )
            self.assertEqual(status, "PASS")
            self.assertEqual(reasons, [])
            assert pack is not None
            self.assertEqual(set(pack["credential_ids"]), {"EV-TABLE", "EV-FOOTNOTE", "EV-SECTION"})


if __name__ == "__main__":
    unittest.main()
