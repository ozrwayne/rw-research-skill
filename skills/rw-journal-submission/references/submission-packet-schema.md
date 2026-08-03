# Submission Packet JSON 结构

顶层字段：

- `schema_version`：固定为 `rw-journal-submission/submission-packet/v1`。
- `submission_id`：单次投稿的稳定 ID。
- `created_at`、`updated_at`：UTC ISO 8601 时间。
- `manuscript`：题目、文章类型和版本。
- `target`：期刊、平台和要求核验时间。
- `materials`：投稿文件与版本状态。
- `authors`：作者资料。邮箱、通讯作者和 CRediT 必须分别带状态。
- `declarations`：基金、利益冲突、伦理、数据、AI 使用等声明。
- `reviewers`：审稿人候选、来源、冲突检查和状态。
- `portal`：当前系统、草稿、步骤、页面错误、检查时间和最终递交状态。
- `gaps`：待补项目。
- `audit_log`：只追加的处理记录。

资料字段状态只能是 `confirmed`、`missing`、`needs_author_confirmation` 或 `not_applicable`。

门户步骤状态只能是 `complete`、`incomplete` 或 `unverified`。

`portal` 记录当前页面状态，不等于已投稿。最终递交状态必须带证据来源，不能由页面步骤状态推断。

`portal.final_submission` 与 `portal.steps` 分开：

- `state`：`not_submitted`、`awaiting_human_submit`、`submitted` 或 `unverified`。
- `evidence`：未提交时为 `null`；已提交时记录 `user_confirmation` 或 `platform_receipt`、记录时间、可选稿件编号和回执引用。
- `agent_observation`：`user_confirmation` 时为 `not_observed`；Agent 读到平台回执时为 `observed`。

最终 `Submit` 由人类完成。Agent 只能在用户告知结果或读到平台回执后写回 `final_submission`。
