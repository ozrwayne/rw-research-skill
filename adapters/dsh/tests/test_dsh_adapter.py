#!/usr/bin/env python3
"""DSH 适配的结构验收。

跑法：

    python3 -m unittest discover -s adapters/dsh/tests

分两层：

- 纯 Python 部分（补丁渲染、占位符、隐私、fixture 完整性）永远跑。
- DSH 部分（Skill 发现、正文加载、热改、MCP、事件投影）需要一个装了
  @deepseek-ai/dsh 的目录，用 RW_DSH_RUNTIME_DIR 指过去。没有就 skip，
  不伪造通过。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ADAPTER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ADAPTER_DIR.parents[1]
PROBE = ADAPTER_DIR / "tests" / "probe_dsh.mjs"
PATCH_SCRIPT = ADAPTER_DIR / "scripts" / "rw_dsh_patch.py"

PUBLIC_ENTRIES = ["rw-research-router", "rw-paper-extractor", "rw-research-referee", "rw-phd-write"]

_PROBE_CACHE: dict[str, object] | None = None
_PROBE_ERROR: str | None = None


def _optional_yaml():
    try:
        import yaml
    except ImportError:
        return None
    return yaml


def probe_report() -> dict:
    """跑一次 node 探针，结果缓存给所有用例共用。"""
    global _PROBE_CACHE, _PROBE_ERROR
    if _PROBE_CACHE is not None or _PROBE_ERROR is not None:
        if _PROBE_ERROR:
            raise unittest.SkipTest(_PROBE_ERROR)
        return _PROBE_CACHE  # type: ignore[return-value]
    try:
        completed = subprocess.run(
            ["node", str(PROBE)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        _PROBE_ERROR = "没有 node，跳过 DSH 结构验收"
        raise unittest.SkipTest(_PROBE_ERROR)
    if completed.returncode != 0:
        raise AssertionError(f"探针退出码 {completed.returncode}\n{completed.stderr[-2000:]}")
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    if report.get("skipped"):
        _PROBE_ERROR = f"没找到 DSH 运行时：{report.get('reason')}"
        raise unittest.SkipTest(_PROBE_ERROR)
    _PROBE_CACHE = report
    return report


class PatchRenderingTest(unittest.TestCase):
    """补丁在运行时生成，绝对路径不进仓库。"""

    def test_template_keeps_placeholders(self) -> None:
        text = (ADAPTER_DIR / "cordis.patch.example.yml").read_text(encoding="utf-8")
        for placeholder in (
            "RW_SKILLS_DIR_PLACEHOLDER",
            "RW_FIXTURE_DIR_PLACEHOLDER",
            "RW_RECORDER_URL_PLACEHOLDER",
            "RW_RUN_LOG_PLACEHOLDER",
        ):
            self.assertIn(placeholder, text, f"模板里少了占位符 {placeholder}")

    def test_render_resolves_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch.yml"
            subprocess.run(
                [sys.executable, str(PATCH_SCRIPT), "--out", str(out)],
                check=True,
                capture_output=True,
                text=True,
            )
            text = out.read_text(encoding="utf-8")
        self.assertIn(str(REPO_ROOT / "skills"), text)
        self.assertNotIn("PLACEHOLDER", text, "渲染后不该还有占位符")
        self.assertIn("providerName: rw-research", text)
        self.assertIn("includeDefaultRoots: false", text)

    def test_render_can_append_mcp_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch.yml"
            subprocess.run(
                [
                    sys.executable, str(PATCH_SCRIPT),
                    "--out", str(out),
                    "--with-mcp", "stdio",
                    "--with-mcp", "streamable-http",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            text = out.read_text(encoding="utf-8")
        self.assertIn("serverName: rwfixture", text)
        self.assertIn("transport: streamable-http", text)
        self.assertNotIn("PLACEHOLDER", text)

    def test_rendered_patch_is_a_loadable_patch_list(self) -> None:
        """DSH 的补丁层必须是顶层 YAML 数组，空文件或非数组会抛。"""
        yaml = _optional_yaml()
        if yaml is None:
            self.skipTest("没有 PyYAML，跳过补丁结构解析")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch.yml"
            subprocess.run(
                [sys.executable, str(PATCH_SCRIPT), "--out", str(out), "--with-mcp", "stdio"],
                check=True, capture_output=True, text=True,
            )
            # `!!js` 是 DSH loader 自己的标签，标准解析器不认，注册成直通。
            loader = yaml.SafeLoader
            loader.add_constructor("!js", lambda self, node: self.construct_scalar(node))
            data = yaml.load(out.read_text(encoding="utf-8"), Loader=loader)
        self.assertIsInstance(data, list, "补丁层必须是顶层数组")
        inserted = [row for patch in data for row in patch.get("insert", [])]
        ids = [row["id"] for row in inserted]
        self.assertIn("rw-research-skills", ids)
        self.assertIn("rw-research-recorder", ids)
        self.assertIn("rw-mcp-fixture-stdio", ids)
        for patch in data:
            self.assertNotIn("id", patch, "这份补丁只 insert，不改任何现有行")
        skills_row = next(row for row in inserted if row["id"] == "rw-research-skills")
        self.assertEqual(skills_row["config"]["customSkillDirs"], [str(REPO_ROOT / "skills")])
        self.assertIs(skills_row["config"]["includeDefaultRoots"], False)
        recorder_row = next(row for row in inserted if row["id"] == "rw-research-recorder")
        self.assertTrue(recorder_row["name"].startswith("file://"))


def dsh_bin() -> str | None:
    """dsh 可执行文件：优先 RW_DSH_BIN，其次运行时目录里的 .bin/dsh。"""
    explicit = os.environ.get("RW_DSH_BIN")
    if explicit and Path(explicit).exists():
        return explicit
    runtime = os.environ.get("RW_DSH_RUNTIME_DIR")
    if runtime:
        candidate = Path(runtime) / "node_modules" / ".bin" / "dsh"
        if candidate.exists():
            return str(candidate)
    return None


class DshConfigComposeTest(unittest.TestCase):
    """让 DSH 自己的 composer 解析这份补丁。--dump-config 不 boot、不要凭据。"""

    def test_headless_profile_composes_with_the_patch(self) -> None:
        binary = dsh_bin()
        if binary is None:
            self.skipTest("没找到 dsh 可执行文件，设 RW_DSH_BIN 或 RW_DSH_RUNTIME_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            patch = Path(tmp) / "rw.patch.yml"
            subprocess.run(
                [sys.executable, str(PATCH_SCRIPT), "--out", str(patch), "--with-mcp", "stdio"],
                check=True, capture_output=True, text=True,
            )
            env = dict(os.environ, DSH_HOME=str(Path(tmp) / "dsh-home"))
            completed = subprocess.run(
                [binary, "--profile", "headless", "--patch", str(patch), "--dump-config"],
                capture_output=True, text=True, timeout=300, env=env, cwd=REPO_ROOT,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        dumped = completed.stdout
        for row in ("rw-research-skills", "rw-research-fixture-skills", "rw-research-recorder", "rw-mcp-fixture-stdio"):
            self.assertIn(f"id: {row}", dumped, f"composer 里没有 {row}")
        self.assertNotIn("patch: entry", completed.stderr, "有补丁没命中任何行")
        self.assertNotIn("patch insert: entry", completed.stderr)


class RepositoryHygieneTest(unittest.TestCase):
    """适配目录不许带本机路径、用户名或凭据。"""

    def _tracked_files(self) -> list[Path]:
        return [path for path in ADAPTER_DIR.rglob("*") if path.is_file() and "__pycache__" not in path.parts]

    def test_no_hardcoded_user_or_machine_paths(self) -> None:
        # 模式按片段拼，免得这个文件自己命中自己。
        home = "/" + "Users" + "/[A-Za-z0-9._-]+"
        volume = "/" + "Volumes" + "/[^\\s\"']+"
        forbidden = re.compile("|".join([home, volume]))
        offenders = []
        for path in self._tracked_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for match in forbidden.finditer(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
        self.assertEqual(offenders, [], "适配目录里出现了本机绝对路径或用户名")

    def test_no_credentials(self) -> None:
        forbidden = re.compile("|".join([
            "sk" + "-[A-Za-z0-9]{16,}",
            "ghp" + "_[A-Za-z0-9]{16,}",
            "Bearer" + r"\s+[A-Za-z0-9._-]{16,}",
        ]))
        offenders = []
        for path in self._tracked_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if forbidden.search(text):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], "适配目录里出现了疑似凭据")

    def test_fixture_skill_is_outside_skills_dir(self) -> None:
        """fixture Skill 不能混进 21 个 Skill，否则 check_repository.py 会挂。"""
        manifest = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
        actual = {path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir()}
        self.assertEqual(actual, set(manifest["skills"]))
        self.assertNotIn("rw-dsh-fixture-echo", actual)


class FixtureTaskTest(unittest.TestCase):
    """3 个研究 fixture 声明的 Skill 必须真实存在。"""

    def _fixtures(self) -> list[tuple[Path, dict]]:
        out = []
        for path in sorted((ADAPTER_DIR / "fixtures" / "tasks").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            block = text.split("---", 2)[1]
            meta: dict = {}
            key = None
            for line in block.splitlines():
                if not line.strip():
                    continue
                if line.startswith("  - "):
                    meta.setdefault(key, []).append(line[4:].strip())
                elif ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()
                    meta[key] = value if value else []
            out.append((path, meta))
        return out

    def test_three_fixtures_exist(self) -> None:
        self.assertEqual(len(self._fixtures()), 3)

    def test_declared_skills_exist(self) -> None:
        manifest = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
        known = set(manifest["skills"])
        for path, meta in self._fixtures():
            self.assertIn(meta["entry_skill"], PUBLIC_ENTRIES, f"{path.name} 的入口不是公开入口")
            for skill in meta.get("downstream_skills", []):
                self.assertIn(skill, known, f"{path.name} 声明了不存在的下游 Skill {skill}")

    def test_fixtures_cover_three_research_stages(self) -> None:
        entries = {meta["entry_skill"] for _, meta in self._fixtures()}
        self.assertEqual(entries, {"rw-research-router", "rw-research-referee", "rw-phd-write"})


class DshSkillDiscoveryTest(unittest.TestCase):
    def test_all_21_skills_discovered(self) -> None:
        skills = probe_report()["skills"]
        manifest = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(skills["discovered_names"], sorted(manifest["skills"]))
        self.assertEqual(skills["discovered_count"], len(manifest["skills"]))

    def test_discovery_uses_the_custom_root_only(self) -> None:
        self.assertEqual(probe_report()["skills"]["sources"], ["custom"])

    def test_public_entries_load_full_body(self) -> None:
        bodies = probe_report()["skills"]["entry_bodies"]
        for name in PUBLIC_ENTRIES:
            with self.subTest(entry=name):
                self.assertTrue(bodies[name]["loaded"])
                self.assertGreater(bodies[name]["bytes"], 500)
                self.assertEqual(bodies[name]["provider"], "rw-research")
                self.assertTrue(bodies[name]["resource_base"].endswith(f"skills/{name}"))

    def test_body_edit_is_visible_without_a_second_copy(self) -> None:
        live = probe_report()["skills"]["live_edit"]
        self.assertTrue(live["reloaded_sees_new_body"], "改了主来源正文，DSH 下一次加载没读到新内容")
        self.assertTrue(live["resource_base"].endswith("fixtures/skills/rw-dsh-fixture-echo"))

    def test_internal_metadata_does_not_gate_dsh(self) -> None:
        """已知缺口：DSH 不认 metadata.internal，21 个 Skill 全部对模型可见。"""
        skills = probe_report()["skills"]
        self.assertEqual(skills["model_invocable_count"], 21)
        self.assertEqual(skills["user_invocable_count"], 21)


class DshMcpTest(unittest.TestCase):
    def test_stdio_tools_are_discovered_and_callable(self) -> None:
        stdio = probe_report()["mcp"]["stdio"]
        self.assertEqual(stdio["tool_names"], ["mcp__rwfixture__count_sources", "mcp__rwfixture__echo_claim"])
        self.assertFalse(stdio["is_error"])
        self.assertIn("RW_FIXTURE_ECHO:handover checklist reduces errors", stdio["call_text"])

    def test_streamable_http_tools_are_discovered_and_callable(self) -> None:
        http = probe_report()["mcp"]["streamable_http"]
        self.assertEqual(http["tool_names"], ["mcp__rwfixturehttp__count_sources", "mcp__rwfixturehttp__echo_claim"])
        self.assertFalse(http["is_error"])
        self.assertIn("RW_FIXTURE_COUNT:3", http["call_text"])

    def test_tool_names_keep_the_mcp_shape(self) -> None:
        pattern = re.compile(r"^mcp__[A-Za-z0-9_-]{1,32}__.+$")
        for transport in ("stdio", "streamable_http"):
            for name in probe_report()["mcp"][transport]["tool_names"]:
                with self.subTest(transport=transport, tool=name):
                    self.assertRegex(name, pattern)


class RecorderProjectionTest(unittest.TestCase):
    def test_covers_submit_pre_tool_post_tool_and_stop(self) -> None:
        recorder = probe_report()["recorder"]
        for stage in ("task_entry", "tool_pre", "tool_post", "stop"):
            self.assertIn(stage, recorder["stages"])

    def test_stage_gate_is_recorded_as_a_pair(self) -> None:
        stages = probe_report()["recorder"]["stages"]
        self.assertIn("stage_gate_open", stages)
        self.assertIn("stage_gate_closed", stages)
        self.assertLess(stages.index("stage_gate_open"), stages.index("stage_gate_closed"))

    def test_skill_load_is_distinguished_from_ordinary_tool_calls(self) -> None:
        recorder = probe_report()["recorder"]
        self.assertIn("skill_selected", recorder["stages"])
        self.assertEqual(recorder["skill_selected"], "rw-search-strategy")

    def test_mcp_calls_and_failures_are_marked(self) -> None:
        recorder = probe_report()["recorder"]
        self.assertEqual(recorder["mcp_flagged"], 1)
        self.assertEqual(recorder["failed_tool_post"], 1)

    def test_stop_reason_is_kept(self) -> None:
        self.assertEqual(probe_report()["recorder"]["stop_reason"], "completed")


if __name__ == "__main__":
    unittest.main()
