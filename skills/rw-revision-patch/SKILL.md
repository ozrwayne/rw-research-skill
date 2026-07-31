---
name: rw-revision-patch
metadata:
  internal: true
description: |
  将 Markdown 文稿切成带稳定 ID 和 hash 的段落块，只对用户批准的块执行替换，并输出保留比例、修改理由和问题追踪报告。Use when the user asks for“只改这几段”“按审稿意见局部修改”“保留其他内容不动”“生成可复核修改 patch”,or requests the rw-revision-patch workflow.
---

# RW Revision Patch

限制修改范围。第一版只替换已有 Markdown 块，不静默增加、删除或重排章节。

## 启动

1. 读取 `references/method.md` 和 `references/patch-format.md`。
2. 保留原始文稿，运行 `scripts/revision_patch.py anchor` 生成带块 ID 的副本和 manifest。
3. 根据已批准的修改范围建立 Patch JSON。
4. 运行 `check`，确认 hash、块 ID、修改比例和问题 ID。
5. 运行 `apply` 生成新文稿和报告。
6. 对修改块复核内容，对未修改块核对 preserved ratio。

## 命令

```bash
python3 scripts/revision_patch.py anchor draft.md --output draft.anchored.md --manifest draft.manifest.json
python3 scripts/revision_patch.py check draft.anchored.md --manifest draft.manifest.json --patch revision.patch.json
python3 scripts/revision_patch.py apply draft.anchored.md --manifest draft.manifest.json --patch revision.patch.json --output draft.revised.md --report revision.report.json
```

修改块超过全文 60% 时停止。只有用户明确同意大范围修改后才能加入 `--allow-large-patch`。

## 工作阶段

1. 固定基础文稿和版本 hash。
2. 把标题、段落、列表或代码块按空行边界编号。
3. 先确定每条批注对应的完整论证单位。批注框选的词句只是问题位置，不自动等于修改边界；必要时把同段前后句纳入同一 replace。
4. 将每项修改连接到块 ID、旧 hash、理由和 issue ID。需要跨块、增删或重排时，先说明范围并转入相应流程。
5. 先验证所有操作；任意一项失败时不生成部分结果。
6. 生成新文件，不覆盖原文件。
7. 输出修改块、保留块、保留比例和新 hash。

## 运行规则

- 原文件不被修改。
- Patch 第一版只支持 `replace`。
- 一个块在一次 Patch 中只能修改一次。
- `expected_hash` 必须与 manifest 一致。
- `new_text` 不能包含 RW block marker。
- 任意 precondition 失败时整批停止。
- 未涉及块的正文保持原样。
- 局部批注限制未经批准的改动范围，不要求修改只停留在高亮词句。内容正确性需要在完整论证单位上复核。
- “Expand”“Tell me more”“I don't understand”不能只通过增加字数、例子或同义词关闭。先检查主体、对象、行动、发生环节、作用关系、适用边界和当前意义是否仍需读者猜测。
- 新增、删除、重排章节进入结构修改，不伪装成局部替换。
- Patch 只能限制改动范围，不能证明修改内容正确。

## 输出

- Anchored Markdown 副本。
- Block manifest JSON。
- Patch JSON。
- Revised Markdown 新文件。
- Apply report JSON，包含 preserved ratio 和修改追踪。
- 每条批注的论证单位、修改边界理由和仍未闭合的问题。

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

- 输入文稿没有稳定版本时，不生成 Patch。
- hash、块 ID 或基础文稿不匹配时停止。
- 修改比例超过 60% 且用户没有明确批准时停止。
- 需要新增、删除或重排章节时，改走结构修订流程。
- 解决批注必须跨越用户尚未批准的块时，先报告所需范围，不静默扩大 Patch。

## 接续

- 学术写作：`rw-academic-writing`。
- 作者语气：`rw-phd-tone`。
- 审稿回复：`rw-journal-submission`。
- 主张复核：`rw-claim-audit`。
