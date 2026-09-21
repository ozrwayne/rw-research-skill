# 验收

## 独立运行

- 不要求私人工作区、Obsidian、个人语料目录或预设 research-lab 存在。
- 用户只提供当前任务材料时，仍能完成方法选择、处理和输出。
- 网络不可用时，当前事实标记待核验，不把访问失败写成事实不存在。

## 内容

- 保留用户原问题，区分事实、推断和未知事项。
- 关键结论有来源或明确证据缺口。
- 至少有 24 条知识原子、8 条公理和 6 个行为合同。
- 行为合同包含至少 4 个正常案例和 2 个停止条件反例。
- 输出包含：结构化论文卡片或批量表。、原文定位、置信度和复核状态。、缺失项、冲突和待补材料。
- Paper Case 模式保存来源 hash、配置 hash、文本 locator、视觉分段 locator 和阶段状态。
- 跨页表格拼接后仍能回到每一页的 bbox。
- LitNet 接续只生成预览，不能绕过 Claim Audit 门禁直接写入。

## 结构

- `SKILL.md` 必须包含 `name` 和 `description`；内部模块可声明 `metadata.internal: true`，与发行入口清单一致。
- `python3 scripts/self_check.py` 通过。
- `python3 -m unittest -v tests/test_paper_case.py` 通过。

静态结构检查、确定性脚本测试和模型行为验证分别记录。合同数量或 self_check 通过不表示合同已由模型执行；缺少运行记录的合同保持未执行状态。
