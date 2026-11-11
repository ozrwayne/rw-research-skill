from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "rw-research-learning"
SCANNER_PATH = SKILL / "scripts" / "research_learning_scan.py"


def load_scanner():
    spec = importlib.util.spec_from_file_location("research_learning_scan", SCANNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_docx(path: Path, text: str) -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


class ResearchLearningTests(unittest.TestCase):
    def run_scanner(self, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCANNER_PATH), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_scan_query_and_sensitive_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "corpus"
            state = root / "state"
            corpus.mkdir()
            (corpus / "notes.md").write_text(
                "# 因果推断\n\n我用有向无环图检查混杂路径，再决定调整集。\n",
                encoding="utf-8",
            )
            (corpus / ".env").write_text("TOKEN=do-not-index\n", encoding="utf-8")
            write_docx(corpus / "methods.docx", "差异中的差异需要检查平行趋势。")

            summary = self.run_scanner(
                "scan", "--mode", "folder", "--root", str(corpus), "--state-dir", str(state)
            )
            self.assertEqual(3, summary["totals"]["files_seen"])
            self.assertEqual(2, summary["totals"]["indexed"])
            self.assertEqual(1, summary["totals"]["sensitive"])

            result = self.run_scanner(
                "query", "--state-dir", str(state), "--topic", "因果推断", "--limit", "5"
            )
            self.assertGreaterEqual(result["count"], 1)
            self.assertTrue(result["matches"][0]["path"].endswith("notes.md"))
            self.assertNotIn("do-not-index", json.dumps(result, ensure_ascii=False))

    def test_incremental_scan_reuses_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "corpus"
            state = root / "state"
            corpus.mkdir()
            (corpus / "one.txt").write_text("研究问题需要可证伪条件。", encoding="utf-8")

            self.run_scanner("scan", "--mode", "folder", "--root", str(corpus), "--state-dir", str(state))
            second = self.run_scanner(
                "scan", "--mode", "folder", "--root", str(corpus), "--state-dir", str(state)
            )
            self.assertEqual(1, second["totals"]["unchanged"])
            self.assertEqual(0, second["totals"].get("changed", 0))

    def test_rejects_filesystem_root(self) -> None:
        scanner = load_scanner()
        with self.assertRaisesRegex(ValueError, "filesystem root"):
            scanner.resolve_roots("folder", [Path(Path.cwd().anchor)])

    def test_profile_template_matches_schema(self) -> None:
        scanner = load_scanner()
        profile = json.loads((SKILL / "assets" / "profile-template.json").read_text(encoding="utf-8"))
        self.assertEqual([], scanner.validate_profile(profile))

    def test_landscape_discovers_candidates_without_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            research = root / "projects" / "research-notes"
            research.mkdir(parents=True)
            (research / "plan.md").write_text("Synthetic private sentence.", encoding="utf-8")

            result = self.run_scanner(
                "landscape", "--mode", "folder", "--root", str(root), "--limit", "10"
            )
            self.assertFalse(result["content_extracted"])
            self.assertTrue(any(item["root"].endswith("research-notes") for item in result["candidates"]))
            self.assertNotIn("Synthetic private sentence", json.dumps(result, ensure_ascii=False))

    def test_malformed_pdf_does_not_stop_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "corpus"
            state = root / "state"
            corpus.mkdir()
            (corpus / "good.md").write_text("Synthetic research record.", encoding="utf-8")
            (corpus / "broken.pdf").write_bytes(b"%PDF-1.7\nnot-a-valid-pdf")

            summary = self.run_scanner(
                "scan", "--mode", "folder", "--root", str(corpus), "--state-dir", str(state)
            )
            self.assertEqual(1, summary["totals"]["indexed"])
            self.assertEqual(2, summary["totals"]["files_seen"])
            self.assertEqual(
                1,
                summary["totals"].get("unreadable", 0)
                + summary["totals"].get("unsupported", 0),
            )

    def test_external_reference_cannot_be_only_applied_evidence(self) -> None:
        scanner = load_scanner()
        profile = json.loads((SKILL / "assets" / "profile-template.json").read_text(encoding="utf-8"))
        profile["capabilities"] = [
            {
                "name": "Synthetic method",
                "status": "applied",
                "judgment": "Synthetic judgment",
                "confidence": "medium",
                "evidence": [
                    {
                        "path": "synthetic/reference.pdf",
                        "locator": "page 1",
                        "reason": "The file only describes the method.",
                        "source_kind": "external_reference",
                        "authorship_confidence": "low",
                        "currentness": "reference",
                    }
                ],
            }
        ]
        self.assertIn(
            "capabilities[0].applied requires user-role evidence",
            scanner.validate_profile(profile),
        )

    def test_nested_library_folder_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "project"
            library = corpus / "library"
            state = root / "state"
            library.mkdir(parents=True)
            (library / "reference.md").write_text("Synthetic external reference.", encoding="utf-8")

            summary = self.run_scanner(
                "scan", "--mode", "folder", "--root", str(corpus), "--state-dir", str(state)
            )
            self.assertEqual(1, summary["totals"]["files_seen"])
            self.assertEqual(1, summary["totals"]["indexed"])


if __name__ == "__main__":
    unittest.main()
