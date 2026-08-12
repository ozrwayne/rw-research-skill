---
name: rw-citation-audit
description: |
  核对文内引用、参考文献、作者身份、年份消歧、DOI 和指定格式规则，不判断来源是否支持主张。 Use when the user asks for “检查引用格式”、“核对文内引用和参考文献”、“检查同姓作者”、“做 citation audit”, or requests the rw-citation-audit workflow. Runs without a private local workspace or preset research-lab; use user-provided material and bundled public-source methods.
---

# RW Citation Audit

核对文内引用、参考文献、作者身份、年份消歧、DOI 和指定格式规则，不判断来源是否支持主张。

## 启动

1. 读取 `references/standalone.md`、`references/method.md` 和 `references/standards.md`。
2. 读取用户本轮提供的材料；没有材料时，只完成当前证据允许的部分。
3. 需要规则判断时检索 `references/atoms.jsonl`；遇到相似任务时读取 `references/cases.md`。
4. 需要选择方法或工具时读取 `references/domain-guide.md`，并使用 `assets/worksheet.md` 组织交付。
5. 读取 `references/acceptance.md`。`references/behavior-tests.json` 只用于测试，不作为用户任务事实。
6. 当前文献、API、报告规范和期刊要求可能变化时，打开 `references/source-map.md` 中的官方链接核验并记录日期。

## 工作阶段

1. 确认文稿版本、引用格式、参考文献边界和允许使用的元数据来源。
2. 建立文内引用与参考文献的双向对应表。
3. 核验作者姓名、年份、题名、来源、DOI 和出版状态。
4. 按指定格式检查同姓不同作者、同作者同年、同首作者同年的消歧。
5. 检查排序、重复、缺失字段、DOI 规范和文内引用形式。
6. 把问题分为 BLOCK、REVIEW 和 PASS，并将主张支持问题转交 rw-claim-audit。

## 运行规则

- 来源存在、来源支持主张和引用格式正确是 3 个问题，分别核验。
- 判定来源存在必须留下可回到的验证位置，例如 DOI 解析结果或索引条目。查不到就写无法核验，不按题名和年份推断。
- 预印本和正式发表版本分开记录，题名、年份和版本在不同版本之间发生漂移时，标明采用哪一版和为什么。
- 引用格式规则必须来自用户指定的 style guide、机构要求或目标期刊当前规则。
- 同姓作者的首字母、同作者同年的字母后缀和同首作者同年的作者展开按指定格式处理。
- 文内每个引用应能回到一个参考文献条目，参考文献中的每项也要说明是否在正文使用。
- DOI 先规范化再查重，不根据题名猜 DOI。
- Crossref、ORCID 和出版商元数据可以互相核对，但单一元数据源可能不完整。
- 正式题名、作者拼写和期刊名不做语言本地化改写。
- 参考文献排序和标点检查不能替代作者身份核验。
- 自动解析失败的团体作者、非拉丁姓名和复杂作者组进入人工 REVIEW。
- 作者姓名冲突未解决时不能标记为 PASS。
- 文稿变化后，旧 citation audit 结果标记为 STALE。
- 文稿和参考文献都没变时不重跑核验，不挂定时器。
- 引用核验只修改明确错误，不为统一外观改写来源题名。

## 输出

- 文内引用与参考文献双向核对表。
- 作者消歧、年份、DOI、排序和格式问题清单。
- PASS、REVIEW、BLOCK 和 STALE 状态。

## 停止条件

- 没有文稿版本、参考文献列表或指定引用格式时，不给最终 PASS。
- 无法核验作者或出版元数据时标记 REVIEW，不生成字段。
- 不把 citation audit 当成 claim-to-source audit。
- 不自动修改来源的正式题名和作者姓名。

## 随 Skill 提供的资源

- `scripts/citation_audit.py`：检查文内引用、参考文献、同姓作者消歧和重复 DOI。
- `assets/citation-audit-template.md`：引用核验记录模板。

## 独立运行

- 默认不读取私人工作区、个人语料目录或预设 research-lab。
- 用户提供的文件、文本、链接和数据是当前任务输入，不是安装依赖。
- 网络不可用时，使用 Skill 内的稳定方法继续；需要当前事实的部分标记为待核验。
- 本包内其他科研 Skill 存在时可以接续；单独安装时直接返回下一步说明，不停止当前任务。

## 来源纪律

- 把用户材料、公开来源、当前推断和未知事项分开。
- 报告规范只检查报告透明度，不自动证明设计质量。
- 公开来源摘要保存在 Skill 内；需要版本、费用、政策、API 或期刊现状时回到官方页面。
- 不生成不存在的论文、数据、DOI、工具运行结果或期刊要求。
