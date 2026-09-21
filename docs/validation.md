# RW Research Skill v0.13.0 合并验证

合并 0.12.0 主包审计修复与独立 `rw-peer-review` v0.9.2。旧分支基于 0.11.0；本次仅采用其同行评审模块，其他模块沿用较新的 0.12.0 主包实现。4 个公开入口、22 个 Skill。

- 本地 CI manifest 四项检查通过：仓库、确定性回归、完整 ZIP 和 SkillHub ZIP。确定性回归 299 项通过，公开内容检查覆盖 425 个文件，失败项为 0。
- DSH 适配测试共 24 项，其中 10 项本地检查通过、14 项因没有 DSH 运行时而跳过。历史 0.12.0 的 21 Skill DSH 结果不转移为当前 22 Skill 的实机验收。
- 新增 Peer Review 的合成合同没有运行模型行为测试；本次没有新的跨模型效果实验，也没有真实投稿或 GitHub Release。

以下为历史版本记录，不将旧版测试结论自动转移到 v0.13.0。

# 2026-09-19 本地审计

本次对现有 0.12.0 工作树做本地软件修复，未创建发布或转移历史跨模型标签。当前验证入口为 `python3 scripts/run_ci_manifest.py`，覆盖仓库合同、确定性回归、完整包和 SkillHub 包。输入隔离、来源完整性、文件保全及打包边界见 `software-integrity.md`。新增 5 个合成行为合同只通过结构核验，`execution_status` 保持 `not_run`；没有执行新的模型行为或效果实验。以下版本记录保留为历史记录。

# RW Research Skill v0.12.0 验证记录

日期：2026-08-04。

## 当前证据

- 发布 Skill：21 个。
- 对外入口：4 个。
- License：Apache-2.0。
- 541 条知识原子、170 条公理、149 个案例和反例、162 条行为合同。
- Router 与投稿包的确定性测试通过。
- 仓库版本、入口 manifest、目录、公开计数和 Skill 接续检查通过。
- 公共内容检查覆盖 Skill、文档和跨模型评测记录。541 条知识原子、149 个案例和 162 条行为合同的隐私检查失败项为 0。
- 知识原子不保留原始个人材料字段；案例和行为合同标记为合成输入。
- `rw-citation-audit` 独立结构检查通过。
- 确定性 Python 工具测试见仓库 `tests/` 和 CI 记录。

## v0.12.0 投稿路由

`rw-research-router` 在稿件完成、已有目标期刊或需要选刊，且没有已知研究关键阻塞项时，交接到 `rw-journal-submission`。交接包含稿件版本、目标期刊、作者、披露、数据、伦理、引文和未解决项。

`rw-journal-submission` 可以整理 Submission Packet、期刊要求和门户字段。期刊当前要求无法访问时标记为待核验。最终 `Submit` 始终由人类完成。

本次本地检查包括公开边界检查、Router 路由测试、Submission Packet 测试和完整发布 CI。它们检查打包结构和确定性行为，不证明任何真实期刊已接受投稿。

## 4 个对外入口和治理文件

`manifest.json` 记录 4 个对外入口及 21 个内部 Skill 的唯一归属。旧 Skill 名称继续可用，但不作为默认导航。

- `rw-research-router`：研究启动与推进。
- `rw-paper-extractor`：论文精读与证据。
- `rw-research-referee`：研究设计与审查。
- `rw-phd-write`：论文写作与投稿。

`ci/manifest.json` 是本地、Pull Request、main 分支和 GitHub Release 的共同检查清单。`docs/degradation-registry.json` 当前包含 10 条降级规则，记录触发条件、状态、替代动作、禁止行为、用户提示、责任 Skill 和测试引用。`docs/degradation-scenarios.json` 为 4 个对外入口各保存 2 个降级场景。

## v0.11.0 安装和前向测试

2026-07-23 在干净临时目录使用当前 `skills` CLI 安装本地仓库：

- 默认 `--list` 显示 4 个对外入口。
- 默认安装后，普通 `skills list --json` 显示 4 个入口。
- 安装目录中保留 21 个 Skill。
- 设置 `INSTALL_INTERNAL_SKILLS=1` 后，`--list` 和已安装列表均显示 21 个 Skill。

4 个真实 Codex 子 Agent 分别加载 1 个入口，并处理 1 个合成降级场景。4 个结果均通过检查：没有补造缺失证据，说明了阻断或降级状态，并给出待补材料或下一步。记录见 [`evals/entry-degradation/2026-07-23-v0.11.0/`](../evals/entry-degradation/2026-07-23-v0.11.0/)。

这次前向测试覆盖 4 个提示和当前运行环境。它不证明所有模型、提示和真实科研任务都会执行相同行为。

## v0.10.0 多数据库检索策略

`rw-search-strategy` 处理中文、英文和混合语言研究问题。它建立英文规范概念、自由词、受控词审计记录和分平台检索式。

当前确定性测试覆盖：

- PubMed 的 MeSH 和 `tiab` 自由词组合。
- Ovid MEDLINE、Embase.com、Ovid Embase 和 EBSCOhost CINAHL 的独立语法。
- EBSCOhost、Ovid 和 ProQuest 3 种 PsycINFO 语法。
- 未核验 Emtree 候选默认不进入可执行式。
- 订阅平台核验记录的来源和日期门。
- 专有词表不能使用 MeSH 的公开 API 状态。
- JSON 和 Markdown 输出。

2026-07-23 的在线验收使用 NLM 官方接口。MeSH RDF 返回 `Depressive Disorder`、descriptor `D003866`、tree number `F03.600.300` 和词条状态。PubMed ESearch 对测试式返回结果数和 query translation。在线结果说明接口链路可用，不证明完整检索策略的查全率。

Emtree、CINAHL Headings 和 APA Thesaurus 没有打包在仓库中。没有订阅平台、授权接口或用户核验记录时，它们保持 `candidate` 或 `unverified` 状态。

## v0.9.0 PDF Paper Case

`rw-paper-extractor` 增加 PDF 工作区、图表候选提取、跨页表格拼接、5 阶段报告和 Claim Audit／LitNet 接续。

当前确定性测试覆盖：

- 来源 hash、配置 hash 和阶段状态。
- 章节候选识别、置信度和人工修正。
- 参考文献条目不被识别为正文章节。
- 跨页表格候选拼接，并保留每一页的 page、bbox 和 text unit 定位。
- 上游 hash 改变后的 STALE 传播。
- Claim Audit 为 PASS 后生成 LitNet 回写预览。

真实回归使用 Neal et al. 2021 的 1 篇 PDF。结果包含 362 个文本单元、20 个章节候选和 2 个视觉对象，其中 1 个表格跨第 18—19 页拼接。该结果验证这份 PDF 的流程，不代表所有版式都能自动识别。章节和图表仍保留复核状态。

## v0.8.0 本地积累扫描和学习起点

`rw-research-learning` 支持指定文件夹、当前项目和可读用户内容 3 种模式。索引使用 Python 标准库和 SQLite，不要求私人工作区或预设索引。

当前确定性测试覆盖：

- Markdown、文本和 Word 提取。
- 主题检索和命中片段。
- 环境变量文件的敏感排除。
- 第二次扫描复用未变更文件。
- 操作系统根目录拒绝。
- `research-profile.json` Schema 验证。
- 元数据范围发现不返回正文。
- 损坏 PDF 不终止其他文件扫描。
- 外部参考不能单独支持 `applied`。
- 项目内部名为 `library` 的资料目录不会被当成用户主目录下的系统 Library 跳过。

这些测试验证扫描器的读取、排除、增量和结构行为。它们不证明 Agent 在所有用户材料上都能正确判断能力或学习起点。

## v0.7.1 跨模型配对验证记录

运行 `2026-07-20-cross-model-v2` 使用 2 家提供方的 4 个模型入口：

- OpenAI `gpt-5.6-sol`；
- OpenAI `gpt-5.6-terra`；
- Anthropic `sonnet`，提供方用量记录包含 `claude-sonnet-4-6` 和辅助 `claude-haiku-4-5-20251001`；
- Anthropic `opus`，提供方用量记录包含 `claude-opus-4-8` 和辅助 `claude-haiku-4-5-20251001`。

评测包含 8 个合成任务，覆盖 `rw-claim-audit`、`rw-revision-patch`、`rw-research-passport` 和 `rw-research-router`。每个任务分别运行带 Skill 和不带 Skill 条件，共 64 次调用。模型工具和网络工具关闭，输出按固定 JSON Schema 解析，再用确定性规则判分。

结果：

- 带 Skill：32／32，100%；
- 不带 Skill：19／32，59.375%；
- 配对通过率差：+40.625 个百分点；
- 每个任务的带 Skill 跨模型通过率：4／4；
- 带 Skill 条件的执行或解析错误：0。

评测协议、任务、模型配置、完整输出、检查结果、CLI 版本、prompt hash 和 Skill-context hash 保存在 [`evals/cross-model/`](../evals/cross-model/)。本次 [结果摘要](../evals/cross-model/results/2026-07-20-cross-model-v2/summary.md) 标记为 `CROSS_MODEL_VERIFIED`。

第一次完整运行 `2026-07-20-cross-model-v1` 为 `CROSS_MODEL_NOT_VERIFIED`：带 Skill 26／32，路由表缺少引用核验映射，Passport 测试状态与正式 Schema 不一致。该记录保留为开发证据，没有改分后覆盖。修复定义后另建并固定第 2 组任务。

以上 2 次运行属于 v0.7.1。结果文件保留当时的模型配置和 hash。它们不作为 v0.8.0 默认模型表的运行证据。

## v0.8.0 本地模型和真实文档审阅

v0.8.0 默认模型表为：

- Codex `gpt-5.6-sol`；
- Codex `gpt-5.6-terra`；
- Codex `gpt-5.6-luna`；
- Claude `claude-opus-4-8`。

Claude 调用使用本机 Claude CLI 登录状态。真实文档审阅器要求输出保存在公开仓库外。汇总不按 4 个模型投票。Codex 和 Claude 锚定同一处原文时，问题进入 cross-provider findings；只有 Codex 重复发现时，问题进入 Codex-family findings。

当前确定性测试覆盖默认模型表、`.docx` 读取、引用锚点合并和 provider 平衡分类。v0.8.0 的完整 4 模型合成矩阵尚未运行，因此不把 v0.7.1 的 `CROSS_MODEL_VERIFIED` 标签转移到当前模型表。

2026-07-20 的合成文档 smoke test 中，Sol、Terra 和 Luna 均返回符合 Schema 的结果。Claude CLI 在调用前后显示未登录，因而没有得到 Opus 4.8 输出。该结果标记为 `REVIEW_INCOMPLETE`，不作为 4 模型验证记录。运行器现已增加登录预检；完成一次 `claude auth login` 后才能运行完整本地矩阵。

## 证据边界

- 160 条行为合同没有被全部调用执行。跨模型矩阵执行的是另存的 8 个合成任务。
- 静态自检证明文件、结构、数量和独立运行约束符合当前发布要求，不证明模型输出质量。
- v0.7.0 记录的场景结果属于维护者记录。仓库没有同时保存完整模型输出、模型版本、参数、判分和重放日志，因此不作为独立复现证据。
- 当前已有合成任务的 without-Skill 基线和跨模型执行记录。判分是字段和值的确定性检查，不使用被评模型或另一个模型做 Judge。
- 第 2 组任务在首次调用前固定，但它由仓库维护者编写，不是外部独立 benchmark。
- 运行开始时工作树含未提交变更。记录保存了 source revision、任务文件 hash、prompt hash 和 Skill-context hash；这不等同于干净 commit 上的独立复现。
- 当前状态：`CROSS_MODEL_VERIFIED` 只适用于 v0.7.1 已记录的合成任务、模型入口和版本。v0.8.0 的学习入口、v0.9.0 的 PDF Paper Case、v0.10.0 的检索策略和 v0.11.0 的 4 个对外入口尚未运行跨模型矩阵。整包仍不标记 `VERIFIED EFFECTIVE`。

## 发布边界

- 本地硬依赖：0。
- 私人工作区路由：0。
- 真实业务材料：0。
- SkillHub 公共版保留公开来源入口，不包含私人来源摘录和本地研究材料。
- 完整发行包和 SkillHub 公共版共用 `scripts/check_public_privacy.py` 构建门。
- 安装路径使用仓库和 `npx skills add`。GitHub Release 不附带安装 zip。

## 下一步证据

- 使用 v0.8.0 当前模型表运行一组新的合成任务记录，不覆盖 v0.7.1 结果。
- 用多种本地资料结构测试 `rw-research-learning` 的能力证据分类和学习起点选择。
- 使用 3 至 5 个去标识真实任务做 project-local paired eval。
- 增加第 2 次重复运行，检查同一模型的波动。
- 由未参与 Skill 和 fixture 编写的人复核任务、预期值和结果。
