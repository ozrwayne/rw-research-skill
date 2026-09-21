<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-2ea44f.svg"></a>
  <a href="VERSION"><img alt="Version: v0.9.2" src="https://img.shields.io/badge/version-v0.9.2-blue.svg"></a>
  <a href="#直接调用的-skill"><img alt="21 research Skills" src="https://img.shields.io/badge/research%20Skills-21-6f42c1.svg"></a>
  <a href="#安装"><img alt="Works with Agent Skills" src="https://img.shields.io/badge/works%20with-Agent%20Skills-0969da.svg"></a>
  <a href="evals/cross-model/results/2026-07-20-cross-model-v2/summary.md"><img alt="Cross-model record: 4 models" src="https://img.shields.io/badge/cross--model%20record-4%20models-2ea44f.svg"></a>
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg"></a>
</p>

<h1 align="center">🔬 RW Research Skill</h1>

<p align="center"><strong>把研究任务拆成可以核验、可以交接、可以继续推进的一步。</strong></p>

<p align="center">研究问题 → 文献 → 证据 → 设计 → 写作 → 核验 → 投稿</p>

<p align="center">
  <a href="#新手从这里开始">快速开始</a> ·
  <a href="#安装">安装</a> ·
  <a href="#常见场景与当前入口">常见场景</a> ·
  <a href="#直接调用的-skill">全部 Skill</a> ·
  <a href="#知识与验收">验证记录</a> ·
  <a href="CONTRIBUTING.md">贡献</a>
</p>

---

RW Research Skill 由 Roland Wayne 创建。当前版本：`v0.9.2`。当前包含 21 个科研 Skill、555 条知识原子、187 条公理、149 个案例和反例，以及 162 条行为合同。

适用于手上有研究想法、论文、数据、研究方案、章节草稿或审稿意见，需要判断下一步的人。你可以直接提交材料，也可以只说现在卡在哪里。系统会选择一个主 Skill，每次处理当前一步。

本地 v0.9.2 仅更新 `rw-peer-review` 审计修复及版本入口；其余历史模块不代表本次已同步版本。未提交、推送或发布。验证边界见 `docs/validation.md`。

## 你可以用它做什么

| 你交付的内容 | RW Research Skill 会处理什么 |
| --- | --- |
| 一个长期保存推文、视频文稿、笔记和研究材料的文件夹 | 扫描现有积累，区分已使用、已表达、有接触和未找到证据，再选择学习起点 |
| 一个还没定下来的研究兴趣 | 界定对象、构念、边界和可证伪条件，形成研究问题 |
| 一组需要查找或整理的文献 | 设计检索、核验来源、提取字段，并组织证据关系 |
| 文献中的冲突、空白或异常 | 区分缺证据和真冲突，生成并筛选候选创新点 |
| 一个研究方案或方法选择 | 检查设计、样本、测量、分析和替代解释 |
| 一组数据、代码、协议或材料链接 | 核对版本、标识符、访问路径、限制和数据声明 |
| 一篇带统计结果的文稿 | 核对分析单位、重复层级、方法和报告数字 |
| 一篇论文或章节草稿 | 根据已有材料组织论证，检查语气、来源支持和修改范围 |
| 一组审稿意见 | 拆分修改任务，只改批准的内容，并保留核验记录 |
| 一个持续推进的研究项目 | 保存材料、判断、未知项、阶段、交接和变更记录 |
| 一个需要选择工具的科研任务 | 根据任务、数据和环境选择工具，不把工具当成研究判断 |

## 新手从这里开始

安装后，在 Codex 中输入：

```text
$rw-research-router 新手入门
```

在其他支持 Agent Skills 的 Agent 中，直接说：

```text
请用 rw-research-router 带我新手入门。
```

新手入口不会先展示全部 Skill。有可读项目或指定文件夹时，它会先进入 `rw-research-learning`，扫描你已经写过、解释过和应用过的内容，再选择学习起点和后续主 Skill。

你也可以直接指定资料夹：

```text
$rw-research-learning 扫描这个文件夹，然后带我学系统综述：<folder>
```

你也可以直接提交任务：

```text
我只有一个研究想法，还没有形成研究问题：……
我有一批文献，需要判断应该先提取什么：……
这些研究的结果互相冲突，我想找能继续验证的方向：……
这是我的研究设计，请在执行前找出漏洞：……
这段论文引用了 3 篇文献，帮我检查来源是否支持这些说法：……
这是审稿意见和原稿，只修改指定段落：……
```

完成当前一步后，再次使用 `rw-research-router`。它会根据刚得到的结果选择下一步，不预先排出一条固定流程。

## 安装

### 按需安装

先查看仓库中可以安装的 Skill：

```bash
npx -y skills add rolandwonglonam/rw-research-skill --list
```

只安装研究入口：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --skill rw-research-router
```

安装一个当前需要的 Skill：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --skill rw-claim-audit
```

`npx -y` 会下载并执行 `skills` CLI，`-g` 会写入全局 Skill 目录。先确认仓库地址、目标目录和安装范围。

### 安装全部 Skill

需要整套科研路由时，可以安装全部 21 个 Skill：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --all
```

如果已经有科研路由、审计或写作系统，先按需安装，避免增加重复入口。

安装后没有立即出现新入口时，新建一次对话再使用。

### 更新

已经通过 `skills` CLI 安装时，可以让 Agent 执行：

```bash
npx -y skills update
```

更新前可以检查已安装 Skill 是否有新版本：

```bash
npx -y skills check
```

## 常见场景与当前入口

RW Research Skill 每次选择一个主流程。下面使用 `$skill-name` 表示 Codex 入口；在其他 Agent 中可以直接说“使用 skill-name”。

### 不知道从哪里开始

```text
$rw-research-router 新手入门
```

有可读材料时，入口先调用 `rw-research-learning`。它先发现内容范围，再建立本地索引，从原文中判断你已使用、已表达、有接触和暂时无证据的内容，然后给出第一份学习产物。

```text
$rw-research-learning 因果推断
$rw-research-learning 扫描 <folder>，根据我现有的内容带我学习。
```

### 从研究兴趣形成问题

```text
$rw-research-question 我想研究……，帮我把它变成可检索、可证伪的问题。
```

先确认对象、构念、边界和可能推翻结论的证据，再决定是否进入文献发现或研究设计。

### 查找并整理文献

```text
$rw-literature-discovery 为这个判断寻找并核验文献：……
$rw-paper-extractor 从这些论文中提取研究设计、样本、测量和结果。
$rw-evidence-map 把这些研究的支持、冲突、偏倚和缺口连起来。
```

文献存在、字段提取和证据关系分开处理。找到论文不等于论文支持当前主张。

### 从证据空白形成研究方向

```text
$rw-research-novelty 根据这组证据冲突，生成可以继续验证的候选创新点。
```

候选方向需要标出证据来源、贡献、可行性和证伪条件。没有完成检索时，不使用“首次”或“从未研究”等表述。

### 设计研究或投稿前找漏洞

```text
$rw-research-design 把这个研究问题转成设计、样本、测量和分析计划。
$rw-research-referee 在执行前检查偏倚、替代解释和结论边界。
```

研究设计负责形成方案；研究审查负责攻击方案。两者不在同一步混用。

### 检查研究材料和统计报告

```text
$rw-research-data 检查这篇论文的数据、代码和补充材料能否取得，并整理数据声明。
$rw-statistics-audit 核对这篇文稿的分析单位、重复层级、统计方法和报告数字。
```

研究材料审查处理对象、版本、访问路径和限制。统计审查处理报告是否对得上；没有原始数据和代码时，不声称已经重新分析。

### 写作、核验和局部修改

```text
$rw-phd-write 判断当前部分的写作功能，连接证据、解释和研究问题，不补造来源。
$rw-phd-tone 保留我的学术语气，只改影响理解的部分。
$rw-citation-audit 核对文内引用、参考文献、作者、年份和 DOI。
$rw-claim-audit 检查每个事实主张是否被指定来源原文支持。
$rw-revision-patch 只修改我批准的 Markdown 段落，其他内容保持不动。
```

写作、语气、来源核验和局部修改各自保留边界。需要改稿时，先确认问题属于哪一层。

### 准备投稿

```text
$rw-journal-submission 核验目标期刊要求，并整理投稿文件和审稿回复。
```

期刊要求、费用、政策和投稿入口可能变化。执行时回到期刊官方页面核验日期和版本。

### 评审一份稿件

```text
$rw-peer-review 按期刊配置评审 Agent，逐条记录意见、证据和处置。
```

评审台账与作者本人的研究档案分开保存。意见状态不是 `open` 时必须写下场，撤回意见必须连接说服它的来源。

全文、页面、章节、图表、脚注和补充材料形成多少张 Evidence Credential，由材料和提取粒度决定。Store 不设置凭据总数量上限。脚本在本地管理来源、依赖、状态和 hash，并为每条 Finding 生成 Paper Context Pack。模型只读取当前判断所需的必要依赖闭包，不一次载入全部凭据。

### 管理项目状态或选择科研工具

```text
$rw-research-passport 为这个研究项目建立可以交接的状态档案。
$rw-research-lab-router 根据任务、数据和当前环境选择工具。
```

项目状态保存研究材料和判断；工具路由只负责执行环境，不代替研究设计。

## 直接调用的 Skill

| 目标 | Skill |
| --- | --- |
| 判断当前研究阶段和下一步 | `rw-research-router` |
| 扫描本地研究积累，判断基础并选择学习起点 | `rw-research-learning` |
| 把研究兴趣变成问题 | `rw-research-question` |
| 发现并核验文献 | `rw-literature-discovery` |
| 从论文和补充材料提取字段 | `rw-paper-extractor` |
| 整理证据关系、冲突、偏倚和缺口 | `rw-evidence-map` |
| 生成并筛选候选创新点 | `rw-research-novelty` |
| 设计系统综述、范围综述和证据综合流程 | `rw-review-methods` |
| 建立研究设计、样本、测量和分析计划 | `rw-research-design` |
| 审查数据、代码和材料的访问与声明 | `rw-research-data` |
| 审查分析单位、重复层级和统计报告 | `rw-statistics-audit` |
| 在执行或投稿前检查研究漏洞 | `rw-research-referee` |
| 保存单个研究项目的状态和交接记录 | `rw-research-passport` |
| 核对文内引用、参考文献、作者、年份和 DOI | `rw-citation-audit` |
| 核验主张是否被指定来源支持 | `rw-claim-audit` |
| 对批准的 Markdown 块执行局部修改 | `rw-revision-patch` |
| 判断科研文本的写作功能，组织证据、解释和研究问题连接 | `rw-phd-write` |
| 提取并保持作者的学术语气 | `rw-phd-tone` |
| 核验期刊并准备投稿和审稿回复 | `rw-journal-submission` |
| 评审一份稿件并记录意见、辩论和处置 | `rw-peer-review` |
| 根据任务和环境选择科研工具 | `rw-research-lab-router` |

完整的前后关系见 [Skill 关系图](docs/skill-link-map.md)。

## 项目状态与接续

对话中的上下文不等于研究项目档案。需要跨对话、跨 Agent 或跨阶段继续时，使用 `rw-research-passport` 保存 JSON 状态。

状态文件记录：

- 当前研究阶段和原问题。
- 已有材料及其处理状态。
- 已确认事实、当前判断和未知事项。
- 已否定方向、停止条件和下一步。
- Skill 交接和变更记录。

主张核验使用 `rw-claim-audit` 保存来源位置、原文定位和 `PASS`、`REVIEW`、`BLOCK` 判断。局部改稿使用 `rw-revision-patch` 保存块 ID、hash、修改原因和未修改内容的保留比例。

## 知识与验收

公开包当前包含：

- 555 条结构化知识原子。
- 187 条运行公理。
- 149 个案例和反例。
- 162 条行为合同。
- 20 个独立运行静态自检脚本。

行为合同保存提示词、应做事项、不应做事项和下一步，用于后续模型评测。静态自检只检查文件、结构、数量和独立运行约束，不代表模型已经执行全部行为合同，也不证明真实任务提效。

2026-07-20 的 v0.7.1 跨模型配对验证使用 2 家提供方的 4 个模型入口和 8 个合成任务。带 Skill 条件通过 32／32，不带 Skill 条件通过 19／32，差值为 +40.625 个百分点。这个结果只适用于结果文件保存的任务、模型和版本。它不适用于 v0.8.0 的默认模型表，也不代表真实科研结果已经改善。评测协议和完整记录见 [`evals/cross-model/`](evals/cross-model/) 和 [结果摘要](evals/cross-model/results/2026-07-20-cross-model-v2/summary.md)。

v0.8.0 增加真实文档审阅入口。默认使用本机已登录的 Codex 和 Claude CLI，不要求 API key。当前模型表为 `gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna` 和 `claude-opus-4-8`。汇总不按模型数量投票：Codex 与 Claude 都锚定到同一段原文时，才进入 cross-provider findings；只有 Codex 模型重复发现的问题单列。真实文档和结果必须保存在公开仓库外。使用方式见 [跨模型评测说明](evals/cross-model/README.md)。

公开内容不包含个人论文、数据、评审记录、研究项目状态或个人来源标签。案例和行为合同使用合成或占位输入。规则见 [`docs/public-content-policy.md`](docs/public-content-policy.md)。

每个 Skill 自带适用方法、来源入口、停止条件、案例、反例、工作表和自检。需要当前文献、API、期刊政策或报告规范时，仍需核验官方来源。

发布检查结果见 [v0.9.1 验证记录](docs/validation.md)。

## v0.9.1 更新

- `rw-peer-review` 增加独立的 `judgment-learning/FIND-ID.json` 判断学习旁车，不改变 `review-ledger.json` 的 v1 结构。
- 增加面向零经验用户的 `guided`：合成基线题、不同案例的 worked example、当前 Finding 引导审稿卡和针对性反馈。
- 将正确审稿定义为意见可定位、证据连接可解释、推断边界受控、严重程度相称、修改建议可执行，不要求猜中编辑决定。
- 将本次任务的 `ready` 与能力评定的 `mastery` 分开。`mastery` 不自定训练时间或案例数，使用课程、期刊或导师预先声明的标准和评定结果。
- 使用 Review Quality Instrument 的 7 个核心维度检查评审报告，并加入 COPE 接单边界和 EQUATOR 报告完整性边界。
- 根据 2023 Cochrane Review、2004 BMJ 随机试验和 2016 系统综述，删除“快速掌握”和固定迁移次数的效果承诺。
- 在综合前增加问题图、用户初判、最强质疑、最强回应、材料核对和用户终判。
- 将“作者提到”“回应命中”“回应成立”“正文仍需补报”拆成 4 个字段。
- 增加正文、补充材料、作者解释、统计原则和研究对象／estimand 的核对状态。
- 增加 `init`、`validate`、`summary`、综合 Gate 和交付 Gate。
- 对外报告排除用户初判、改判过程、Agent 分歧、模型信息和迁移记录。
- 增加 29 条判断学习知识原子、14 条公理、11 个案例和反例、16 条行为合同，以及 13 个确定性单元测试。
- 保留原 Review Ledger Gate 和历史数据读取；Ledger PASS 不表示稿件质量或用户掌握。

## v0.9.0 更新

- `rw-paper-extractor` 增加带来源 hash 和配置 hash 的 PDF Paper Case。
- 增加章节识别依据、置信度和人工修正入口，减少参考文献条目被识别成章节的问题。
- 增加图表候选提取和跨页表格拼接；拼接图保留各页的 page、bbox 和 text unit 定位。
- 增加 5 阶段精读报告、阶段状态和 STALE 传播。
- 候选主张先进入 `rw-claim-audit`；只有门禁为 PASS 才能生成 LitNet 回写预览。
- LitNet 接口只生成预览，不写 Zotero，也不自动改正式卡片。

## v0.8.0 更新

- 新增 `rw-research-learning`。
- 支持指定文件夹、当前项目和可读用户内容 3 种扫描模式。
- 建立本地 SQLite 索引，支持文本、Markdown、HTML、JSON、CSV、Word、PowerPoint、Excel 和可选 PDF 提取。
- 用 `applied`、`articulated`、`exposed` 和 `no_evidence` 区分可见研究基础。
- 扫描跳过凭据、私钥、环境变量、密码库、依赖包和操作系统目录。
- 增量扫描只重新提取新增和修改文件。
- 内容扫描前先做元数据范围发现，区分发现范围和实际正文扫描范围。
- 区分用户产出、过程记录、协作材料、外部参考和下载工具。
- 区分当前文件、历史方案、参考材料和未知版本。
- 单个文件解析失败时标记为 `unreadable`，其他文件继续扫描。
- 研究画像、索引和能力报告默认为本地私有状态，公开测试只使用合成材料。
- `rw-research-router` 在用户不知道从哪里开始时，先路由到 `rw-research-learning`。

## v0.8.0 更新

- 默认模型表改为 Codex Sol、Terra、Luna 和 Claude Opus 4.8。
- Claude 通过本机 Claude CLI 和现有登录状态运行，不经过本项目配置 API key。
- 增加 `.md`、`.txt` 和 `.docx` 真实文档审阅入口。
- 汇总按 provider 分组，不把 3 个 Codex 模型当作对 Claude 的多数票。
- 真实文档、prompt 和结果不进入公开仓库。

## v0.7.1 更新

- 将行为条目标记为行为合同，不再把静态自检写成模型行为测试。
- 增加 `rw-citation-audit`，分开检查引用身份、格式和主张支持。
- 默认展示按需安装，整包全局安装改为可选路径。
- SkillHub 保留公开来源入口和原有来源标识。
- 增加仓库检查、确定性工具测试和 push／PR CI。

## v0.7.0 更新

- 修复了一些已知问题。
- 增加 SkillHub 公共版构建，合并参考资料并限制为最多 200 个文件。
- 清除公共版中的本地来源标签、个人研究材料和内部来源说明。
- 增加 `rw-research-data`，检查研究对象、版本、访问路径、限制和声明。
- 增加 `rw-statistics-audit`，检查分析单位、重复层级、统计方法和报告数字。
- 文献发现增加可取得层级、版本关系和失败来源记录。
- 审稿回复增加稳定意见编号、状态和修改位置。

## v0.6.0 更新

- 新增 `rw-research-passport`，保存研究项目的材料、判断、未知项、阶段和交接状态。
- 新增 `rw-claim-audit`，区分来源存在、引用格式和来源是否支持具体主张。
- 新增 `rw-revision-patch`，按稳定 Markdown 块和 hash 执行局部替换，并报告保留比例。
- 更新 `rw-research-router`，加入“新手入门”和 3 个新流程的路由。
- 更新 `rw-phd-write`，按写作功能判断解释义务，不按章节编号套用模式。
- 公开包增加到 16 个科研 Skill。

## 本地构建

公开仓库中的 Skill 是发布副本。维护者从工作区源码同步后运行：

```bash
python3 scripts/sync_from_workspace.py
python3 scripts/build_release.py
```

发布包生成在：

```text
dist/rw-research-skill-0.9.1.zip
```

构建过程检查版本一致性、Skill 结构和 20 个独立运行静态自检。

## License

本项目采用 [Apache License 2.0](LICENSE)。

公共仓库：[rolandwonglonam/rw-research-skill](https://github.com/rolandwonglonam/rw-research-skill)
