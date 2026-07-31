#!/usr/bin/env python3
"""Build a public, compact RW Research Skill edition for SkillHub."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path


MAX_FILES = 200
EXCLUDED_REFERENCES = {"source-evidence.md"}
PRIVATE_MARKERS = re.compile(
    r"lsss|roland|wayne|local[_ -]|"
    r"user[-_]provided[-_]supervisor|rw[-_]journal[-_]submission_and_local",
    re.IGNORECASE,
)


def public_text(text: str, path: Path) -> str:
    replacements = {
        "Runs without a private local workspace or preset research-lab; use user-provided material and bundled public-source methods.": "Uses user-provided material and bundled public-source methods.",
        "打开 `references/source-map.md` 中的官方链接核验并记录日期。": "打开相关官方来源核验并记录日期。",
        "、Obsidian、个人语料目录或预设 research-lab": "",
        "、个人语料目录或预设 research-lab": "",
        "不要求私人工作区、Obsidian 存在。": "不依赖预设本地目录。",
        "任何人的私人工作区和个人知识库。": "用户未提供的本地目录和个人知识库。",
        "预设的 research-lab 目录。": "预设工具目录。",
        "本地 research-lab 是可选集成，不是运行前提。": "预设工具目录不是运行前提。",
        "没有预设本地 research-lab 也能工作": "不依赖预设工具目录",
        "本机没有 research-lab": "本机没有预设工具目录",
        "local_hard_dependencies": "hard_dependencies",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    if PRIVATE_MARKERS.search(text):
        raise ValueError(f"private marker remains in {path}")
    return text


def public_atoms(path: Path) -> str:
    records: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record.pop("original", None)
        for field in ("source", "source_kind"):
            value = record.get(field)
            if isinstance(value, str) and PRIVATE_MARKERS.search(value):
                record[field] = "packaged_internal_rule"
        atom_type = record.get("type")
        if isinstance(atom_type, str) and atom_type.startswith("local_"):
            record["type"] = atom_type.removeprefix("local_") or "rule"
        rendered = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        records.append(public_text(rendered, path))
    return "\n".join(records) + "\n"


def public_reference(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.name == "source-map.md" and PRIVATE_MARKERS.search(text):
        return "本模块的来源记录包含不进入公共包的内部规则，没有公开来源入口。\n"
    return public_text(text, path)


def module_text(skill: Path) -> str:
    parts = [public_text((skill / "SKILL.md").read_text(encoding="utf-8"), skill / "SKILL.md").rstrip()]
    parts.append("\n## 打包参考资料")
    references = skill / "references"
    for path in sorted(references.iterdir()):
        if not path.is_file() or path.name in EXCLUDED_REFERENCES:
            continue
        content = public_atoms(path) if path.name == "atoms.jsonl" else public_reference(path)
        parts.append(f"\n### {path.name}\n\n{content.rstrip()}")
    return "\n".join(parts) + "\n"


def runtime_files(skill: Path):
    for base_name in ("assets", "scripts"):
        source = skill / base_name
        if not source.is_dir():
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.name != "self_check.py" and path.suffix != ".pyc":
                yield base_name, path


def validate_skill_sources(skill: Path) -> None:
    module_text(skill)
    for _, path in runtime_files(skill):
        public_text(path.read_text(encoding="utf-8"), path)


def write_root(output: Path, version: str, entries: list[dict], skills: list[str]) -> None:
    items = "\n".join(
        f"- `{entry['name']}`：{entry['label']}。{entry['intent']}"
        for entry in entries
    )
    (output / "SKILL.md").write_text(
        f"""---
slug: rw-research-skill
displayName: RW Research Skill
version: {version}
summary: 通过 4 个入口处理研究启动、论文证据、研究审查和论文写作。
license: Apache-2.0
---

# RW Research Skill

这个包共 {len(skills)} 个科研模块，其中 {len(entries)} 个是公开入口，{len(skills) - len(entries)} 个是内部模块。用户不需要先理解内部模块名称。

用户可以提供研究想法、文献、数据、草稿、审稿意见，或直接说明卡在哪里。一次只推进当前一步。

## 对外入口

{items}

入口和内部模块的归属见 `MANIFEST.json`。内部模块保存在 `modules/`，已有调用仍可继续使用。

## 边界

- 只使用用户本轮提供的材料和公开来源。
- 需要当前文献、期刊政策、工具状态或 API 信息时，回到官方来源核验。
- 不生成不存在的论文、数据、DOI、期刊要求或工具结果。
- 不把通用流程当成临床、伦理或统计审批。
""",
        encoding="utf-8",
    )


def write_readme(output: Path, version: str, entries: list[dict], skills: list[str]) -> None:
    entry_items = "\n".join(f"- `{entry['name']}`：{entry['label']}。" for entry in entries)
    (output / "README.md").write_text(
        f"""# RW Research Skill

版本：`{version}`

这是 SkillHub 发行版。它共包含 {len(skills)} 个科研模块，其中 {len(entries)} 个是公开入口，{len(skills) - len(entries)} 个是内部模块。每个模块的参考资料已合并。公共版不包含私人工作区说明、个人研究记录或本地决策来源。本地规则统一标为 `packaged_internal_rule`。

## 对外入口

{entry_items}

内部模块归属见 `MANIFEST.json`。降级条件和替代动作见 `DEGRADATION_REGISTRY.json`，4 个入口的场景合同见 `DEGRADATION_SCENARIOS.json`。构建规则见 `PUBLIC_RELEASE_POLICY.md`。
""",
        encoding="utf-8",
    )
    (output / "PUBLIC_RELEASE_POLICY.md").write_text(
        """# 公共发行规则

- 发行目录最多 200 个文件。
- 不包含私人工作区路径、个人研究状态、项目名称、内部决策记录或个人来源标签。
- 保留知识原子已有的公开来源标识和日期；本地来源标为 `packaged_internal_rule`。
- 保留通过隐私检查的 `source-map.md`；包含本地决策的来源图只保留说明。
- 每次构建后必须运行隐私扫描和文件数检查。
""",
        encoding="utf-8",
    )


def copy_runtime_files(skill: Path, output: Path) -> None:
    target_names = {"assets": "templates", "scripts": "tools"}
    for base_name, path in runtime_files(skill):
        source = skill / base_name
        destination = output / target_names[base_name] / skill.name / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = path.read_text(encoding="utf-8")
        destination.write_text(public_text(content, path), encoding="utf-8")


def validate(output: Path) -> list[Path]:
    files = sorted(path for path in output.rglob("*") if path.is_file())
    if len(files) > MAX_FILES:
        raise ValueError(f"SkillHub release has {len(files)} files; limit is {MAX_FILES}")
    for path in files:
        if path.name == "LICENSE":
            continue
        public_text(path.read_text(encoding="utf-8"), path)
    return files


def build_zip(output: Path, version: str) -> Path:
    archive = output.parent / f"rw-research-skill-{version}-skillhub.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            bundle.write(path, path.relative_to(output))
    return archive


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    skills = list(dict.fromkeys(manifest["skills"]))
    entries = manifest["entry_skills"]
    output = root / "dist" / "skillhub"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    write_root(output, version, entries, skills)
    write_readme(output, version, entries, skills)
    shutil.copy2(root / "LICENSE", output / "LICENSE")
    (output / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "rw-entry-manifest/v1",
                "name": manifest["name"],
                "version": manifest["version"],
                "entry_skills": entries,
                "skills": skills,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copy2(root / "docs" / "degradation-registry.json", output / "DEGRADATION_REGISTRY.json")
    shutil.copy2(root / "docs" / "degradation-scenarios.json", output / "DEGRADATION_SCENARIOS.json")
    for name in skills:
        skill = root / "skills" / name
        validate_skill_sources(skill)
        module = output / "modules" / f"{name}.md"
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(module_text(skill), encoding="utf-8")
        copy_runtime_files(skill, output)

    files = validate(output)
    archive = build_zip(output, version)
    print(json.dumps({"files": len(files), "output": str(output), "archive": str(archive)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
