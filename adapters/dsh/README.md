# RW Research Skill → DeepSeek Harness 适配（v0.1）

把 RW Research Skill 的 21 个 Skill 接到 DeepSeek Harness（DSH）这个宿主上。
不复制知识库，不改 Skill 正文，不动 Claude Code 和 Codex 现有适配。

DSH 处于 Developer Preview。已知兼容缺口全部列在 `COMPATIBILITY.md`，
Hook 和事件的缺口在 `EVENT_MAP.md`。用之前先看这两份。

## 装什么

```bash
npm i -g @deepseek-ai/dsh@next
```

子包必须带 `@next`。它们的 `latest` dist-tag 是旧的，直接装会拿到对不上的版本。

## 怎么跑

```bash
adapters/dsh/scripts/rw-dsh-headless.sh "帮我把这个研究问题拆成检索式"
adapters/dsh/scripts/rw-dsh-web.sh
```

两个脚本做同一件事：调 `scripts/rw_dsh_patch.py` 在运行时解析仓库根目录，
渲染出一份带绝对路径的临时补丁，用 `--patch` 挂给 DSH，退出时删掉。

仓库里只有模板 `cordis.patch.example.yml`，绝对路径不进 Git。

带上 MCP：

```bash
RW_DSH_WITH_MCP=stdio adapters/dsh/scripts/rw-dsh-headless.sh "任务"
```

只想看补丁长什么样：

```bash
python3 adapters/dsh/scripts/rw_dsh_patch.py --print
```

## 补丁做了什么

三行，都是往 DSH 的根条目列表里 `insert`，不改任何现有行：

1. `rw-research-skills` —— 一个独立命名的 `skill-filesystem` provider，
   `includeDefaultRoots: false` + `customSkillDirs` 指向仓库的 `skills/`。
   这是 Skill 唯一来源，不建副本。
2. `rw-research-fixture-skills` —— fixture 根，只给结构测试用，生产可以删。
3. `rw-research-recorder` —— 原生 Cordis 插件，把 RW 关心的阶段写成 JSONL。

web 和 headless 用同一份补丁。`dsh-web-app` bundle 把宿主自带的 `skill-filesystem` 行关掉了，
但宿主全局层注册的 provider 仍然会并进每个 agent 的 catalog，所以不用为 web 单独做 preset。

## 事件记录

recorder 默认写到系统临时目录，路径在脚本启动时打出来。改路径：

```bash
RW_DSH_RUN_LOG=/some/where/events.jsonl adapters/dsh/scripts/rw-dsh-headless.sh "任务"
```

一行一条，字段 `rw_stage` 是 RW 阶段名：`session_start`、`task_entry`、`skill_selected`、
`tool_pre`、`tool_post`、`stage_gate_open`、`stage_gate_closed`、`stop`。

## 模型和凭据

DSH 有两条计费路，别混：

- **Codex OAuth** —— 走 ChatGPT Pro 订阅。
- **OpenAI API key** —— 走 API 计费，跟订阅无关。

凭据走 DSH 自己的凭据层或环境变量，不进仓库，也不进生成的补丁。
补丁模板里所有敏感位置写的都是 `!!js process.env.XXX`。

## 测试

```bash
RW_DSH_RUNTIME_DIR=/path/to/dsh-install python3 -m unittest discover -s adapters/dsh/tests
```

`RW_DSH_RUNTIME_DIR` 指向一个装了 `@deepseek-ai/dsh` 的 node 目录。
不设的话，需要 DSH 的用例会 skip，纯 Python 的用例照跑——skip 不是通过。

测试覆盖：

- 补丁渲染出真实仓库路径，渲染后没有占位符残留。
- 适配目录里没有本机绝对路径、用户名、疑似凭据。
- fixture Skill 在 `skills/` 之外，不会污染 `check_repository.py` 的 21 个目录检查。
- 3 个研究 fixture 声明的入口和下游 Skill 真实存在。
- DSH 发现 21 个 Skill，逐名与 `manifest.json` 相等（不是硬编码数字）。
- 4 个公开入口能加载完整正文，`resourceBase` 指向主来源。
- 改 fixture Skill 正文后下一次加载读到新内容。
- MCP stdio 和 streamable-http 两条都能发现工具、调用、拿到结果，工具名保持 `mcp__<server>__<raw>`。
- 事件投影覆盖提交前、工具前、工具后、阶段门和停止点。

## 目录

```text
adapters/dsh/
├── README.md                     这份
├── COMPATIBILITY.md              基线、兼容矩阵、缺口、没验证的部分
├── EVENT_MAP.md                  RW 阶段 ↔ DSH 事件 ↔ Hook 桥
├── cordis.patch.example.yml      补丁模板，带占位符
├── config/
│   ├── mcp.stdio.example.yml
│   └── mcp.streamable-http.example.yml
├── plugins/
│   └── rw-research-recorder.mjs  原生 Cordis 事件记录插件
├── scripts/
│   ├── rw_dsh_patch.py           运行时渲染补丁
│   ├── rw-dsh-headless.sh
│   └── rw-dsh-web.sh
├── fixtures/
│   ├── skills/rw-dsh-fixture-echo/   热改测试用，不属于 21 个 Skill
│   ├── mcp/rw_fixture_mcp_server.mjs 零依赖 fixture MCP server
│   └── tasks/                        3 个研究任务 fixture
└── tests/
    ├── probe_dsh.mjs             DSH 结构探针
    └── test_dsh_adapter.py       验收断言
```

## 现在还不能说的话

- 没跑过真实模型。本次只有结构验证，状态是 `local_check_passed`，不是 `live_model_smoke_passed`。
- 没在 DSH `0.1.0-rc.5` 上复测过，只在 `0.1.0-rc.6` 上跑通。
- 没验证 RW 的 Python 脚本在 DSH 的文件系统、Shell 和权限策略下能不能跑。
