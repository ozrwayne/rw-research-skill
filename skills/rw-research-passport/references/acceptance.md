# 验收

- `SKILL.md` 包含 `name`、`description`，并允许包内使用的 `metadata.internal`。
- 至少 13 条知识原子、8 条公理和 6 个行为测试。
- `passport.py init` 能创建有效 JSON。
- `add-material` 能增加材料并保留审计记录。
- `record-credential` 能同时增加判断、Credential 和审计记录。
- `validate` 能发现重复 ID、无效状态、不存在的引用和被修改的 Credential。
- 输出区分材料状态、判断、Credential、未知项和交接。
- 原始材料不被复制或修改。

- `python3 -m unittest discover -s scripts -p "test_passport*.py"` 通过，覆盖负向凭据、废止传播和并发写入。
- 文本 JSON 结构通过不等于当前研究决定正确或已取得所需人类确认。

静态结构检查、确定性脚本测试和模型行为验证分别记录。合同数量或 self_check 通过不表示合同已由模型执行；缺少运行记录的合同保持未执行状态。
