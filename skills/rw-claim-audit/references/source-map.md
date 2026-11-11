# 方法来源

## 包内规则

- 2026-07-13：建立独立的 `RW Claim Audit`。
- 引用存在、格式正确和支持具体主张分开检查。
- 无法回到来源原文时，不给 `VERIFIED`。

## RW 系统关系

- `rw-paper-extractor`：保存页码、段落、表、图和补充材料位置。
- `rw-phd-write`：建立 claim-to-source 表，按来源范围限制句子范围。
- `rw-research-referee`：检查因果强度、替代解释和外推边界。

## 实现

- Verdict、Gate、JSON 结构和 Python 脚本随 Skill 提供。
- 脚本只验证记录结构和 Gate，不自动下载论文，不替代人工读取原文。
