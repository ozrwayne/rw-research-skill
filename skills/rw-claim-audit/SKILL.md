---
name: rw-claim-audit
description: |
  逐条核验论文、报告或研究笔记中的事实性主张是否被指定来源原文支持，保存主张位置、来源指针、原文定位、判断和阻断状态。Use when the user asks for“检查引用是否支持这句话”“做 claim-to-source audit”“核验数字、趋势或因果说法”“投稿前查主张”,or requests the rw-claim-audit workflow.
---

# RW Claim Audit

检查来源是否支持具体主张。引用存在、格式正确和支持主张是 3 个不同问题。

## 启动

1. 读取 `references/method.md` 和 `references/verdicts.md`；核验作者自己的数字时读 `references/self-data.md`。
2. 确认文稿版本、允许使用的来源和能否访问全文。
3. 用 `assets/claim-audit-template.json` 建立记录，或运行 `scripts/claim_audit.py init`。
4. 逐条回到原始来源，保存来源指针和页码、段落、表、图或补充材料位置。
5. 运行 `validate`、`summary` 和 `gate`。
6. 交付前读取 `references/acceptance.md`。

## 工作阶段

1. 提取数字、类别、趋势、比较、因果、方法和作者解释类主张。
2. 为每条主张记录文稿位置和主张范围。
3. 找到被引来源中的对应位置；只有摘要时标明访问边界。
4. 比较人群、时间、变量、方向、数值和不确定性。
5. 给出 verdict，并说明差异会怎样改变结论。
6. 核验作者自有数字时，只拿文稿和原始结果文件，按 `references/self-data.md` 的七种对账逐条比。
7. 对阻断项收窄、删除或更换来源，再重新核验。

## 命令

```bash
python3 scripts/claim_audit.py init claim-audit.json --document-id DOC-001 --document-path manuscript.md
python3 scripts/claim_audit.py add-claim claim-audit.json --id CLM-001 --text "Claim text" --location "Results, paragraph 3" --claim-type quantitative
python3 scripts/claim_audit.py set-verdict claim-audit.json --claim-id CLM-001 --verdict VERIFIED --source-id SRC-001 --source-pointer paper.pdf --locator "p. 4, Results" --support-note "人群、数字和时间点一致"
python3 scripts/claim_audit.py validate claim-audit.json
python3 scripts/claim_audit.py summary claim-audit.json
python3 scripts/claim_audit.py gate claim-audit.json
```

`gate`：PASS 返回 0，REVIEW 返回 1，BLOCK 返回 2。

## 运行规则

- DOI 或文献存在只能证明来源存在。
- `VERIFIED` 必须有具体 locator 和支持说明。
- 来源支持范围小于句子范围时，收窄句子。
- 摘要不能支持摘要未报告的细节。
- 作者解释、测得结果和当前推断分开核验。
- 数字同时核对分母、单位、时间点、人群和分析集。
- 因果措辞需要与设计和来源措辞相符。
- 无法访问全文时使用 `UNVERIFIABLE_ACCESS`，不能写成 `VERIFIED`。
- 不自动修改文稿；先输出核验结果和修复动作。
- 核验自有数字时不读实验日志、分析笔记、既往审计结果和写作方的任何总结。写实验和写论文的是同一方，给它自己的总结就会按预期读数据。
- 相对提升、均值口径、随机次数和对比条件逐一回到原始文件核对，不采信文稿里的换算结果。
- 文稿和结果文件都没变时不重跑核验，不挂定时器。

## 输出

- Claim Audit JSON。
- verdict 计数和 PASS／REVIEW／BLOCK 状态。
- 每条问题的文稿位置、来源位置、差异和修复动作。

## 停止条件

- 没有文稿版本或主张位置时，不开始批量核验。
- 找不到来源原文时，不给 `VERIFIED`。
- `DISTORTED` 或 `UNSUPPORTED` 未处理时，状态保持 BLOCK。

## 接续

- 提取原文：`rw-paper-extractor`。
- 调整论文：`rw-phd-write`。
- 核对引用身份和格式：`rw-citation-audit`。
- 审查结论：`rw-research-referee`。
- 局部修改：`rw-revision-patch`。
