import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from scripts.check_agent_parity import validate_agent_parity


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def example_skill(*, agent_target: str | None = "rw-example", write_agent_card: bool = True):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skill = root / "skills" / "rw-example"
        (skill / "agents").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: rw-example\ndescription: |\n  test\n---\n# Test\n",
            encoding="utf-8",
        )
        if write_agent_card:
            (skill / "agents" / "openai.yaml").write_text(
                f'interface:\n  default_prompt: "Use ${agent_target} to do X."\n',
                encoding="utf-8",
            )
        yield root


class AgentParityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    def test_every_skill_resolves_to_the_same_target_in_codex_and_claude_code(self):
        self.assertEqual(validate_agent_parity(self.manifest), [])

    def test_mismatched_default_prompt_target_is_rejected(self):
        manifest = {"skills": ["rw-example"]}
        with example_skill(agent_target="rw-other") as root:
            failures = validate_agent_parity(manifest, root)
        self.assertTrue(any("expected $rw-example" in failure for failure in failures))

    def test_missing_agent_card_is_rejected(self):
        manifest = {"skills": ["rw-example"]}
        with example_skill(write_agent_card=False) as root:
            failures = validate_agent_parity(manifest, root)
        self.assertTrue(any("agents/openai.yaml is missing" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
