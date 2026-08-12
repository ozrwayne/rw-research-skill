# Review Ledger JSON 结构

评审台账独立于 `rw-research-passport`。Passport 保存作者自己项目的材料和判断，评审台账保存对一份外来稿件的意见和处置。两者不共用文件，也不互相读取。

必需顶层字段：

- `schema_version`：固定为 `rw-peer-review/v1`。
- `review_id`：本次评审稳定 ID。
- `manuscript`：稿件对象。
- `stage`：`intake`、`panel`、`debate`、`synthesis`、`delivered` 或 `closed`。
- `updated_at`：UTC ISO 8601 时间。
- `reviewers`：Agent 数组。
- `sources`：证据来源数组。
- `findings`：评审意见数组。
- `credentials`：Review Credential 数组。
- `audit_log`：变更记录数组。

## Manuscript

必需字段：`id`、`title`、`journal`、`version`、`pointer`。

`journal` 决定领域和评审标准。`pointer` 是稿件位置，不复制全文。

## Reviewer

必需字段：`id`、`role`、`model_family`、`assigned_at`。

`id` 以 `agent:` 或 `human:` 开头。`role`：`method`、`domain`、`adversary` 或 `editor`。`model_family`：`claude`、`codex`、`human` 或 `other`。

一次评审的默认配置是两个打分 Agent（`method` 和 `domain`）、一个 `adversary` 和一个 `editor`。

## Source

必需字段：`id`、`type`、`title`、`pointer`、`added_at`。

`type`：`manuscript`、`reference`、`data` 或 `note`。意见的证据只能引用已登记的来源。

## Finding

一条评审意见一条记录。

必需字段：

- `id`：意见稳定 ID。
- `location`：稿件位置，写到页、表、图或段落。
- `quote`：被指出的原文。
- `problem`：为什么是问题。
- `fix`：怎么改。
- `publication_impact`：`blocking` 或 `non_blocking`，即影不影响录用。
- `status`：`open`、`sustained`、`narrowed`、`withdrawn`、`answered`、`deferred` 或 `needs_input`。
- `evidence_ids`：支持这条意见的来源 ID 数组。
- `raised_by`：提出者，必须是已登记的审稿人 ID。
- `recorded_at`：UTC ISO 8601 时间。

可选字段：

- `resolution_note`：下场说明。状态不是 `open` 时必需。
- `credential_id`：处置被讨论确认时，指向对应的 Review Credential。

规则：

- 状态不是 `open` 时必须写 `resolution_note`，意见不能空着消失。
- `withdrawn` 必须至少连接一个来源 ID，即撤回意见时要写清被哪份证据说服。
- `raised_by` 必须是已登记 Agent，综合 Agent 据此追溯每条意见的来处。
- 意见范围变化时用 `narrowed`，并在说明里写清收窄到什么范围。

## Review Credential

记录一条意见的处置是怎么定下来的。

必需字段：

- `id`：凭据稳定 ID。
- `finding_id`：对应的意见 ID。
- `session_id`：辩论或讨论的稳定 ID。
- `record_pointer`：原始讨论记录位置。
- `settled_by`：参与确认者数组，使用 `human:ID` 或 `agent:ID`。
- `authority`：`advisory`、`agent_consensus`、`delegated` 或 `human_confirmed`。
- `basis`：`evidence`、`reasoning` 或 `delegated_choice`。使用 `evidence` 时至少连接一个来源 ID。
- `scope`：该处置适用的范围。
- `finding_snapshot`：签发时的 `status`、`publication_impact`、`resolution_note` 和 `evidence_ids`。
- `issued_at`：UTC ISO 8601 时间。
- `supersedes`：被替代凭据的 ID；没有时为 `null`。
- `content_hash`：对其余字段计算的 SHA-256。

规则：

- `advisory` 凭据不能撤回一条意见。撤回是终局判断，需要 Agent 共识、已委托权限或人类确认。
- Credential 写入后不改写。处置变化时新增 Credential，并用 `supersedes` 指向旧的。
- `content_hash` 只检查凭据内容是否被改动，不证明评审判断正确。

## 阶段限制

`stage` 是 `synthesis` 或 `delivered` 时，不允许存在 `open` 且 `blocking` 的意见。
