# 判断学习流程

这套流程训练用户形成和修正评审判断。它不替代 Review Ledger，也不改变 `review_ledger.py gate` 的含义。

## 何时运行

- 默认用于需要判断一条 Finding、作者回应、统计结论或修改是否成立的任务。
- 用户第一次审稿或不能独立说明“结论—证据—问题—影响”时，使用 `guided`，并读取 `references/novice-review.md`。
- 用户只要机械整理时，可以显式设为 `off`。`off` 不产生学习 PASS。
- 预先声明的课程、期刊或导师标准允许，并且近期同类独立案例达到该标准时，可以使用 `abbreviated`。
- 研究类型、目标效应或争议类型变化时，回到 `full`。
- `guided` 达到掌握标准后转为 `full`；第一次处理新的研究设计或问题类型时重新使用 `guided`。

## 顺序

1. `guided` 先完成合成基线题和另一个合成 worked example，再填写当前 Finding 的引导审稿卡。
2. 机器只整理原问题、证据位置、研究对象、目标效应和未知项，不先给结论。
3. 用户写初判、依据、信心和不确定性。
4. 机器写当前材料支持的最强质疑，标明它攻击数据、测量、分析、estimand、报告还是解释。
5. 机器或用户写当前材料中的最强回应。没有回应时写“未提供可核对回应”，不替作者补话。
6. 分别核对正文、补充材料、作者解释、统计原则和研究对象／estimand。
7. 只解释当前判断需要的概念。
8. 用户写终判、处置、依据、剩余不确定性，以及什么证据改变了或会改变判断。
9. 终判完成后，综合 Agent 才生成对外报告。
10. 对外报告清理内部字段并通过干净度检查。
11. 交付后用一个不同材料、同类结构的短案例做迁移检查。
12. 单独运行 `mastery`，不要从交付完成推断用户已经掌握。

## 固定区分

- 作者提到了，不等于回应命中了原问题。
- 回应命中了，不等于回应成立。
- 回应成立了，不等于正文已经可复核。
- `p` 值分类、估计值、不确定性、效应方向和结论变化分开写。
- 整体交互、简单效应、方向一致和亚组同质性分开写。
- 敏感性分析要核对是否仍针对同一个目标效应。
- 多个 Agent 同意，只说明问题被重复提出，不构成独立验证。
- Review Ledger 的 `gate PASS` 只表示 Finding 已有处置，不表示稿件质量或用户掌握。

## 对外交付边界

可进入报告：已核对的原文位置、研究对象、目标效应、统计结果、作者已完成或需要完成的修改、公开证据。

留在内部：用户初判、改判过程、Agent 分歧、模型信息、学习字段、迁移记录、内部路径、hash 和日志。

## 命令

```bash
python3 scripts/judgment_learning.py init judgment-learning/FIND-001.json --review-id RVW-001 --finding-id FIND-001
python3 scripts/judgment_learning.py validate judgment-learning/FIND-001.json
python3 scripts/judgment_learning.py summary judgment-learning/FIND-001.json
python3 scripts/judgment_learning.py ready judgment-learning/FIND-001.json --stage synthesis
python3 scripts/judgment_learning.py ready judgment-learning/FIND-001.json --stage delivery
python3 scripts/judgment_learning.py mastery judgment-learning/FIND-001.json
```
