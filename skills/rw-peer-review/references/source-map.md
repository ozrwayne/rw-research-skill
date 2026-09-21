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
- 判断学习使用独立 `judgment-learning/FIND-ID.json` 旁车，保持 `rw-peer-review/v1` 台账兼容。
- 判断旁车的方法来源摘要保存在 `references/source-evidence.md`。
- 零经验 reviewer training、RQI、COPE 和 EQUATOR 的专项证据保存在 `references/novice-review-sources.md`。
- 分层证据、provenance、状态和 research object 的来源保存在 `references/evidence-credential-sources.md`。
- 主要来源包括 Cognitive Apprenticeship、自我解释、deliberate practice、COPE、EQUATOR、ASA p-value statement、ICH E9(R1) 和交互模型论文。来源用于定义核对步骤，不替代当前稿件证据。
- 证据凭据结构参考 W3C PROV、W3C Verifiable Credentials Data Model 2.0 和 RO-Crate。当前实现是内部 JSON，不宣称符合这些标准。
