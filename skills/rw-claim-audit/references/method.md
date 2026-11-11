# 方法

## 输入门

- 固定文稿版本或文件 hash。
- 给出主张位置和允许使用的来源。
- 说明全文、摘要或二手材料的访问范围。

## 核验单位

一条记录只处理一个可以判断真假的主张。一个句子含多个主张时拆开。

## 比较项

1. 主张类型和强度。
2. 人群、情境和时间。
3. 变量、比较和结果。
4. 数字、分母、单位和不确定性。
5. 来源原文是否直接说了这件事。
6. 来源设计能否支持当前措辞。

## Gate

- PASS：所有需核验主张为 `VERIFIED` 或 `NOT_APPLICABLE`。
- REVIEW：存在 `PARTIAL`、`UNVERIFIABLE_ACCESS` 或 `NOT_CHECKED`。
- BLOCK：存在 `DISTORTED` 或 `UNSUPPORTED`。

Gate 是文稿核验状态，不是论文质量评分。
