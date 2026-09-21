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

## 可执行完整性边界

- JSON 加载拒绝重复键及 NaN、Infinity、1e999 等非有限数字；写入同样拒绝非有限数字。校验非空标识符、UTC 时间、枚举和引用类型；异常 JSON 类型返回错误，不作为有效记录。
- 当前 Decision 的内容、依据和材料列表须与所连 Credential 快照一致，并保持双向链接。Decision 被废止时只允许当前 `status` 与历史快照不同，旧凭据不改写。
- `settled_by` 的前缀后必须有非空 ID，禁止重复 ID。`agent_consensus` 至少需要 2 个不同 Agent ID；这不证明两个 Agent 独立，也不等于人类确认。
- 材料及 Credential 的替代链禁止自引用和循环。新增替代记录时，脚本废止旧记录及其当前依赖，并追加原因。
- `confirmed` 判断和 `prepared` 交接不得引用 `rejected` 或 `superseded` 材料。已接受的历史交接保留原状态，不代表旧材料仍可重新使用。
- CLI 写入使用同目录 `.lock` 文件串行化，并通过原子替换保存；不要删除正在使用的锁文件。此锁只协调使用该 CLI 的写入，手工编辑及直接 Python API 调用由调用者协调。
- JSON 状态路径和锁路径不得为符号链接。`--force` 仍是显式覆盖，不代替备份。
- 兼容读取旧版缺少 `credentials` 的 Passport，但结构验证通过不表示旧版决定取得了确认凭据。将旧版决定交给确认门前，先补充可核对的凭据。
- 脚本不自动读取原始材料、不验证人类是否实际确认、不验证权限委托，也不提供防篡改签名。

### 历史材料导入和唯一后继

`add-material --supersedes-id` 接受两种输入：

1. 旧节点尚未废止：脚本在同次写入中废止旧材料、失效当前依赖，并登记新版本。
2. 旧节点已经是 `superseded`，且尚无后继：允许补录它的唯一后继，审计动作使用 `material_history_linked`，不伪称本轮改变了旧状态。

两种情况都要求旧节点存在且没有其他后继。材料替代链不分叉；新版本继续变化时引用当前链尾，而不是再次引用早先的旧节点。失败不改动原文件。历史导入仍须通过当前依赖一致性检查，已有 confirmed 判断或 prepared 交接引用废止材料时须先按原始记录纠正。
