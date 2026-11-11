# 分层证据凭据与上下文包

## 目的

一篇稿件产生多少张证据凭据，由正文、附件、图表和提取粒度决定。Evidence Credential Store 不设置总数量上限。脚本保存来源、层级、依赖、状态和 hash；模型只读取当前 Finding 的最小完整证据包。

这套内部结构借用 provenance、credential status 和 research object 的建模逻辑，但不是 W3C Verifiable Credential，也不声称具备数字签名或外部互操作性。来源见 `references/evidence-credential-sources.md`。

## 文件

```text
evidence-credentials.json       全部证据凭据和状态
context-packs/FIND-ID.json      一条 Finding 的 Paper Context Pack
review-ledger.json              Finding 连接 context_pack_id 和 evidence_credential_ids
```

## 层级

| 层 | 例子 |
|---|---|
| 来源 | 主文、Supplement、Protocol、Author response |
| 结构 | 页、章节、段落、表、图、标题、图例、脚注 |
| 语义 | 方法定义、分析人群、分母、单位、时间点、estimand、结果 |
| 判断 | claim、Finding、Review Credential |

父子关系用 `parent_id`。前后文用 `previous_id` 和 `next_id`。判断所必需的证据用 `required_dependencies`，补充材料用 `optional_dependencies`。

## 状态

```text
discovered → extracted → linked → verified
                         ↘ disputed
                         ↘ needs_input
verified → superseded | stale | revoked
```

- `verified`：定位、hash 和必要依赖都通过检查。
- `disputed`：不同证据或解释冲突，等待裁决。
- `needs_input`：缺页、OCR 失败、图表无法读取或必要材料不存在。
- `stale`：上游文件或必要依赖变化。
- `superseded`：有新版凭据替代。
- `revoked`：不得继续使用。

状态不是内容真假的证明。图表解释、统计含义和因果判断仍需语义检查。

## 根来源和覆盖门

每份主文或 Supplement 建一张 `source` 凭据。它的 `required_dependencies` 列出本次评审必须覆盖的页面、章节和视觉对象。

建立根来源时使用 `--source-file`。脚本保存文件路径、大小和 SHA-256。`gate` 重新计算当前文件 hash；文件内容变化时返回 BLOCK。

根来源只有在必要子凭据全部为 `verified` 后才能验证。缺少一项时，`gate` 返回 BLOCK。

不要把所有段落都设为每个 Finding 的依赖。根来源负责全文覆盖；Finding 依赖只保存形成该判断所需的证据。

## 图表证据包

一张表或图至少检查：

- 图表本体。
- caption、legend 和 footnote。
- Results 中对应文字。
- Methods 中的变量、模型和分析人群定义。
- 分母、单位、时间点和 estimand。
- 对应 Supplement 项。

必要项写入 `required_dependencies`。无法取得时用 `needs_input`，不以相似段落替代。

## Paper Context Pack

`pack` 从目标凭据开始计算必要依赖闭包，再加入父节点和相邻文字。根来源只作为版本和覆盖证明，不把它的全部子凭据放入模型上下文。

规则：

1. 目标、必要依赖、父节点和相邻节点必须是 `verified`。
2. 对应根来源必须通过全文覆盖门。
3. 超过 `max_credentials` 时整体 BLOCK，不截断依赖。
4. 超过 `max_estimated_tokens` 时整体 BLOCK，不截断文字或依赖。
5. Context Pack 保存来源 hash、凭据 hash、选择规则和 pack hash。
6. token 上限按序列化 JSON 的 UTF-8 字节数加固定余量估算。它是跨 tokenizer 的保守工程门，不是实际计费 token。

`max_credentials` 和 `max_estimated_tokens` 只控制一次发给模型的 Context Pack，可按运行环境调整。它们不限制 Evidence Credential Store 的总凭据数量。

## Finding 连接

Review Ledger 中的 Finding 可以增加：

```json
{
  "context_pack_id": "PACK-FIND-001",
  "evidence_credential_ids": ["EV-TABLE-002", "EV-FOOTNOTE-002"]
}
```

`record-credential` 会把这两个字段写入不可改写的 Finding snapshot。`validate-ledger` 检查 Finding、Context Pack 和当前凭据状态是否一致。

## Token 边界

脚本执行以下工作，不调用模型：

- ID、hash、层级、依赖和状态管理。
- 覆盖门、循环依赖和悬空引用检查。
- 失效传播。
- 必要依赖闭包和上下文包生成。
- Context Pack 与 Review Ledger 连接检查。

模型只处理 Context Pack 中的语义解释和判断。无论 Store 中有多少凭据，都不一次发送给模型。

批量提取时复制 `assets/evidence-credential-import-template.json`，生成一个 `credentials` 数组，再运行 `import`。批量导入只在本批记录进入内存后验证一次，允许根来源引用同批次中尚未排序到前面的子凭据。批次大小是执行参数，不是凭据总量限制。

## 停止条件

- 根来源没有验证，不形成 Context Pack。
- 必要依赖缺失、未验证、争议、失效或撤销，不形成确定性 Finding。
- 依赖闭包超过上限，不截断；拆分 Finding。
- 保守 token 上限超过预算，不截断；拆分 Finding。
- Context Pack hash 或任一凭据 hash 变化，原包失效。
- 根来源文件 hash 变化，先把来源标为 `stale`，再重新提取和签发。
- Review Ledger 的 Finding 没有当前 Context Pack，不能进入 synthesis。

## 2026-09-19 校验边界修复

- 空的根来源覆盖依赖不构成覆盖完成，返回 BLOCK。空目标、重复目标、空台账不返回 PASS。
- `validate-pack` 先验证 Store，再逐字段比较凭据和来源投影、目标集合、完整依赖闭包、预算及当前源文件 SHA-256。重新计算 `pack_hash` 不会让篡改文字或缺失证据通过。
- 被加入的父节点和相邻文字，其必要依赖也进入包。可选上下文开关不裁剪必要依赖。
- `selection.max_estimated_tokens` 保存生成时预算。旧包缺该字段时按 20000 检查；旧包不符合当前闭包时重新生成，不补造内容。
- 相同 `pack_id` 的多个文件视为歧义并返回 BLOCK。Pack 输出不得覆盖 Store，包括软链接和硬链接别名。
- JSON 重复键、NaN、Infinity、浮点溢出、错误容器类型、非法 page/bbox 和非正整数预算均阻断；依赖循环检查不依赖 Python 递归深度。
- hash 是完整性比对，不是签名。能够同时改写 Store、源文件和 hash 的一方仍可重建一致记录；脚本不认证记录者身份、人工核验动作或原文语义。必须另行保留可信原件与独立复核记录。
