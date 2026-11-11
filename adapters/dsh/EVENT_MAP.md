# RW 研究阶段 ↔ DSH 事件映射

基线：`deepseek-ai/deepseek-harness@47f943859bef60e4160492346772ded9b24f765a`，
npm `@deepseek-ai/dsh@0.1.0-rc.6`。以源码为准，文档只作参考。

DSH 有两套东西，不要混：

- **Cordis 扩展点**：进程内事件，插件用 `ctx.on(...)` 挂。有 emit、waterfall、serial 三种语义。可以改流程。
- **Session 日志事件**：追加写进会话日志，可持久化、可回放。只记录，不改流程。

RW 要的是「可持久记录」，所以主线走 session 日志事件；要拦截才用 Cordis 扩展点。

## 一、RW 阶段 → DSH

| RW 阶段 | Cordis 扩展点 | Session 日志事件 | 是否可持久 | 说明 |
|---|---|---|---|---|
| 会话开始 | `session/created`、`agent/session-start` | 无专门事件 | 部分 | 会话本身落盘，但没有一条“会话开始”的日志事件。recorder 用 `session/created` 补一条。 |
| 用户提交研究任务 | `agent/pre-step`（waterfall，可拒绝） | `user/message` | 是 | 用 `source.kind` 区分人写的和注入的；`skill-invocation` 是 `/name` 手势注入的 Skill 正文。 |
| Skill 加载 | `skills/change`（只报目录变化） | 无专门事件 | 间接 | **没有 `skill/loaded` 这种事件。** 落盘的是 `tool/call`（`name === 'skill'`）和它的 `tool/result`，加上 `skill-catalog` / `skill-invocation` 两种消息 source。recorder 靠工具名把它从普通工具调用里分出来。 |
| 工具调用前 | `tools/pre-execute`（waterfall，可 deny / ask） | `tool/call` | 是 | `tool/call` 是模型请求的原样记录：`callId`、`name`、未解析的 `arguments` 字符串。 |
| 工具调用后 | `tools/post-execute`（waterfall，可 block）、`tools/result`（emit） | `tool/result` | 是 | 结果里带 `error?: {name, code}`；成功值 `value` 是执行局部的，**不进日志**。 |
| 阶段门等待人工确认 | `approval/request` | `approval/asked` + `approval/decided` | 是 | 一问一答成对。`approval/policy` 记录策略切换。 |
| 回合停止 | `agent/turn-stopping`（serial，可 steer 强制续跑） | `turn/end` | 是 | `reason.kind` ∈ `completed` / `aborted` / `blocked` / `error` / `max-tokens` / `interrupted`。 |

recorder（`plugins/rw-research-recorder.mjs`）挂 `session/event` 火管，把上面这些投影成 JSONL，
字段是 `rw_stage`。它是原生 Cordis 插件，不经过 Hook 桥、不起子进程。

## 二、Claude Code / Codex Hook 桥的位置

桥只是兼容入口。RW 现有的 Claude Code / Codex hook 如果只是记录或简单拦截，可以先挂桥跑起来；
要做 RW 自己的研究状态记录，用原生插件。

桥不在 `@deepseek-ai/dsh` 的默认安装树里，要单独装：

```bash
npm i @deepseek-ai/dsh-hooks-claude-code@next @deepseek-ai/dsh-hooks-codex@next
```

注意这两个包的 `latest` dist-tag 是旧的（`0.0.1-rc.5` / `0.0.1-rc.1`），必须用 `@next` 或写死版本，
否则装到的版本和 `@deepseek-ai/dsh@0.1.0-rc.6` 对不上。

### Claude Code 桥映射（7 个点）

| CC hook | DSH 点 | 能做什么 |
|---|---|---|
| `SessionStart` | `agent/session-start`（emit） | 只能注入 additionalContext，不能拦 |
| `UserPromptSubmit` | `agent/pre-step`（waterfall） | `deny` → 拒绝；只给 context 就往下传 |
| `PreToolUse` | `tools/pre-execute`（waterfall） | `deny` / `ask` |
| `PostToolUse` | `tools/post-execute`（waterfall） | `deny` → block + feedback |
| `Stop` | `agent/turn-stopping`（serial） | 阻塞式 Stop 会 steer 强制再跑一步 |
| `SubagentStart` | `subagent/start`（emit） | 只能给在进程内的子 agent 注入 |
| `SubagentStop` | `subagent/end`（emit） | 只看不拦 |

### Codex 桥映射（5 个点）

`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop`，落点与 CC 相同。
`PreToolUse` 只有 `block`，没有 `allow` / `ask`。

## 三、明确没映射的部分

这一节是「不以完全兼容描述部分桥接」的具体内容。以下都来自上游 README 的
Known Limitations，不是推测。

### Claude Code：30 个 hook 事件里 23 个不支持

`Setup`、`InstructionsLoaded`、`UserPromptExpansion`、`MessageDisplay`、`PermissionRequest`、
`PostToolUseFailure`、`PostToolBatch`、`PermissionDenied`、`Notification`、`TaskCreated`、
`TaskCompleted`、`StopFailure`、`TeammateIdle`、`ConfigChange`、`CwdChanged`、`FileChanged`、
`WorktreeCreate`、`WorktreeRemove`、`PreCompact`、`PostCompact`、`SessionEnd`、`Elicitation`、
`ElicitationResult`。这些事件的配置在解析前就被丢掉。

已支持的 7 个点也都是部分支持：

- `SessionStart`：只吃 JSON `additionalContext`。纯 stdout context、`initialUserMessage`、`sessionTitle`、`watchPaths`、`reloadSkills`、`CLAUDE_ENV_FILE` 都不支持。hook 是 detached 跑的，context 可能赶不上第一次请求。
- `UserPromptSubmit`：不支持纯 stdout context、`sessionTitle`、`suppressOriginalPrompt`。默认超时用 600 秒，不是 CC 的 30 秒。
- `PreToolUse`：`allow` 不预批准，`defer` 不支持，`additionalContext` 被忽略，`updatedInput` 只记日志不生效。
- `PostToolUse`：`updatedToolOutput`、`updatedMCPToolOutput` 不支持，`tool_response` 被拍平成文本。
- `Stop`：`stop_hook_active` 永远 `false`，没有连续阻塞上限。一个无条件阻塞的 hook 会让每一步都强制续跑。
- `SubagentStart` / `SubagentStop`：`agent_type` 永远是常量 `general-purpose`，用的是子会话 id 而不是父会话 id。

字段层面：`prompt_id`、`transcript_path`、`permission_mode`、`effort` 在部分事件缺失；
`systemMessage` 只记日志；`{"continue": false}` 记下来但不真的停；
`suppressOutput`、`stopReason`、`terminalSequence` 不生效。

handler 层面：只跑 shell 形式的 `type: 'command'`。`http`、`mcp_tool`、`prompt`、`agent` 直接跳过。
`args`、`async`、`asyncRewake`、`shell`、`if`、`once`、`statusMessage` 都不生效。
同一个点上的多个 hook 串行跑且不去重，CC 是并行加去重。
`configPath` 是进程级的，只在加载时解析一次，没有 CC 那套项目 / 用户 / 插件 / 策略分层发现和热重载。

### Codex：10 个 hook 事件里 5 个不支持

`PermissionRequest`、`PreCompact`、`PostCompact`、`SubagentStart`、`SubagentStop`。
这些配置在解析时被静默丢弃。

### RW 侧的结论

- 研究状态记录**不要**走桥。桥的字段缺失面太大，而且 `continue: false` 不真的停。用原生插件。
- 需要真的拦住工具（比如没批准就不许写文件）时，`tools/pre-execute` 的 `deny` 是可靠的，`allow` 不是。
- 阶段门用 `approval/*`，不要用 `Stop` hook 模拟——`Stop` 没有连续阻塞上限，容易变成死循环。
