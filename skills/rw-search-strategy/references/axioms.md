# RW Search Strategy 公理

## AXIOM-01：研究问题可以是中文、英文或混合语言；检索概念先标准化为英文

- 规则：研究问题可以是中文、英文或混合语言；检索概念先标准化为英文，再保留中文解释供复核。
- 来源原子：`RWS-SEARCH-STRATEGY-009`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：研究问题的核心概念无法区分时，停止在概念澄清，不生成看似完整的检索式。

## AXIOM-02：受控词和自由词必须并行；只用受控词会漏掉新词、未索引记录和作者用语

- 规则：受控词和自由词必须并行；只用受控词会漏掉新词、未索引记录和作者用语。
- 来源原子：`RWS-SEARCH-STRATEGY-010`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：没有订阅平台或授权 API 证据时，不把 Emtree、CINAHL Headings 或 APA Thesaurus 候选标为已核验。

## AXIOM-03：不同数据库的词表分别建模

- 规则：不同数据库的词表分别建模，不能把 MeSH 名称直接贴成 Emtree、CINAHL Headings 或 APA Thesaurus。
- 来源原子：`RWS-SEARCH-STRATEGY-011`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：不抓取、复制、打包或再分发受访问控制的完整词表。

## AXIOM-04：同名受控词仍要核对定义、层级、年份、爆炸范围和限定词

- 规则：同名受控词仍要核对定义、层级、年份、爆炸范围和限定词。
- 来源原子：`RWS-SEARCH-STRATEGY-012`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：没有已知相关记录、结果检查或人工复核时，不声称检索式已验证或适合正式综述。

## AXIOM-05：只有 verified_by_public_api、verified_in_subscribed_platform 或 user_confirmed 状态可以写成已核验

- 规则：只有 verified_by_public_api、verified_in_subscribed_platform 或 user_confirmed 状态可以写成已核验。
- 来源原子：`RWS-SEARCH-STRATEGY-013`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：不把一个平台可运行的语法原样交给其他平台。

## AXIOM-06：candidate 和 unverified 状态必须保留在审计表中

- 规则：candidate 和 unverified 状态必须保留在审计表中，不能混入已核验词清单。
- 来源原子：`RWS-SEARCH-STRATEGY-014`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：研究问题的核心概念无法区分时，停止在概念澄清，不生成看似完整的检索式。

## AXIOM-07：公开 MeSH 自动核验不等于研究语境适配

- 规则：公开 MeSH 自动核验不等于研究语境适配，最终选择仍需看 scope note、tree position 和目标概念。
- 来源原子：`RWS-SEARCH-STRATEGY-015`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：没有订阅平台或授权 API 证据时，不把 Emtree、CINAHL Headings 或 APA Thesaurus 候选标为已核验。

## AXIOM-08：Emtree、CINAHL Headings 和 APA Thesaurus 不随 Skill 打包

- 规则：Emtree、CINAHL Headings 和 APA Thesaurus 不随 Skill 打包，也不通过未授权抓取补全。
- 来源原子：`RWS-SEARCH-STRATEGY-016`。
- 适用：把中英文研究问题拆成概念块，生成并核验 MeSH、Emtree、CINAHL Headings、APA Thesaurus 和平台检索式。
- 停止：不抓取、复制、打包或再分发受访问控制的完整词表。
