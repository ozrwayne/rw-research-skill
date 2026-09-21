# RW Research Skill × DeepSeek Harness 兼容矩阵

以下是 `0.12.0`、21 个 Skill 的历史 DSH 验收快照。当前合并包为 `0.13.0`、22 个 Skill；新增 `rw-peer-review` 后的 DSH 状态以本次复测记录为准，不把旧结果自动算作新版本通过。

## 一、基线

| 项 | 值 |
|---|---|
| RW `origin/main` | `38c57fd4c766df61026c552e939a30f13f0644b1` |
| RW 版本（VERSION / manifest / plugin.json） | `0.12.0` |
| RW Skill 数量 | 21 |
| RW 公开入口 | 4（`rw-research-router`、`rw-paper-extractor`、`rw-research-referee`、`rw-phd-write`） |
| DSH 源码 commit | `47f943859bef60e4160492346772ded9b24f765a` |
| DSH 源码根包版本 | `0.1.0-rc.5` |
| 实际测试用的 DSH npm 版本 | `0.1.0-rc.6` |
| DSH 阶段 | Developer Preview |

工单里写的 RW 版本是 `0.11.0`，实际 `origin/main` 上是 `0.12.0`。以仓库为准。

### npm 与源码不一致

工单把「DSH npm 包与源码基线是否完全一致」列为未知项。结论是**不一致**：

- 源码 pin 在 `47f9438`，根包 `0.1.0-rc.5`。
- npm `@deepseek-ai/dsh` 的 `latest` 已经是 `0.1.0-rc.6`。
- 子包的 `latest` dist-tag 全是旧的。`@deepseek-ai/dsh-skill-filesystem` 的 `latest` 是 `0.0.1-rc.3`，`next` 才是 `0.1.0-rc.6`。装 `@deepseek-ai/dsh` 时依赖解析拿到的是 `0.1.0-rc.6`，但手动 `npm i @deepseek-ai/dsh-skill-filesystem` 会拿到 `0.0.1-rc.3`。

**装子包必须带 `@next` 或写死版本。** 这条同样适用于两个 Hook 桥包。

本次验收跑在 `0.1.0-rc.6` 上。**没有在 `0.1.0-rc.5` 上复测过**，也就是说工单合并门里
「至少完成 1 次 DSH 上游版本变化后的适配复测」只做了一半：适配是照 rc.5 源码写的，
在 rc.6 上跑通了；反向没验。这条风险保留。

## 二、Skill 解析

DSH `skill-filesystem` 的解析规则（源码 `packages/skill/skill-filesystem/src/index.ts`）：

- 目录 bundle `<root>/<name>/SKILL.md`，或扁平文件 `<root>/<name>.md`。只认一层，不递归。
- frontmatter 是开放 YAML 对象，用 `yaml` 包解析。
- 必需：`name`、`description`。
- 可选：`whenToUse`、`metadata`、`disable-model-invocation`、`user-invocable`。
- 名字必须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`。
- 驼峰写法的 `disableModelInvocation` / `modelInvocable` / `userInvocable` 会**整条 Skill 被丢掉**，不是忽略字段。
- `skill(name)` 每次加载都重新读盘重新解析，正文改动不需要缓存失效。

RW 现有结构 `skills/<name>/SKILL.md` + `name` / `description` / `metadata.internal` 正好落在这个规则里。

## 三、兼容矩阵

### 可直接加载（21 / 21）

21 个 Skill 全部被 DSH 发现并能加载完整正文。实测记录见
`tests/probe_dsh.mjs` 的输出，断言在 `tests/test_dsh_adapter.py::DshSkillDiscoveryTest`。

| 检查 | 结果 |
|---|---|
| 发现数量 | 21，与 `manifest.json` 的 skills 列表逐名相等 |
| 发现来源 | 全部 `custom`（只扫 `customSkillDirs`，没扫到项目根或用户目录） |
| 4 个公开入口正文加载 | 全部成功，字节数 2152—3674 |
| `resourceBase` | 指向 `skills/<name>/`，即主来源本身 |
| 名字合法性 | 21 个全部通过 kebab-case 校验 |
| description 长度 | 最长 356 字符，低于 catalog 默认上限 500，不会被截断 |
| 改主来源正文后重新加载 | 读到新正文，没有第二份副本 |

### 需要适配（配置层解决，不改 Skill 正文）

| 项 | 情况 | 处理 |
|---|---|---|
| provider 隔离 | 默认 provider 会扫项目根 `.dsh/skills`、`.agents/skills`、`$DSH_HOME/skills`、`~/.agents/skills` 和 bundled 根 | 用独立 `providerName` + `includeDefaultRoots: false`，只看 RW 的 `skills/` |
| web profile | `dsh-web-app` bundle 把宿主的 `skill-filesystem` 行关掉了（`disabled: true`），本机发现交给 agent preset | 本适配插的是宿主全局层的新 provider 行，它的 catalog 会并进每个 agent 的 scope，所以 web 和 headless 用同一份补丁，不用复制 preset |
| 绝对路径 | 补丁需要绝对路径，但绝对路径不能进仓库 | `scripts/rw_dsh_patch.py` 运行时用 `git rev-parse --show-toplevel` 解析根目录，渲染成临时补丁 |

### 当前不支持 / 已知缺口

| 缺口 | 影响 | 现在怎么办 |
|---|---|---|
| **`metadata.internal: true` 在 DSH 里不起作用** | RW 的 17 个内部 Skill 在 DSH 里全部对模型和用户可见（`modelInvocable: true`、`userInvocable: true`）。Claude Code 那边靠这个字段收起来，DSH 只把 `metadata` 当不透明数据 | 保持现状，不改 Skill 正文。要收起来得给 17 个 Skill 加 `disable-model-invocation: true`，那会动 `skills/` 和其他宿主的行为 —— 属于停止条件，需要单独提案 |
| DSH 只接 MCP Tools | Resources 和 Prompts 没有 harness 消费方 | 本次通过范围只算 Tools。RW 如果有依赖 Resources 的 MCP 服务，暂时接不进来 |
| Hook 桥缺口面很大 | CC 30 个事件支持 7 个，Codex 10 个支持 5 个；已支持的也都是部分 | 研究状态记录走原生 Cordis 插件，不走桥。明细见 `EVENT_MAP.md` |
| Skill 加载没有独立的持久事件 | 日志里看不到「加载了哪个 Skill」这一条 | recorder 靠 `tool/call` 里 `name === 'skill'` 反推，把 `arguments` 里的 Skill 名取出来 |
| 会话开始没有持久事件 | 会话本身落盘，但没有「会话开始」这一条日志 | recorder 挂 Cordis 的 `session/created` 补一条 |
| 发现只有一层 | `<root>/<name>/SKILL.md` 之外的嵌套结构不认 | RW 当前结构正好是一层，暂时没影响；以后如果分组就会踩到 |
| 坏条目静默消失 | frontmatter 解析失败只 warn 一句就跳过，模型看到的 catalog 里分不清「没有」和「坏了」 | 结构测试断言的是数量和逐名相等，坏一个就会失败 |
| 子包 `latest` dist-tag 是旧的 | 手动装子包会装到不匹配的版本 | 文档和脚本里一律用 `@next` |

### 没有验证的部分

| 项 | 状态 |
|---|---|
| RW 现有脚本在 DSH 的文件系统 / Shell / 权限策略下能否跑 | **没验证。** 本次只跑了 Skill 加载、MCP 和事件投影，没在 DSH 里执行过 RW 的 Python 脚本 |
| DSH Codex OAuth 在本机能否完成真实模型调用 | **没验证。** 本机没有配置 DSH 模型登录，没跑过真实模型 |
| 3 个研究 fixture 在 DSH 里的真实路由结果 | **没验证。** fixture 已经写好，声明的 Skill 名做了存在性断言，但没有真实模型跑过 |
| 在 DSH `0.1.0-rc.5` 上复测 | **没做。** 只在 `0.1.0-rc.6` 上跑过 |

## 四、计费路径

DSH 有两条互相独立的路：

- **Codex OAuth**：走 ChatGPT Pro 订阅，不额外按 token 计费。
- **OpenAI API key**：走 API 计费，跟订阅无关。

两条不能混着算。RW 侧约定 ChatGPT Pro 只从 Codex OAuth 走，API key 属于单独预算。
凭据都不进仓库，也不进生成的补丁——补丁里只写 `!!js process.env.XXX`。
