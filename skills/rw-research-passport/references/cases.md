# 案例和反例

> 公开案例使用合成或占位输入，不来自任何个人研究项目。

## 案例 1：把提取结果交给写作

- 将论文登记为 `MAT-001`。
- 提取完成后改为 `extracted`。
- 原文位置复核后改为 `verified`。
- 建立从 `extraction` 到 `writing` 的 handoff，只传需要的材料 ID。

## 案例 2：保留未解决问题

- 数据来源仍不确定时建立 `UNK-001`，状态为 `open`。
- 不因为进入写作阶段把它改为 `resolved`。

## 反例：把 Passport 当结论证明

- 错误：因为材料状态是 `verified`，便声称论文结论正确。
- 正确：回到研究设计、结果和原文位置核对。

## 案例 3：会议形成研究决定

- 把会议纪要登记为原始记录指针。
- 将每个已定事项写成一个 Decision。
- 记录 `settled_by`、`authority`、`basis`、`scope`、证据和开放未知项。
- 生成 Research Credential 后再交给下游 Skill。

## 案例 4：Agent 讨论形成共识

- `settled_by` 记录参加讨论的 Agent ID。
- `authority` 写为 `agent_consensus`。
- 下游需要人类确认时继续停止，不能把 Agent 共识改写为 `human_confirmed`。

## 反例：修改旧 Credential

- 错误：研究方向改变后直接改写旧 Credential 的决定内容。
- 正确：创建新 Credential，用 `supersedes` 指向旧 Credential。
