# Passport JSON 结构

必需顶层字段：

- `schema_version`：固定为 `rw-research-passport/v1`。
- `project_id`：项目稳定 ID。
- `title`：项目名称。
- `stage`：`question`、`discovery`、`extraction`、`synthesis`、`design`、`analysis`、`writing`、`review`、`submission` 或 `closed`。
- `updated_at`：UTC ISO 8601 时间。
- `materials`：材料数组。
- `decisions`：判断数组。
- `unknowns`：未知项数组。
- `handoffs`：交接数组。
- `credentials`：Research Credential 数组。旧版 Passport 可以缺少该字段；新建 Passport 必须包含。
- `audit_log`：变更记录数组。

## Material

必需字段：`id`、`type`、`title`、`source_pointer`、`status`、`added_at`。

`status`：`raw`、`extracted`、`verified`、`rejected` 或 `superseded`。

可选字段：

- `content_sha256`：当前登记版本的 SHA-256。
- `supersedes_id`：当前材料替代的旧材料 ID。

## Decision

必需字段：`id`、`statement`、`status`、`evidence_ids`、`recorded_at`。

`status`：`proposed`、`confirmed`、`rejected` 或 `superseded`。

## Unknown

必需字段：`id`、`question`、`status`。

`status`：`open`、`resolved` 或 `blocked`。

## Handoff

必需字段：`id`、`from_stage`、`to_stage`、`material_ids`、`status`、`recorded_at`。

`status`：`prepared`、`accepted` 或 `rejected`。

## Research Credential

必需字段：

- `id`：凭据稳定 ID。
- `decision_id`：对应的判断 ID。
- `session_id`：会议、头脑风暴或讨论的稳定 ID。
- `record_pointer`：会议纪要、聊天记录或其他原始讨论记录的位置。
- `settled_by`：参与确认者数组，使用 `human:ID` 或 `agent:ID`。
- `authority`：`advisory`、`agent_consensus`、`delegated` 或 `human_confirmed`。
- `basis`：`evidence`、`reasoning` 或 `delegated_choice`。使用 `evidence` 时至少连接一个材料 ID。
- `scope`：该决定适用的项目、阶段或任务范围。
- `decision_snapshot`：签发时的 `statement`、`status`、`basis` 和 `evidence_ids`。
- `unknown_ids`：签发时仍未关闭的相关未知项。
- `issued_at`：UTC ISO 8601 时间。
- `supersedes`：被替代 Credential 的 ID；没有时为 `null`。
- `content_hash`：对 Credential 其余字段计算的 SHA-256。

Credential 是决定形成过程的记录，不是研究结论正确性的证明。决定改变时新增 Credential，不改写旧 Credential。

材料 hash 变化时，不创造新的状态枚举。旧材料和依赖判断使用 `superseded`，仍引用旧材料的待交接记录使用 `rejected`。复核后的材料、判断和交接使用新记录和新 ID。

脚本检查结构、枚举、ID 唯一性、材料和未知项引用、Credential 链接与内容 Hash。脚本不检查论文内容是否真实。
