# Submission Packet JSON 结构

顶层字段：

- `schema_version`：新资料包使用 `rw-journal-submission/submission-packet/v2`；脚本继续读取 v1。
- `submission_id`：单次投稿的稳定 ID。
- `created_at`、`updated_at`：UTC ISO 8601 时间。
- `manuscript`：题目、文章类型和版本。
- `target`：期刊、平台和要求核验时间。
- `materials`：投稿文件与版本状态。
- `display_policy`、`display_items`：图表是否单独提交、编号规则、主文嵌入限制、正文引用、对应文件和上传顺序。
- `authors`：作者资料。邮箱、通讯作者和 CRediT 必须分别带状态。
- `declarations`：基金、利益冲突、伦理、数据、AI 使用等声明。
- `reviewers`：审稿人候选、来源、冲突检查和状态。
- `portal`：当前系统、草稿、步骤、页面错误、校样、退回事件、检查时间和最终递交状态。
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

## v2 展示项与校样

`display_policy` 字段：

- `separate_files_required`：期刊要求图表单独上传时为 `true`。
- `numbering_policy`：`separate_sequences` 表示图和表分别从 1 编号；`global_sequence` 表示共用序号。该值来自当前指南或作者确认。
- `main_manuscript_embeds`：图表必须分开提交时为 `forbidden`。
- `main_material_id`：主文稿在 `materials` 中的 ID。

每个 `display_items` 记录 `kind`、`number`、`body_reference`、`material_id`、`upload_order` 和 `status`。`preflight-display-items` 只支持 DOCX 主文；它检查 Word 表格、绘图、媒体和 Figure／Table 引用，并输出文件 hash。预检不判断图表内容、数据或视觉排版。

`portal.proof` 分开记录文字检查和视觉检查。浏览器无法读取原生 PDF 时使用 `needs_human_visual_check`。只有用户确认已查看时才记录 `human_confirmed`。

`portal.return_events` 保留退回理由、退回时间、修复动作和保存证据。修复同一草稿时保留原 `submission_id` 和 `draft_id`。
