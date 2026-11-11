# RW Search Strategy 来源证据

## 公开来源用途

- `mesh_rdf`：NLM Medical Subject Headings RDF API。查询 MeSH descriptor、entry term、tree number、qualifier 和年度版本；公开接口返回的匹配仍需结合研究语境判断。 官方页面：https://id.nlm.nih.gov/mesh/
- `pubmed_help`：PubMed User Guide。核对 PubMed 字段标签、Automatic Term Mapping、短语检索和检索历史。 官方页面：https://pubmed.ncbi.nlm.nih.gov/help/
- `nlm_mesh_terms`：NLM Terms and Conditions for Data。确认 NLM 数据下载、再分发和使用边界。 官方页面：https://www.nlm.nih.gov/databases/download/terms_and_conditions.html
- `elsevier_embase`：Elsevier Embase。确认 Embase 和 Emtree 的产品范围；具体词表与检索结果依赖订阅平台。 官方页面：https://www.elsevier.com/products/embase
- `elsevier_embase_api`：Elsevier Developer Portal。确认 Embase API 的认证和访问条件；没有获授权接口时不自动抓取 Emtree。 官方页面：https://dev.elsevier.com/
- `ebsco_cinahl`：EBSCO CINAHL Database。确认 CINAHL 的主题范围和 CINAHL Headings；具体首选词与爆炸选项在订阅平台核验。 官方页面：https://www.ebsco.com/products/research-databases/cinahl-database
- `ebsco_eds_api`：EBSCO Discovery Service API。确认 EBSCO API 需要客户认证和 profile；没有授权时使用人工平台核验导入。 官方页面：https://developer.ebsco.com/knowledge-services/docs/eds-api
- `apa_psycinfo`：APA PsycINFO。确认 PsycINFO 的数据库范围和受控词入口；不同供应平台需要各自语法转换。 官方页面：https://www.apa.org/pubs/databases/psycinfo
- `apa_terms`：APA Website Terms and Conditions of Use。确认 APA 内容访问和自动化使用边界；不系统下载或打包 APA Thesaurus。 官方页面：https://www.apa.org/about/apa/terms

## 边界

- 这里保存的是来源定位和短用途说明，不是完整标准副本。
- 报告规范不等于设计质量评价；偏倚工具不等于写作模板。
- 版本、政策、费用、API 和期刊要求在任务执行时核验。
