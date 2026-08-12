# 方法来源

## 包内规则

- 2026-08-12：建立独立的 `RW Peer Review`，评审台账与作者的研究档案分开。
- 一条意见一条记录，状态不是 `open` 时必须写下场。
- 撤回意见必须连接说服它的来源。

## RW 系统关系

- `rw-claim-audit`：核验主张是否被来源支持，以及自有数字是否忠于原始结果。
- `rw-citation-audit`：核验引用身份、年份、DOI 和格式。
- `rw-research-referee`：用四问检查结论能否被证伪。
- `rw-journal-submission`：回应审稿意见和组织修改证据。

## 实现

- 台账结构、凭据哈希、Gate 和 Python 脚本随 Skill 提供。
- 脚本只验证记录结构和 Gate，不读取稿件内容，不替代人工判断。
