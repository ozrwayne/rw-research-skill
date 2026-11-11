from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cross_model_review.py"
SPEC = importlib.util.spec_from_file_location("cross_model_review", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def response(issue: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "verdict": "minor_revision",
        "verdict_reason": "One revision is needed.",
        "strengths": [],
        "issues": [issue] if issue else [],
        "unknowns": [],
        "decision": "revise_then_send",
    }


def issue(quote: str, problem: str = "The claim is not explained.") -> dict[str, str]:
    return {
        "severity": "major",
        "location": "Section 1.1, paragraph 2",
        "quoted_text": quote,
        "problem": problem,
        "effect": "The reader cannot follow the inference.",
        "basis": "confirmed_text",
        "repair_action": "Add the missing interpretation.",
    }


class CrossModelReviewTests(unittest.TestCase):
    def test_default_matrix_matches_personal_local_models(self) -> None:
        models = json.loads(MODULE.DEFAULT_MODELS.read_text(encoding="utf-8"))
        self.assertEqual(
            [
                ("openai-gpt-5.6-sol", "codex", "gpt-5.6-sol"),
                ("openai-gpt-5.6-terra", "codex", "gpt-5.6-terra"),
                ("openai-gpt-5.6-luna", "codex", "gpt-5.6-luna"),
                ("anthropic-claude-opus-4.8", "claude", "claude-opus-4-8"),
            ],
            [(item["id"], item["provider"], item["model"]) for item in models],
        )

    def test_provider_balancing_does_not_treat_three_codex_votes_as_cross_provider(self) -> None:
        shared = "This sentence states a result but does not explain why it matters."
        codex_only = "The objectives are introduced before the evidence gap is established."
        records = [
            {"model_id": "sol", "provider": "codex", "response": response(issue(shared)), "error": None},
            {"model_id": "terra", "provider": "codex", "response": response(issue(codex_only)), "error": None},
            {"model_id": "luna", "provider": "codex", "response": response(issue(codex_only)), "error": None},
            {"model_id": "opus", "provider": "claude", "response": response(issue(shared)), "error": None},
        ]
        summary = MODULE.summarize({"records": records, "models": [{"id": record["model_id"]} for record in records], "finished_at": "fixture-complete"})
        self.assertEqual("MULTI_PROVIDER_REVIEW_COMPLETE", summary["status"])
        self.assertEqual(1, len(summary["cross_provider_findings"]))
        self.assertEqual(["opus", "sol"], summary["cross_provider_findings"][0]["models"])
        self.assertEqual(1, len(summary["codex_family_findings"]))
        self.assertEqual(["luna", "terra"], summary["codex_family_findings"][0]["models"])

    def test_quote_containment_can_join_two_anchored_findings(self) -> None:
        short = "The reader cannot see why this finding matters to the research question."
        long = f"In this paragraph, {short} The next sentence changes topic."
        left = issue(short, "The evidence does not explain why the finding matters to the research question.")
        right = issue(long, "The finding is stated without explaining why it matters to the research question.")
        self.assertTrue(MODULE.anchored_match(left, right))

    def test_same_quote_does_not_merge_different_problems(self) -> None:
        quote = "The reviewed evaluations do not provide a North Campus estimate under local conditions."
        style = issue(quote, "Several paragraphs repeat the same negative boundary sentence and create uniform rhythm.")
        evidence = issue(quote, "The cited source texts are unavailable, so the evidence gap cannot be verified.")
        self.assertFalse(MODULE.anchored_match(style, evidence))

    def test_docx_reader_uses_standard_library(self) -> None:
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>First paragraph.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p></w:body></w:document>'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            self.assertEqual("First paragraph.\n\nSecond paragraph.\n", MODULE.read_document(path))

    def test_plain_claim_gate_is_included_only_when_present(self) -> None:
        text, _hashes = MODULE.build_skill_context(["rw-phd-write"])
        self.assertIn("rw-phd-write/references/plain-claim-gate.md", text)
        self.assertIn("防御性写作", text)
        other, _other_hashes = MODULE.build_skill_context(["rw-research-referee"])
        self.assertNotIn("plain-claim-gate.md", other)

    def test_invalid_writing_category_is_rejected(self) -> None:
        bad = issue("The residence-hall sample does not stand for students across the country.")
        bad["writing_category"] = "hedge"
        with self.assertRaises(ValueError):
            MODULE.validate_response(response(bad))

    def test_summary_groups_findings_by_writing_category(self) -> None:
        defensive = issue("The residence-hall sample does not stand for students across the country.", "The sentence blocks a criticism instead of stating who was included.")
        defensive["writing_category"] = "defensive"
        coined = issue("Each clinic is reported as a sender-channel pair.", "The noun string is not a sourced term.")
        coined["writing_category"] = "coined_term"
        records = [
            {"model_id": "sol", "provider": "codex", "response": response(defensive), "error": None},
            {"model_id": "opus", "provider": "claude", "response": response(defensive), "error": None},
            {"model_id": "terra", "provider": "codex", "response": response(coined), "error": None},
        ]
        summary = MODULE.summarize({
            "records": records,
            "models": [{"id": record["model_id"]} for record in records],
            "finished_at": "fixture-complete",
        })
        rendered = MODULE.summary_markdown({
            "run_id": "fixture",
            "document_file": "fixture.md",
            "document_sha256": "0",
            "brief_sha256": "0",
            "models_sha256": "0",
            "skills": ["rw-phd-write"],
            "cli_versions": {},
            "summary": summary,
        })
        self.assertIn("### defensive", rendered)
        self.assertIn("### coined_term", rendered)
        self.assertLess(rendered.index("### defensive"), rendered.index("### coined_term"))
        self.assertIn("两边一致", rendered)
        self.assertIn("仅一方标出", rendered)

    def test_collocation_category_is_accepted_and_grouped(self) -> None:
        self.assertIn("collocation", MODULE.build_prompt("text", "brief", "context", 3))
        row = issue("The study uses dormitory-sleep methods.", "A setting noun is joined directly to methods.")
        row["writing_category"] = "collocation"
        MODULE.validate_response(response(row))
        summary = MODULE.summarize({
            "records": [{"model_id": "sol", "provider": "codex", "response": response(row), "error": None}],
            "models": [{"id": "sol"}],
            "finished_at": "fixture-complete",
        })
        rendered = MODULE.summary_markdown({
            "run_id": "fixture",
            "document_file": "fixture.md",
            "document_sha256": "0",
            "brief_sha256": "0",
            "models_sha256": "0",
            "skills": ["rw-phd-write"],
            "cli_versions": {},
            "summary": summary,
        })
        self.assertIn("### collocation", rendered)
        self.assertLess(rendered.index("### internal_context"), rendered.index("### collocation"))


if __name__ == "__main__":
    unittest.main()
