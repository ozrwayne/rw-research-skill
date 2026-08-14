---
id: rw-dsh-fixture-01
label: 文献发现与检索策略
entry_skill: rw-research-router
downstream_skills:
  - rw-literature-discovery
  - rw-search-strategy
tools:
  - skill
  - mcp__rwfixture__count_sources
expects_stage_gate: false
---

# 输入

把下面这句原样发给 DSH：

```text
我要查「护士交接班标准化对住院患者用药差错的影响」的文献。先帮我把它拆成检索概念块，生成 PubMed 和 Embase 的检索式，再列出这次检索要覆盖和不覆盖的范围。
```

# 期望的可观察结果

- 入口 Skill 是 `rw-research-router`。
- 下游至少加载 `rw-search-strategy`；如果 DSH 判断需要先定问题，也可以先过 `rw-research-question`，这不算失败。
- 产出里带可执行的检索式，并写清楚数据库和字段。
- 停止状态是 `completed`。

# 记录

真实运行后把下列字段写进 `run_records/rw-dsh-fixture-01.json`：
输入、触发的入口 Skill、下游 Skill、工具调用、session 事件、输出摘要、停止状态。
记录来源是 recorder 写的 JSONL，不是人手记的印象。
