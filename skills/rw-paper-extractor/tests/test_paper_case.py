from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import paper_case


class PaperCaseTests(unittest.TestCase):
    def make_pdf(self, path: Path) -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Abstract")
        page.insert_text((72, 100), "A test paper reports one result.")
        page.draw_rect(fitz.Rect(72, 140, 300, 260), color=(0, 0, 0))
        page.insert_text((72, 280), "Figure 1. Test diagram")
        document.save(path)

    def test_source_change_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            out = root / "case"
            self.make_pdf(pdf)
            args = type(
                "Args",
                (),
                {
                    "pdf": pdf,
                    "output": out,
                    "title": "Test",
                    "doi": "",
                    "zotero_library_id": 1,
                    "zotero_key": "TESTKEY",
                    "zotero_attachment_key": "ATTACH",
                },
            )()
            self.assertEqual(paper_case.build_case(args), 0)
            self.assertEqual(paper_case.validate_case(out), [])
            document = fitz.open(pdf)
            document[0].insert_text((72, 320), "changed")
            changed = root / "changed.pdf"
            document.save(changed)
            pdf.write_bytes(changed.read_bytes())
            problems = paper_case.validate_case(out)
            self.assertIn("source PDF hash changed; case is STALE", problems)

    def test_case_records_no_external_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            out = root / "case"
            self.make_pdf(pdf)
            args = type(
                "Args",
                (),
                {
                    "pdf": pdf,
                    "output": out,
                    "title": "Test",
                    "doi": "",
                    "zotero_library_id": 1,
                    "zotero_key": "TESTKEY",
                    "zotero_attachment_key": "ATTACH",
                },
            )()
            paper_case.build_case(args)
            case = json.loads((out / "case.json").read_text(encoding="utf-8"))
            self.assertFalse(case["privacy"]["external_model_called"])
            self.assertFalse(case["privacy"]["pdf_copied"])

    def test_changed_stage_artifact_marks_downstream_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            out = root / "case"
            self.make_pdf(pdf)
            args = type(
                "Args",
                (),
                {
                    "pdf": pdf,
                    "output": out,
                    "title": "Test",
                    "doi": "",
                    "zotero_library_id": 1,
                    "zotero_key": "TESTKEY",
                    "zotero_attachment_key": "ATTACH",
                },
            )()
            paper_case.build_case(args)
            artifact = out / "stage.md"
            artifact.write_text("first\n", encoding="utf-8")
            stage_state = json.loads((out / "stage-state.json").read_text(encoding="utf-8"))
            stage_state["stages"]["report_assembled"].update(
                {
                    "status": "complete",
                    "artifact": "stage.md",
                    "artifact_sha256": paper_case.sha256_file(artifact),
                }
            )
            paper_case.write_json(out / "stage-state.json", stage_state)
            self.assertEqual(paper_case.validate_case(out), [])
            artifact.write_text("changed\n", encoding="utf-8")
            problems = paper_case.validate_case(out)
            self.assertIn(
                "stage artifact changed; downstream is STALE: report_assembled",
                problems,
            )

    def test_heading_requires_complete_term_or_typography(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "headings.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 40), "Publication Date: 2026-01-01", fontsize=13, fontname="hebo")
            page.insert_text((72, 72), "METHODS", fontsize=16, fontname="hebo")
            page.insert_text(
                (72, 110),
                "method. Summary effects on continuous outcomes were determined from a fixed effect model.",
                fontsize=11,
                fontname="helv",
            )
            page.insert_text((72, 150), "Sample size and statistical analysis", fontsize=13, fontname="hebo")
            page.insert_text((72, 180), "The analysis used a prespecified model.", fontsize=11, fontname="helv")
            page.insert_text((72, 220), "TABLE 1 Outcome data", fontsize=13, fontname="hebo")
            document.save(pdf)
            document.close()

            parsed = fitz.open(pdf)
            units, sections = paper_case.extract_text_units(parsed)
            section_text = [section["heading"] for section in sections]
            false_unit = next(unit for unit in units if unit["text"].startswith("method. Summary"))
            self.assertEqual(false_unit["kind"], "paragraph")
            self.assertIn("METHODS", section_text)
            self.assertIn("Sample size and statistical analysis", section_text)
            self.assertNotIn("Publication Date: 2026-01-01", section_text)
            self.assertNotIn("TABLE 1 Outcome data", section_text)
            caption = next(unit for unit in units if unit["text"] == "TABLE 1 Outcome data")
            self.assertEqual(caption["kind"], "caption")

    def test_detects_unruled_table_continuation(self) -> None:
        class FakePage:
            rect = fitz.Rect(0, 0, 595, 842)

            def get_text(self, kind: str, sort: bool = False):
                self_kind = kind
                self_sort = sort
                del self_kind, self_sort
                words = []
                for block_no, y in enumerate((73.0, 98.0, 123.0), start=2):
                    cells = [
                        (62.0, "Outcome"),
                        (256.0, "1.78"),
                        (317.0, "2.23"),
                        (369.0, "0.77"),
                        (416.0, "0.55-1.07"),
                    ]
                    for line_no, (x, text) in enumerate(cells):
                        words.append((x, y, x + 45, y + 10, text, block_no, line_no, 0))
                words.append((56.0, 283.0, 250.0, 293.0, "* footnote", 9, 0, 0))
                return words

        bbox = paper_case.continuation_bbox_from_words(
            FakePage(),
            fitz.Rect(56.87, 137.73, 484.07, 761.62),
            5,
        )
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertLess(bbox.y0, 73.0)
        self.assertGreater(bbox.y1, 133.0)
        self.assertLess(bbox.y1, 283.0)

    def test_standalone_case_scaffold_and_litnet_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            out = root / "case"
            self.make_pdf(pdf)
            build_args = type(
                "Args",
                (),
                {
                    "pdf": pdf,
                    "output": out,
                    "title": "Standalone Test",
                    "doi": "10.0000/test.1",
                    "zotero_library_id": None,
                    "zotero_key": "",
                    "zotero_attachment_key": "",
                },
            )()
            paper_case.build_case(build_args)
            case = json.loads((out / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(case["paper_id"], "doi-10.0000-test.1")
            source = json.loads((out / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("optional_zotero", source)

            scaffold_args = type("Args", (), {"output": out, "force": False})()
            paper_case.scaffold_command(scaffold_args)
            self.assertTrue((out / "stages" / "01-question.md").is_file())
            report = out / "report.md"
            self.assertTrue(report.is_file())

            paper_case.mark_stage_command(type("Args", (), {
                "output": out, "stage": "report_assembled", "artifact": "report.md",
                "status": "complete", "upstream": [f"stages/{name}" for name, _, _ in paper_case.REPORT_STAGES],
            })())
            audit = {
                "schema_version": "rw-claim-audit/v1",
                "document_id": case["paper_id"],
                "document_path": str(report),
                "document_hash": paper_case.sha256_file(report),
                "audited_at": "2026-07-23T00:00:00Z",
                "claims": [
                    {
                        "id": "CLM-001",
                        "text": "Test claim",
                        "location": "report.md",
                        "claim_type": "other",
                        "source_refs": [
                            {
                                "id": "source-1",
                                "source_pointer": str(pdf),
                                "source_path": str(pdf),
                                "source_sha256": paper_case.sha256_file(pdf),
                                "locator": "p. 1",
                                "support_note": "Test support",
                            }
                        ],
                        "verdict": "VERIFIED",
                        "notes": "",
                    }
                ],
            }
            audit_path = out / "audit" / "claim-audit.json"
            paper_case.write_json(audit_path, audit)
            preview_args = type(
                "Args",
                (),
                {
                    "output": out,
                    "claim_audit": audit_path,
                    "litnet_work": "w_test",
                    "zotero_record": "",
                },
            )()
            paper_case.litnet_preview_command(preview_args)
            preview = json.loads((out / "litnet-writeback-preview.json").read_text(encoding="utf-8"))
            self.assertEqual(preview["claim_gate"], "PASS")
            self.assertFalse(preview["write_performed"])


if __name__ == "__main__":
    unittest.main()
