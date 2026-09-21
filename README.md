<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-2ea44f.svg"></a>
  <a href="VERSION"><img alt="Version: v0.13.0" src="https://img.shields.io/badge/version-v0.13.0-blue.svg"></a>
  <a href="#4-个对外入口"><img alt="4 public entries" src="https://img.shields.io/badge/public%20entries-4-6f42c1.svg"></a>
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
  <a href="#4-个对外入口">4 个入口</a> ·
  <a href="#知识与验收">验证记录</a> ·
  <a href="CONTRIBUTING.md">贡献</a>
</p>

---

RW Research Skill 由 Roland Wayne 创建。当前版本：`v0.13.0`。对外提供 4 个入口，内部保留 22 个科研 Skill。当前包含 594 条知识原子、197 条公理、171 个案例和反例，以及 199 条行为合同。

适用于手上有研究想法、论文、数据、研究方案、章节草稿或审稿意见，需要判断下一步的人。你可以直接提交材料，也可以只说现在卡在哪里。系统会选择一个主 Skill，每次处理当前一步。

## 你可以用它做什么

| 你交付的内容 | RW Research Skill 会处理什么 |
| --- | --- |
| 一个长期保存推文、视频文稿、笔记和研究材料的文件夹 | 扫描现有积累，区分已使用、已表达、有接触和未找到证据，再选择学习起点 |
| 一个还没定下来的研究兴趣 | 界定对象、构念、边界和可证伪条件，形成研究问题 |
| 一个中文、英文或混合语言的研究问题 | 拆分概念块，生成 MeSH、Emtree、CINAHL Headings、APA Thesaurus 候选和分平台检索式 |
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

只安装一个研究入口：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --skill rw-research-router
```

安装一个当前需要的 Skill：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --skill rw-claim-audit
```

`npx -y` 会下载并执行 `skills` CLI，`-g` 会写入全局 Skill 目录。先确认仓库地址、目标目录和安装范围。

### 安装 4 个对外入口

默认安装只包含 4 个对外入口：

```bash
npx -y skills add rolandwonglonam/rw-research-skill -g --all
```

其余 17 个 Skill 标记为内部模块，不出现在默认安装清单中。需要兼容旧调用或检查内部模块时，显式开启内部安装：

```bash
INSTALL_INTERNAL_SKILLS=1 npx -y skills add rolandwonglonam/rw-research-skill -g --all
```

内部安装会增加入口数量。普通用户不需要使用这个模式。

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

RW Research Skill 每次选择一个主流程。用户只需要选择下面 4 个入口。入口再调用内部模块。

```text
$rw-research-router 我不知道从哪里开始，请判断当前一步。
$rw-paper-extractor 精读这些论文，提取图表和证据，并核验关键主张。
$rw-research-referee 检查这个研究的综述方法、设计、材料、统计和结论边界。
$rw-phd-write 根据现有证据处理这份论文写作、修改或投稿任务。
```

## 4 个对外入口

| 入口 | 处理范围 |
| --- | --- |
| `rw-research-router` | 学习起点、研究问题、文献发现、检索策略、创新方向、项目状态、投稿和工具接续 |
| `rw-paper-extractor` | PDF 工作区、章节和图表提取、分阶段精读、证据关系、引用和主张核验 |
| `rw-research-referee` | 综述方法、研究设计、研究材料、统计报告和结论审查 |
| `rw-phd-write` | 科研写作、作者语气、局部修订、审稿回复和投稿材料 |

22 个内部 Skill 仍可按原名称直接调用，用于兼容已有流程。对外入口和内部归属由 [`manifest.json`](manifest.json) 统一维护。完整前后关系见 [Skill 关系图](docs/skill-link-map.md)。

依赖不可用、材料不足或上游产物变化时，处理规则见 [degradation registry](docs/degradation-registry.json)。它记录状态、替代动作、禁止行为、用户提示、责任 Skill 和对应测试。4 个入口的合成场景见 [degradation scenarios](docs/degradation-scenarios.json)。

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

- 544 条结构化知识原子。
- 170 条运行公理。
- 152 个案例和反例。
- 165 条行为合同。
- 21 个独立运行静态自检脚本。

行为合同保存提示词、应做事项、不应做事项和下一步，用于后续模型评测。静态自检只检查文件、结构、数量和独立运行约束，不代表模型已经执行全部行为合同，也不证明真实任务提效。

2026-07-20 的 v0.7.1 跨模型配对验证使用 2 家提供方的 4 个模型入口和 8 个合成任务。带 Skill 条件通过 32／32，不带 Skill 条件通过 19／32，差值为 +40.625 个百分点。这个结果只适用于结果文件保存的任务、模型和版本。它不适用于 v0.8.0 的默认模型表，也不代表真实科研结果已经改善。评测协议和完整记录见 [`evals/cross-model/`](evals/cross-model/) 和 [结果摘要](evals/cross-model/results/2026-07-20-cross-model-v2/summary.md)。

v0.8.0 增加真实文档审阅入口。默认使用本机已登录的 Codex 和 Claude CLI，不要求 API key。当前模型表为 `gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna` 和 `claude-opus-4-8`。汇总不按模型数量投票：Codex 与 Claude 都锚定到同一段原文时，才进入 cross-provider findings；只有 Codex 模型重复发现的问题单列。真实文档和结果必须保存在公开仓库外。使用方式见 [跨模型评测说明](evals/cross-model/README.md)。

公开内容不包含个人论文、数据、评审记录、研究项目状态或个人来源标签。案例和行为合同使用合成或占位输入。规则见 [`docs/public-content-policy.md`](docs/public-content-policy.md)。

每个 Skill 自带适用方法、来源入口、停止条件、案例、反例和工作表；自检由模块脚本或确定性测试承担。需要当前文献、API、期刊政策或报告规范时，仍需核验官方来源。

当前合并检查见 [v0.13.0 验证记录](docs/validation.md)。

## v0.13.0 合并

- 将本地审计的证据、状态、检索、文件保护和打包修复合入主包。
- 新增独立 `rw-peer-review` v0.9.2 模块；外来稿件评审归 `rw-research-referee` 入口，作者本人研究审查仍由后者处理。
- 该版本仅指仓库内容；合成行为合同数量不等于模型实测次数。

## v0.12.0 更新

- 新增 `rw-journal-submission` 的 Submission Packet、ScholarOne 交接合同和字段整理工具。
- `rw-research-router` 在稿件完成、已有目标期刊或需要选刊时交接到 `rw-journal-submission`。
- Agent 可以整理材料、核对缺口和协助填写；最终 `Submit` 由人类完成。
- 公开边界检查、Router／投稿包测试和完整发布 CI 通过。

## v0.11.0 更新

- 将 21 个科研 Skill 收到 `rw-research-router`、`rw-paper-extractor`、`rw-research-referee` 和 `rw-phd-write` 4 个对外入口下。
- 17 个内部 Skill 使用 `metadata.internal: true`，默认发现和安装后的普通列表只显示 4 个入口。内部模式仍可发现和调用全部 21 个 Skill。
- `manifest.json` 记录每个内部 Skill 的唯一入口归属。
- `ci/manifest.json` 统一本地、Pull Request、main 分支和 GitHub Release 的检查。
- `docs/degradation-registry.json` 记录降级状态、替代动作、禁止行为和责任 Skill。
- 为每个入口增加 2 个确定性降级场景，并用真实 Agent 各运行 1 个前向场景。
- 前向测试只说明这 4 个合成提示中的行为，不表示所有模型和任务都会照做。

## v0.10.0 更新

- 新增 `rw-search-strategy`。
- 支持中文、英文和混合语言研究问题，保留原问题并建立英文规范概念。
- 分开处理 MeSH、Emtree、CINAHL Headings 和 APA Thesaurus，不把同名词直接视为等价词。
- MeSH 使用 NLM MeSH RDF API 核验 descriptor、entry term、tree number、年份和限定词。
- 专有词表通过订阅平台、授权接口或人工核验记录导入；没有证据时保留为候选，不标记为已核验。
- 分别生成 PubMed、Ovid MEDLINE、Embase.com、Ovid Embase、EBSCOhost CINAHL、EBSCOhost PsycINFO、Ovid PsycINFO 和 ProQuest PsycINFO 检索式。
- 增加 PubMed ESearch 结果数和 query translation 检查。
- 增加受控词状态审计、种子文献检查和第二人复核门。

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
python3 scripts/run_ci_manifest.py
```

发布包生成在：

```text
dist/rw-research-skill-0.13.0.zip
```

本地、Pull Request、main 分支和 GitHub Release 共用 [`ci/manifest.json`](ci/manifest.json)。构建过程检查版本、4 个对外入口、22 个内部 Skill、降级注册表、公开边界、确定性测试和 2 种发行包。

## License

本项目采用 [Apache License 2.0](LICENSE)。

公共仓库：[rolandwonglonam/rw-research-skill](https://github.com/rolandwonglonam/rw-research-skill)
