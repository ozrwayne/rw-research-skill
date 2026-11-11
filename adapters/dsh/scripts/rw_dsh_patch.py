#!/usr/bin/env python3
"""在运行时解析仓库根目录，生成 DSH 的 --patch 覆盖层。

仓库里只存模板（cordis.patch.example.yml），绝对路径不进 Git。
这样同一份适配可以在任何机器、任何 checkout 路径下跑。

用法：

    python3 adapters/dsh/scripts/rw_dsh_patch.py --out /tmp/rw-dsh.patch.yml
    python3 adapters/dsh/scripts/rw_dsh_patch.py --print
    python3 adapters/dsh/scripts/rw_dsh_patch.py --out /tmp/p.yml --with-mcp stdio
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ADAPTER_DIR = Path(__file__).resolve().parents[1]
TEMPLATE = ADAPTER_DIR / "cordis.patch.example.yml"
MCP_TEMPLATES = {
    "stdio": ADAPTER_DIR / "config" / "mcp.stdio.example.yml",
    "streamable-http": ADAPTER_DIR / "config" / "mcp.streamable-http.example.yml",
}


def repo_root() -> Path:
    """仓库根目录：先问 Git，问不到就按目录层级回退。"""
    git = shutil.which("git")
    if git is not None:
        try:
            out = subprocess.run(
                [git, "rev-parse", "--show-toplevel"],
                cwd=ADAPTER_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(out.stdout.strip()).resolve()
        except (subprocess.CalledProcessError, OSError):
            pass
    return ADAPTER_DIR.parents[1]


def default_run_log(root: Path) -> Path:
    """研究事件日志默认落在系统临时目录，不写进仓库。"""
    override = os.environ.get("RW_DSH_RUN_LOG")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "rw-dsh" / f"{root.name}-research-events.jsonl"


def yaml_escape(value: str) -> str:
    """按 YAML 双引号标量转义。路径里有空格和中文，一律带引号。"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def module_url(path: Path) -> str:
    """插件路径写成 file:// URL，避开空格和非 ASCII 在 ESM 解析里的歧义。"""
    return path.resolve().as_uri()


def render(root: Path, run_log: Path, with_mcp: list[str]) -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    recorder = ADAPTER_DIR / "plugins" / "rw-research-recorder.mjs"
    replacements = {
        "RW_SKILLS_DIR_PLACEHOLDER": yaml_escape(str(root / "skills")),
        "RW_FIXTURE_DIR_PLACEHOLDER": yaml_escape(str(ADAPTER_DIR / "fixtures" / "skills")),
        "RW_RECORDER_URL_PLACEHOLDER": yaml_escape(module_url(recorder)),
        "RW_RUN_LOG_PLACEHOLDER": yaml_escape(str(run_log)),
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    leftovers = [key for key in replacements if key in text]
    if leftovers:
        raise SystemExit(f"模板里还有没替换的占位符: {', '.join(leftovers)}")
    for transport in with_mcp:
        block = MCP_TEMPLATES[transport].read_text(encoding="utf-8")
        fixture = ADAPTER_DIR / "fixtures" / "mcp" / "rw_fixture_mcp_server.mjs"
        block = block.replace("RW_FIXTURE_MCP_PLACEHOLDER", yaml_escape(str(fixture)))
        text = text.rstrip("\n") + "\n\n" + block
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 RW → DSH 的 cordis 补丁覆盖层")
    parser.add_argument("--out", type=Path, help="写到这个路径；不给就必须用 --print")
    parser.add_argument("--print", action="store_true", dest="to_stdout", help="打到标准输出")
    parser.add_argument("--run-log", type=Path, help="研究事件 JSONL 路径")
    parser.add_argument(
        "--with-mcp",
        action="append",
        default=[],
        choices=sorted(MCP_TEMPLATES),
        help="附加一段 MCP server 配置，可重复",
    )
    args = parser.parse_args()
    if args.out is None and not args.to_stdout:
        parser.error("要么 --out，要么 --print")

    root = repo_root()
    if not (root / "skills").is_dir():
        raise SystemExit(f"没在 {root} 下找到 skills/，仓库根目录解析失败")
    run_log = args.run_log.resolve() if args.run_log else default_run_log(root)

    text = render(root, run_log, args.with_mcp)
    if args.to_stdout:
        sys.stdout.write(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"补丁已写入 {args.out}", file=sys.stderr)
        print(f"研究事件日志 {run_log}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
