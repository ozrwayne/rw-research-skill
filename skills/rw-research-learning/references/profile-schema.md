# 研究学习画像 Schema

`research-profile.json` 保存某次扫描后的可见研究基础和学习起点。它不是永久能力评分，默认是本地私有状态。

## v2 必填字段

```json
{
  "schema_version": "rw-research-learning/v2",
  "visibility": "private_local",
  "generated_at": "ISO-8601 timestamp",
  "topic": "学习主题；未指定时可为空字符串",
  "scope": {
    "mode": "folder | current | user",
    "discovery_roots": ["metadata discovery path"],
    "roots": ["content scan path"],
    "manifest": "scan-manifest.json"
  },
  "scan_summary": {
    "files_seen": 0,
    "indexed": 0,
    "partial": 0,
    "unsupported": 0,
    "too_large": 0,
    "sensitive": 0,
    "unreadable": 0,
    "unchanged": 0,
    "changed": 0,
    "deleted": 0
  },
  "capabilities": [
    {
      "name": "概念、方法或研究能力",
      "status": "applied | articulated | exposed | no_evidence",
      "judgment": "当前判断",
      "confidence": "high | medium | low",
      "evidence": [
        {
          "path": "source path",
          "locator": "heading, page, row, paragraph or excerpt marker",
          "reason": "该原文为什么支持这项判断",
          "source_kind": "user_output | process_record | collaborative_output | ai_assisted | external_reference | downloaded_tool | unknown",
          "authorship_confidence": "high | medium | low",
          "currentness": "current | historical | reference | unknown"
        }
      ]
    }
  ],
  "conflicts": [],
  "unknowns": [],
  "learning_start": {
    "goal": "第一阶段学习目标",
    "reason": "为什么从这里开始",
    "skipped_basics": [],
    "first_artifact": "第一份学习产物的目标或路径",
    "artifact_type": "document | worksheet | decision_register | analysis_plan | coding_exercise | evidence_map | model_input_table | other",
    "next_skill": "rw skill name or empty string"
  },
  "user_corrections": [],
  "updated_at": "ISO-8601 timestamp"
}
```

## 约束

- `visibility` 固定为 `private_local`，除非用户另行执行脱敏导出流程。
- `discovery_roots` 是元数据发现范围，`roots` 是实际内容扫描范围，不能混写。
- `applied`、`articulated` 和 `exposed` 至少保留 1 条证据。
- `applied` 和 `articulated` 至少有一条明确的用户角色证据，作者归属信心为 medium 或 high。external_reference、downloaded_tool、unknown 不单独支持这两个状态；ai_assisted 必须另有非空 `user_role` 说明，或由独立用户过程记录支持。
- `no_evidence` 可以没有证据，但必须说明扫描范围。
- `confidence` 表示对当前材料判断的信心，不是对用户能力的评分。
- `skipped_basics` 只能来自 `applied` 或多来源 `articulated` 证据。
- 用户纠正必须追加到 `user_corrections`，不覆盖原判断来源。
- `unchanged`、`changed` 和 `deleted` 是扫描活动计数，不与覆盖状态相加计算 `files_seen`。

## 兼容

校验器继续接受 `rw-research-learning/v1`，新画像使用 v2。

校验器检查字段类型、数组及枚举，布尔值不作为扫描数量。`skipped_basics` 使用 capabilities 中的名称，并连接 applied 或来自至少 2 个不同来源路径的 articulated 记录。空模板只表示可填写的结构，不表示完成扫描或形成了有效能力判断。

画像 JSON 加载拒绝重复键、NaN、Infinity 及 1e999 等溢出数字，避免同一字段有多个含义。
