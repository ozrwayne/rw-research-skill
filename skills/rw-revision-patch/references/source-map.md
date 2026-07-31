# 方法来源

## 包内规则

- 2026-07-13：建立独立的 `RW Revision Patch`。
- 修改时保留作者判断和未涉及内容，不用整篇重写完成局部任务。
- 第一版只允许替换已有 Markdown 块。

## RW 系统关系

- `rw-academic-writing`：提供需要修改的论文段落和内容要求。
- `rw-phd-tone`：要求最小修改并保留作者语气。
- `rw-journal-submission`：提供审稿意见 ID 和修改位置。
- `rw-claim-audit`：复核修改后的事实性主张。

## 实现

- 块编号、hash precondition、整批检查和修改报告由随 Skill 提供的 Python 脚本实现。
- 第一版只支持 Markdown 块替换；新增、删除和重排章节另行确认。
