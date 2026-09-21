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
- 输出包含：文内引用与参考文献双向核对表。、作者消歧、年份、DOI、排序和格式问题清单。、PASS、REVIEW、BLOCK 和 STALE 状态。

## 结构

- `SKILL.md` 保留 `name`、`description`；内部模块可带 `metadata.internal`。
- `python3 scripts/self_check.py` 通过。

- 本地正则预检的 structural_status=PASS 不提升为最终 PASS；identity_verification=NOT_CHECKED 保持 REVIEW。
- 双作者引用按首作者匹配，平衡的 DOI 括号保留，单作者同姓消歧也检查。
- 结果文件不得覆盖输入文稿。

静态结构检查、确定性脚本测试和模型行为验证分别记录。合同数量或 self_check 通过不表示合同已由模型执行；缺少运行记录的合同保持未执行状态。
