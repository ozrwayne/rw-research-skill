---
name: rw-research-passport
metadata:
  internal: true
description: |
  为单个研究项目建立和维护可审计的 JSON 状态文件，记录研究阶段、材料、判断、未知项、交接和变更日志。Use when the user asks for“建立研究档案”“保存这个研究项目的材料状态”“把文献、判断和下一步交给另一个科研 Skill”“检查研究状态文件”,or requests the rw-research-passport workflow.
---

# RW Research Passport

为一个研究项目保存当前状态。Passport 是交接文件，不是文献库，也不替代原始材料。

## 启动

1. 读取 `references/method.md` 和 `references/schema.md`。
2. 创建新文件时复制 `assets/passport-template.json`，或运行 `scripts/passport.py init`。
3. 检查现有文件时运行 `scripts/passport.py validate`，再读取原始材料核对关键字段。
4. 需要判断边界时读取 `references/axioms.md` 和 `references/cases.md`。
5. 交付前读取 `references/acceptance.md`。

## 工作阶段

1. 保留用户原问题、项目范围和当前研究阶段。
2. 给每份材料稳定 ID，记录路径或标识符、状态和加入时间。
3. 分开记录判断、未知项和被否定方向，不把推断写成事实。
4. 交给下一个 Skill 时，只传所需材料 ID，并记录交接状态。
5. 每次修改追加审计记录，不覆盖变化原因。
6. 运行验证，输出当前状态、缺口、下一步和停止条件。

## 命令

```bash
python3 scripts/passport.py init project-passport.json --project-id PROJECT-ID --title "Project title"
python3 scripts/passport.py add-material project-passport.json --id MAT-001 --type paper --title "Paper title" --source-pointer "doi:..." --status verified
python3 scripts/passport.py add-material project-passport.json --id MAT-002 --type paper --title "Updated paper" --source-pointer "path-or-id" --content-sha256 SHA256 --supersedes-id MAT-001
python3 scripts/passport.py validate project-passport.json
python3 scripts/passport.py summary project-passport.json
```

脚本只处理 JSON。原始材料可以是本地路径、DOI、PMID、URL 或其他稳定标识。

## 运行规则

- 一个 Passport 只对应一个研究项目。
- Passport 保存指针和状态，不复制论文全文。
- `verified` 只表示完成指定核验，不自动表示研究质量高。
- 判断必须连接材料 ID，或明确写成当前推断。
- 未知项不能因为流程推进而自动关闭。
- 交接只传当前阶段需要的材料，避免把整个工作区当作上下文。
- 原始材料 hash 变化后，旧材料和依赖判断不能继续作为已确认输入；按 `references/method.md` 的版本变化流程处理。
- 不把 Passport 当作跨项目个人记忆。

## 输出

- 可验证的 Passport JSON。
- 当前阶段、材料状态、已确认判断、未知项和下一步。
- 验证错误和不能继续的原因。

## 可选 ADHD 友好输出

- 仅当用户明确要求“ADHD 友好输出”“ADHD 友好模式”或同义方式时启用。
- 不主动询问、介绍或推荐这个模式，不根据表达方式、回复速度或任务完成情况推断。
- 用户只披露有 ADHD，但没有要求改变输出方式时，不启用。
- 默认只在当前任务中保持；用户要求关闭时立即返回普通输出。
- 不保存诊断信息。用户明确要求跨任务保留时，只保存 `interaction_mode: adhd_friendly`。
- 启用后先给“只看这里”：当前任务、用户现在只做的 1 件事和本轮完成标准。
- 多步骤任务再给进度：已完成、当前和待处理；简单回答不生成空栏目。
- 重要但不需要现在处理的内容进入“暂存区”；详细证据放在摘要之后。
- 每轮最多提出 1 个关键问题；必须输入先展示最多 3 项，其余放到后续。
- 加粗当前任务、用户动作、结论和阻断状态；每段不超过 2 处，不加粗整段，不重复加粗同一词。
- 不为缩短输出删除证据边界、未知事项、停止条件或安全提示。
- 用户要求“展开”时提供完整记录，同时保留顶部摘要。
- 中断后先给恢复点，说明上次完成位置、当前状态和下一步，不要求用户重复已提供的信息。

## 停止条件

- 找不到原始材料时，不把对应材料标为 `verified`。
- 项目 ID、材料 ID 或交接 ID 重复时，停止写入。
- 关键判断没有材料或推断标签时，停止交接。

## 接续

- 文献提取：`rw-paper-extractor`。
- 证据组织：`rw-evidence-map`。
- 论文写作：`rw-academic-writing`。
- 主张核验：`rw-claim-audit`。
