# 验收

- `SKILL.md` 前置字段只有 `name` 和 `description`。
- 至少 13 条知识原子、8 条公理和 6 个行为测试。
- `passport.py init` 能创建有效 JSON。
- `add-material` 能增加材料并保留审计记录。
- `record-credential` 能同时增加判断、Credential 和审计记录。
- `validate` 能发现重复 ID、无效状态、不存在的引用和被修改的 Credential。
- 输出区分材料状态、判断、Credential、未知项和交接。
- 原始材料不被复制或修改。
