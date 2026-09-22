---
name: rw-dsh-fixture-echo
description: |
  DSH 适配的结构测试用 Skill，不是 RW 的研究能力。测试会改这里的正文，
  再让 DSH 重新加载一次，验证 DSH 读的是主来源而不是副本。
---

# rw-dsh-fixture-echo

RW_FIXTURE_BODY_MARKER=baseline

这一行下面的内容会被 `tests/probe_dsh.mjs` 临时改写再改回来。
不要把这个 Skill 放进 `skills/`，它不属于 RW 的 22 个 Skill。
