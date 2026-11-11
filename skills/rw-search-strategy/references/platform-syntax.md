# 平台语法

生成器区分词表和检索平台。平台界面更新后，应在正式使用前打开当前帮助页复核字段与运算符。

| 目标 | 受控词 | 自由词字段 | 生成形式 |
|---|---|---|---|
| PubMed | MeSH | `tiab` | `"Heading"[Mesh]`、`term[tiab]` |
| Ovid MEDLINE | MeSH | `ti,ab,kf` | `exp Heading/`、`term.ti,ab,kf.` |
| Embase.com | Emtree | `ti,ab,kw` | `'heading'/exp`、`'term':ti,ab,kw` |
| Ovid Embase | Emtree | `ti,ab,kw` | `exp heading/`、`term.ti,ab,kw.` |
| EBSCOhost CINAHL | CINAHL Headings | `TI`、`AB` | `MH "Heading+"`、`TI "term" OR AB "term"` |
| EBSCOhost PsycINFO | APA Thesaurus | `TI`、`AB` | `DE "Heading"`、`TI "term" OR AB "term"` |
| Ovid PsycINFO | APA Thesaurus | `ti,ab,id` | `exp Heading/`、`term.ti,ab,id.` |
| ProQuest PsycINFO | APA Thesaurus | `TI`、`AB` | `MAINSUBJECT.EXACT.EXPLODE("Heading")`、`TI,AB("term")` |

## 转换规则

- 每个平台重新生成，不对完整字符串做查找替换。
- 爆炸、聚焦、邻近、截词和短语分别记录。
- PubMed 和 Ovid MEDLINE 都使用 MeSH，但字段和命令不同。
- Embase.com 和 Ovid Embase 都使用 Emtree，但语法不同。
- PsycINFO 的词表来自 APA；EBSCOhost、Ovid 和 ProQuest 的字段不同。
- CINAHL Headings 与 MeSH 有结构联系，不代表词条可以直接互换。

## 核验门

- MeSH：可通过 NLM MeSH RDF API 自动核验 descriptor、ID、tree number 和年份。
- Emtree：使用获授权的 Elsevier 接口或 Embase 平台核验。
- CINAHL Headings：使用有权访问的 EBSCOhost CINAHL 平台核验。
- APA Thesaurus：使用有权访问的 PsycINFO 供应平台核验。
- 没有平台证据时，生成器排除专有受控词，只保留自由词和待核验清单。

## 正式使用前检查

- 在目标平台粘贴并运行完整式。
- 记录结果数、错误信息、检索日期和平台。
- 用已知相关记录检查每个概念块和组合式。
- 检查未索引记录是否能由自由词检出。
- 由第二人或信息专家复核，再标记为正式版本。
