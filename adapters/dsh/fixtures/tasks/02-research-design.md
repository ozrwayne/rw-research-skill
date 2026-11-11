---
id: rw-dsh-fixture-02
label: 研究设计与方法检查
entry_skill: rw-research-referee
downstream_skills:
  - rw-research-design
  - rw-statistics-audit
tools:
  - skill
expects_stage_gate: true
---

# 输入

把下面这句原样发给 DSH：

```text
我打算做一个单中心前后对照，比较交接班清单上线前后 6 个月的用药差错率，样本大概每组 400 人次。帮我审这个设计：结论要成立需要哪些证据，哪些偏倚会先杀掉它，统计上按人次算还是按患者算。
```

# 期望的可观察结果

- 入口 Skill 是 `rw-research-referee`。
- 下游至少加载 `rw-research-design` 或 `rw-statistics-audit`。
- 产出里明确点出分析单位问题（人次 vs 患者）和前后对照的历史性偏倚。
- 这条 fixture 用来看阶段门：如果 DSH 在继续之前问了确认，`approval/asked` 和
  `approval/decided` 应该出现在 recorder 日志里。没有阶段门也不算失败，
  但记录里要写清楚这次没触发。

# 记录

同 fixture 01，写进 `run_records/rw-dsh-fixture-02.json`。
