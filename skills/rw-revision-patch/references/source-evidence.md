# 来源证据

- Revision Patch 保留作者判断和未涉及内容，减少无关重写。
- 稳定块 ID、hash 和 apply report 用于限制修改范围。
- 当前实现把范围收窄到 Markdown replace，以便验证修改边界。

## v2 更新

v1 原有替换契约保持；v2 增加明确批准的普通段落整块删除。删除标题或重排章节仍走结构修订。详细契约见 `references/patch-format.md`。
