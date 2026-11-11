# 判断学习旁车结构

判断学习记录使用独立文件，不改变 `review-ledger.json` 的 `rw-peer-review/v1` 结构。

## 文件关系

- 一条需要形成判断的 Finding 对应一个 `judgment-learning/FIND-ID.json`。
- `review_id` 和 `finding_id` 必须能指回 Review Ledger。
- 历史评审没有旁车文件时继续按旧结构读取，不回填判断。
- 旁车文件属于内部过程记录，不进入 reviewer report 或 editor decision。

## 顶层字段

| 字段 | 含义 |
|---|---|
| `schema_version` | 固定为 `rw-peer-review-judgment-learning/v1` |
| `review_id` | 对应 Review Ledger 的评审 ID |
| `finding_id` | 对应一条 Finding |
| `mode` | `guided`、`full`、`abbreviated` 或 `off` |
| `novice_support` | 零经验用户的基线题、示例、引导卡、反馈和能力检查 |
| `machine_issue_map` | 原问题、证据位置、研究对象、目标效应和未知项 |
| `user_initial_judgment` | 用户在机器结论前写下的判断、依据、信心和不确定性 |
| `strongest_challenge` | 当前证据下最强的一条质疑 |
| `strongest_response` | 当前材料中最强的一条回应，不补写作者没有说过的话 |
| `verification` | 正文、补充材料、作者解释、统计原则和研究目标核对 |
| `concepts_used` | 本次判断实际用到的概念，不写通用课程 |
| `user_final_judgment` | 用户核对后的判断、处置、依据和改判证据 |
| `transfer_check` | 交付后的相邻案例检查 |
| `delivery_boundary` | 对外交付物干净度检查 |
| `updated_at` | UTC ISO 8601 时间 |

## 状态

- `confidence`：`high`、`medium`、`low`、`unknown`。
- `strongest_challenge.target`：`data`、`measurement`、`analysis`、`estimand`、`reporting`、`interpretation`。
- 五项材料核对：`verified`、`not_verified`、`not_applicable`。
- 回应核对：`yes`、`partial`、`no`、`unclear`。
- 最终处置：`sustained`、`narrowed`、`withdrawn`、`answered`、`deferred`、`needs_input`。
- 迁移：`not_run`、`passed`、`needs_practice`。
- 干净度：`not_run`、`passed`、`failed`。

## 约束

1. `guided` 用于没有审稿经验的用户；`full` 和 `abbreviated` 用于已经能独立完成初判的用户。3 种模式都保留初判、最强质疑、最强回应、核对和终判。
2. 初判和终判都要有 `statement` 和 `basis`。材料不足时，写明待核验材料，不猜结论。
3. 五项材料核对不能停在 `not_verified` 后进入综合。
4. `response_mentioned`、`response_hits_issue`、`response_is_sufficient` 和 `body_still_needs_reporting` 分开记录。
5. `response_is_sufficient=yes` 且 `body_still_needs_reporting=yes` 时，最终处置不能是 `answered` 或 `withdrawn`。
6. 对外交付前，`internal_fields_excluded=true` 且 `cleanliness_check=passed`。
7. `mode=off` 只表示显式关闭学习记录，不产生判断学习 PASS。
8. `guided` 先做一条合成基线题，再看另一条合成 worked example，之后填写当前 Finding 的引导审稿卡。示例不能使用当前稿件。
9. “完成一次审稿”和“掌握审稿”分开。`ready` 检查本次任务，`mastery` 检查能力迁移。
10. `mastery` 不使用 Skill 自己发明的时间或案例数。必须先记录课程、期刊或导师采用的标准、来源和要求的独立案例数。
11. 质量检查采用 Review Quality Instrument 的 7 个核心维度。全部达到预设标准、没有 critical miss、独立案例数量满足标准，并由评定人记录 `meets_predeclared_standard` 后，`mastery` 才可 PASS。

## 退出码

`scripts/judgment_learning.py ready` 使用：

- PASS：0。
- REVIEW：1。用于 `mode=off` 或迁移仍需练习但不阻断本次交付。
- BLOCK：2。用于结构错误、判断缺失、核对未完成或交付物未清理。

`scripts/judgment_learning.py mastery` 使用同一组退出码。PASS 只表示记录中的掌握条件满足，不表示可以审所有研究类型。

## 独立性检查

独立案例的 `case_id` 不得重复。`guided` 的 worked example 必须与 baseline 不同，二者 ID 均不得等于当前 Finding。案例来源、是否真正独立、用户是否实际作答仍需人工核验；结构通过不认证学习行为。
