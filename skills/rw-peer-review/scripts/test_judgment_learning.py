#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT = Path(__file__).with_name("judgment_learning.py")
SPEC = importlib.util.spec_from_file_location("rw_peer_review_judgment_learning", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load judgment_learning.py")
judgment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judgment)


class JudgmentLearningTests(unittest.TestCase):
    def initialized(self, root: Path, mode: str = "full") -> Path:
        path = root / "judgment-learning" / "FIND-001.json"
        self.assertEqual(judgment.command_init(Namespace(
            path=str(path), review_id="RVW-001", finding_id="FIND-001", mode=mode, force=False,
        )), 0)
        return path

    def complete(self, data: dict[str, object]) -> dict[str, object]:
        data = copy.deepcopy(data)
        data["machine_issue_map"] = {
            "claim": "正文将方向一致写成结果稳健。",
            "evidence_locations": ["Results, Table S3"],
            "research_object": "分析样本中的结局关联",
            "estimand_or_target_effect": "同一目标人群下的调整后关联",
            "unknowns": [],
        }
        data["user_initial_judgment"] = {
            "statement": "方向一致还不足以证明稳健。",
            "basis": ["主模型与敏感性模型需要针对同一目标效应。"],
            "confidence": "medium",
            "uncertainties": ["需要核对权重和分析样本。"],
        }
        data["strongest_challenge"] = {
            "statement": "敏感性模型改变了目标人群。",
            "target": "estimand",
            "evidence": ["Methods, weighting section"],
        }
        data["strongest_response"] = {
            "statement": "补充材料报告了相同方向的估计。",
            "source": ["Table S3"],
            "author_or_user_supplied": True,
        }
        data["verification"] = {
            "main_text": "verified",
            "supplement": "verified",
            "author_explanation": "verified",
            "statistical_principle": "verified",
            "research_object_and_estimand": "verified",
            "response_mentioned": "yes",
            "response_hits_issue": "partial",
            "response_is_sufficient": "partial",
            "body_still_needs_reporting": "yes",
        }
        data["concepts_used"] = ["estimand", "sensitivity analysis"]
        data["user_final_judgment"] = {
            "statement": "回应命中一部分，但正文仍需报告目标人群和权重诊断。",
            "disposition": "narrowed",
            "basis": ["方向一致；目标人群和诊断仍不完整。"],
            "confidence": "high",
            "remaining_uncertainties": [],
            "changed_by_evidence": ["Table S3"],
        }
        return data

    def complete_guided(self, data: dict[str, object]) -> dict[str, object]:
        data = self.complete(data)
        data["mode"] = "guided"
        data["novice_support"] = {
            "experience_declared": "none",
            "baseline_case": {
                "case_id": "SYN-BASE-001",
                "user_answer": "结论超过表格中的关联证据。",
                "status": "completed",
            },
            "worked_example": {
                "case_id": "SYN-WORKED-001",
                "completed": True,
            },
            "guided_review_card": {
                "claim": "敏感性分析证明结果稳健。",
                "evidence_location": "Results, Table S3",
                "study_design": "observational cohort",
                "research_object": "分析样本中的结局关联",
                "estimand_or_target_effect": "同一目标人群下的调整后关联",
                "issue_type": "estimand alignment",
                "publication_impact": "blocking",
                "proposed_fix": "报告目标人群、权重诊断和估计区间。",
                "change_evidence": "同一目标效应下的完整诊断和区间。",
            },
            "feedback": {
                "missed_evidence": [],
                "overreach": [],
                "severity_notes": [],
                "next_practice": ["再做一个同类迁移案例。"],
            },
            "review_quality_check": {
                "research_question_importance": "pass",
                "originality": "pass",
                "method_strengths_weaknesses": "pass",
                "presentation_reporting": "pass",
                "interpretation": "pass",
                "constructiveness": "pass",
                "substantiation": "pass",
            },
            "critical_miss": False,
            "assessment_standard": {
                "name": "Mentor rubric v1",
                "source": "mentor:METHOD-01",
                "required_independent_cases": 2,
            },
            "independent_case_records": [],
            "assessed_by": "human:METHOD-01",
            "mastery_decision": "needs_practice",
        }
        return data

    def test_template_is_structurally_valid(self) -> None:
        template = json.loads(
            (SCRIPT.parents[1] / "assets" / "judgment-learning-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(judgment.validate(template), [])

    def test_initial_template_blocks_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            status, reasons = judgment.readiness(judgment.load(path), "synthesis")
            self.assertEqual(status, "BLOCK")
            self.assertIn("user_initial_judgment.statement is empty", reasons)
            self.assertIn("verification.main_text is not_verified", reasons)

    def test_complete_record_passes_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            self.assertEqual(judgment.validate(data), [])
            self.assertEqual(judgment.readiness(data, "synthesis"), ("PASS", []))

    def test_delivery_requires_cleanliness_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            status, reasons = judgment.readiness(data, "delivery")
            self.assertEqual(status, "BLOCK")
            self.assertIn("delivery_boundary.internal_fields_excluded is false", reasons)
            self.assertIn("delivery_boundary.cleanliness_check is not passed", reasons)
            data["delivery_boundary"] = {
                "internal_fields_excluded": True,
                "cleanliness_check": "passed",
            }
            self.assertEqual(judgment.readiness(data, "delivery"), ("PASS", []))

    def test_mentioned_does_not_imply_sufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            data["verification"]["response_mentioned"] = "yes"
            data["verification"]["response_hits_issue"] = "no"
            data["verification"]["response_is_sufficient"] = "no"
            self.assertEqual(judgment.validate(data), [])
            self.assertEqual(judgment.readiness(data, "synthesis"), ("PASS", []))

    def test_body_reporting_blocks_resolved_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            data["verification"]["response_is_sufficient"] = "yes"
            data["user_final_judgment"]["disposition"] = "answered"
            self.assertIn(
                "user_final_judgment.disposition cannot be answered or withdrawn when body_still_needs_reporting is yes",
                judgment.validate(data),
            )

    def test_mode_off_returns_review_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp), mode="off")
            status, reasons = judgment.readiness(judgment.load(path), "synthesis")
            self.assertEqual(status, "REVIEW")
            self.assertIn("mode is off; judgment learning was explicitly skipped", reasons)

    def test_transfer_needs_practice_returns_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            data["transfer_check"]["status"] = "needs_practice"
            status, _ = judgment.readiness(data, "synthesis")
            self.assertEqual(status, "REVIEW")

    def test_guided_mode_requires_baseline_and_worked_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp), mode="guided")
            data = self.complete(judgment.load(path))
            status, reasons = judgment.readiness(data, "synthesis")
            self.assertEqual(status, "BLOCK")
            self.assertIn("guided mode requires a completed baseline answer", reasons)
            self.assertIn("guided mode requires a completed worked example", reasons)

    def test_complete_guided_record_passes_task_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp), mode="guided")
            data = self.complete_guided(judgment.load(path))
            self.assertEqual(judgment.validate(data), [])
            self.assertEqual(judgment.readiness(data, "synthesis"), ("PASS", []))

    def test_mastery_uses_predeclared_case_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp), mode="guided")
            data = self.complete_guided(judgment.load(path))
            status, reasons = judgment.mastery(data)
            self.assertEqual(status, "REVIEW")
            self.assertIn("novice_support.independent_case_records do not meet the predeclared requirement", reasons)
            data["novice_support"]["independent_case_records"] = [
                {"case_id": "CASE-1", "study_type": "cohort", "problem_type": "estimand", "status": "pass", "assessed_by": "human:METHOD-01"},
                {"case_id": "CASE-2", "study_type": "cohort", "problem_type": "estimand", "status": "pass", "assessed_by": "human:METHOD-01"},
            ]
            data["novice_support"]["mastery_decision"] = "meets_predeclared_standard"
            self.assertEqual(judgment.mastery(data), ("PASS", []))

    def test_critical_miss_prevents_mastery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp), mode="guided")
            data = self.complete_guided(judgment.load(path))
            data["novice_support"]["independent_case_records"] = [
                {"case_id": "CASE-1", "study_type": "cohort", "problem_type": "estimand", "status": "pass", "assessed_by": "human:METHOD-01"},
                {"case_id": "CASE-2", "study_type": "cohort", "problem_type": "estimand", "status": "pass", "assessed_by": "human:METHOD-01"},
            ]
            data["novice_support"]["mastery_decision"] = "meets_predeclared_standard"
            data["novice_support"]["critical_miss"] = True
            status, reasons = judgment.mastery(data)
            self.assertEqual(status, "REVIEW")
            self.assertIn("novice_support.critical_miss is true", reasons)

    def test_task_readiness_does_not_claim_mastery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.initialized(Path(temp))
            data = self.complete(judgment.load(path))
            self.assertEqual(judgment.readiness(data, "synthesis"), ("PASS", []))
            status, _ = judgment.mastery(data)
            self.assertEqual(status, "REVIEW")


if __name__ == "__main__":
    unittest.main()
