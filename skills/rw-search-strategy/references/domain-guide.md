# RW Search Strategy 选择表

| 情形 | 执行动作 | 不要做 |
|---|---|---|
| 问题为中文或中英混合 | 保留原文并建立英文规范概念、拼写变体和缩写 | 只做逐字翻译 |
| 目标为 PubMed 或 Ovid MEDLINE | 通过 NLM MeSH 接口核验词条，再按各平台语法渲染 | 把 PubMed 字段标签复制到 Ovid |
| 目标为 Embase.com 或 Ovid Embase | 导入订阅平台已核验的 Emtree 词条，并分别渲染语法 | 把 MeSH 当成 Emtree |
| 目标为 EBSCOhost CINAHL | 在 CINAHL Headings 中核验首选词和爆炸选择 | 因其结构参考 MeSH 就省略平台核验 |
| 目标为 PsycINFO | 核验 APA Thesaurus 词条，再按 EBSCOhost、Ovid 或 ProQuest 分别渲染 | 混用三个平台的字段和邻近符 |
| 没有订阅数据库访问 | 输出自由词和受控词候选，将专有词表状态标为 requires_platform_validation | 伪造已核验状态 |
| 用于系统综述或范围综述 | 完成种子文献和第二人复核，并保存完整版本记录 | 把自动草案直接写成最终检索式 |

## 核心规则

- 研究问题可以是中文、英文或混合语言；检索概念先标准化为英文，再保留中文解释供复核。
- 受控词和自由词必须并行；只用受控词会漏掉新词、未索引记录和作者用语。
- 不同数据库的词表分别建模，不能把 MeSH 名称直接贴成 Emtree、CINAHL Headings 或 APA Thesaurus。
- 同名受控词仍要核对定义、层级、年份、爆炸范围和限定词。
- 只有 verified_by_public_api、verified_in_subscribed_platform 或 user_confirmed 状态可以写成已核验。
- candidate 和 unverified 状态必须保留在审计表中，不能混入已核验词清单。
- 公开 MeSH 自动核验不等于研究语境适配，最终选择仍需看 scope note、tree position 和目标概念。
- Emtree、CINAHL Headings 和 APA Thesaurus 不随 Skill 打包，也不通过未授权抓取补全。
- 平台语法转换要重新处理字段、邻近运算符、截词、短语、爆炸和聚焦，不做字符串替换。
- 设计、年龄、动物或语言过滤器只有在方案要求并核验来源后才加入。
- 已知相关文献未被检出时，先检查词表、字段、短语和逻辑块，不用增加无边界同义词掩盖问题。
- 结果数用于发现异常，不能单独证明查全率、相关性或检索质量。
- 每次修改保存数据库、平台、日期、词表版本、完整检索式和修改原因。
- 正式综述的检索式在定稿前需要第二人或信息专家复核；自动生成结果标为草案。
