---
id: rw-dsh-fixture-03
label: 学术写作、引用与交付门控
entry_skill: rw-phd-write
downstream_skills:
  - rw-revision-patch
  - rw-journal-submission
tools:
  - skill
  - mcp__rwfixture__echo_claim
expects_stage_gate: true
---

# 输入

把下面这段原样发给 DSH：

```text
这段是我 discussion 的开头：

「本研究显示交接班清单显著降低了用药差错率，说明标准化交接是提升患者安全的有效手段。」

我只想改这一句，其他段落别动。改完告诉我这句在投稿前还缺哪些证据。
```

# 期望的可观察结果

- 入口 Skill 是 `rw-phd-write`。
- 下游至少加载 `rw-revision-patch`（只改指定块）。
- 产出指出「显著」和「有效手段」这两处主张超出单中心前后对照能支持的范围。
- 只替换被批准的块，不重写整段。这是交付门控：没有批准就不该落改动。

# 记录

同 fixture 01，写进 `run_records/rw-dsh-fixture-03.json`。
