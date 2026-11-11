#!/usr/bin/env python3
"""Check the research-to-submission handoff contract."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR_TESTS = ROOT / "references/behavior-tests.json"
DOMAIN_GUIDE = ROOT / "references/domain-guide.md"
ROUTER_SKILL = ROOT / "SKILL.md"


class JournalSubmissionRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        tests = json.loads(BEHAVIOR_TESTS.read_text(encoding="utf-8"))
        self.case = next(item for item in tests if item["id"] == "case-9-submission")

    def test_completed_manuscript_routes_to_submission(self) -> None:
        self.assertIn("完成 manuscript", self.case["prompt"])
        self.assertIn("只选择 rw-journal-submission 作为主 Skill。", self.case["must_do"])
        self.assertIn("登录投稿门户、填写字段或点击 Submit", self.case["must_not"])

    def test_handoff_is_listed_and_keeps_human_submit(self) -> None:
        guide = DOMAIN_GUIDE.read_text(encoding="utf-8")
        skill = ROUTER_SKILL.read_text(encoding="utf-8")
        self.assertIn("稿件版本、目标期刊、作者、披露、数据、伦理、引文与未解决项", guide)
        self.assertIn("登录门户、填写字段或点击 Submit", guide)
        self.assertIn("rw-journal-submission", skill)
        self.assertIn("路由器只交接材料和缺口", skill)


if __name__ == "__main__":
    unittest.main()
