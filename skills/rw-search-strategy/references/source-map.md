# 来源映射

## 随 Skill 提供

- `references/method.md`：完整执行方法。
- `references/domain-guide.md`：任务选择和边界。
- `references/atoms.jsonl`：可检索规则。
- `references/cases.md`：案例和反例。
- `assets/worksheet.md`：输出模板。

## 公开来源

- [NLM Medical Subject Headings RDF API](https://id.nlm.nih.gov/mesh/)：查询 MeSH descriptor、entry term、tree number、qualifier 和年度版本；公开接口返回的匹配仍需结合研究语境判断。
- [PubMed User Guide](https://pubmed.ncbi.nlm.nih.gov/help/)：核对 PubMed 字段标签、Automatic Term Mapping、短语检索和检索历史。
- [NLM Terms and Conditions for Data](https://www.nlm.nih.gov/databases/download/terms_and_conditions.html)：确认 NLM 数据下载、再分发和使用边界。
- [Elsevier Embase](https://www.elsevier.com/products/embase)：确认 Embase 和 Emtree 的产品范围；具体词表与检索结果依赖订阅平台。
- [Elsevier Developer Portal](https://dev.elsevier.com/)：确认 Embase API 的认证和访问条件；没有获授权接口时不自动抓取 Emtree。
- [EBSCO CINAHL Database](https://www.ebsco.com/products/research-databases/cinahl-database)：确认 CINAHL 的主题范围和 CINAHL Headings；具体首选词与爆炸选项在订阅平台核验。
- [EBSCO Discovery Service API](https://developer.ebsco.com/knowledge-services/docs/eds-api)：确认 EBSCO API 需要客户认证和 profile；没有授权时使用人工平台核验导入。
- [APA PsycINFO](https://www.apa.org/pubs/databases/psycinfo)：确认 PsycINFO 的数据库范围和受控词入口；不同供应平台需要各自语法转换。
- [APA Website Terms and Conditions of Use](https://www.apa.org/about/apa/terms)：确认 APA 内容访问和自动化使用边界；不系统下载或打包 APA Thesaurus。

## 使用规则

- Skill 不要求这些网页在每次运行时都可访问；稳定方法已经写入本地引用文件。
- 涉及当前版本、政策、费用、认证、额度或期刊要求时，必须回到官方页面核验。
- 不复制完整清单或受版权保护的长段内容，只保留用途说明和执行判断。
