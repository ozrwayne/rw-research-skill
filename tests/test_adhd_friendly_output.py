from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
SECTION_START = "## 可选 ADHD 友好输出"


def extract_section(skill_text: str) -> str:
    start = skill_text.index(SECTION_START)
    end = skill_text.find("\n## ", start + len(SECTION_START))
    if end == -1:
        end = len(skill_text)
    return skill_text[start:end]


class AdhdFriendlyOutputTests(unittest.TestCase):
    def test_all_manifest_skills_have_the_same_optional_branch(self) -> None:
        sections = []
        for name in MANIFEST["skills"]:
            skill_text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            sections.append(extract_section(skill_text))

        self.assertEqual(21, len(sections))
        self.assertEqual(1, len(set(sections)))

    def test_branch_requires_explicit_output_request(self) -> None:
        section = extract_section(
            (SKILLS_ROOT / "rw-research-router" / "SKILL.md").read_text(encoding="utf-8")
        )
        required_rules = [
            "仅当用户明确要求",
            "不主动询问、介绍或推荐",
            "用户只披露有 ADHD",
            "默认只在当前任务中保持",
            "不保存诊断信息",
        ]
        for rule in required_rules:
            self.assertIn(rule, section)

    def test_branch_contains_focus_and_bold_contract(self) -> None:
        section = extract_section(
            (SKILLS_ROOT / "rw-claim-audit" / "SKILL.md").read_text(encoding="utf-8")
        )
        required_rules = [
            "只看这里",
            "用户现在只做的 1 件事",
            "暂存区",
            "每轮最多提出 1 个关键问题",
            "加粗当前任务、用户动作、结论和阻断状态",
            "不为缩短输出删除证据边界",
            "恢复点",
        ]
        for rule in required_rules:
            self.assertIn(rule, section)

    def test_branch_is_not_advertised_in_readme_or_skill_metadata(self) -> None:
        self.assertNotIn("ADHD", (ROOT / "README.md").read_text(encoding="utf-8"))
        for name in MANIFEST["skills"]:
            skill_text = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            _, frontmatter, _ = skill_text.split("---", 2)
            self.assertNotIn("ADHD", frontmatter)

    def test_representative_behavior_contracts_cover_opt_in_and_non_trigger(self) -> None:
        router_contracts = json.loads(
            (
                SKILLS_ROOT
                / "rw-research-router"
                / "references"
                / "behavior-tests.json"
            ).read_text(encoding="utf-8")
        )
        claim_contracts = json.loads(
            (
                SKILLS_ROOT
                / "rw-claim-audit"
                / "references"
                / "behavior-tests.json"
            ).read_text(encoding="utf-8")
        )
        ids = {record["id"] for record in router_contracts + claim_contracts}
        self.assertIn("case-12-adhd-opt-in", ids)
        self.assertIn("counterexample-13-adhd-disclosure-only", ids)
        self.assertIn("case-14-adhd-off", ids)
        self.assertIn("adhd-opt-in", ids)
        self.assertIn("adhd-disclosure-only", ids)
        self.assertIn("adhd-off", ids)


if __name__ == "__main__":
    unittest.main()
