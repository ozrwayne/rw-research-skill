# 验收

- `SKILL.md` 保留 `name`、`description`；内部模块可带 `metadata.internal`。
- 至少 10 条知识原子、5 条公理和 3 个行为测试。
- 每条 claim 有稳定 ID、文稿位置、类型和 verdict。
- `VERIFIED` 必须有来源、locator 和 support note。
- `validate` 能发现重复 ID、无效 verdict 和缺失定位。
- `gate` 对 PASS、REVIEW 和 BLOCK 使用不同退出码。
- 脚本不自动把来源存在写成主张已验证。

- 来源文件变化或丢失会阻断；无 hash 的旧 VERIFIED 记录不返回 PASS。
- 主张原文、文稿位置非空；NOT_APPLICABLE 有说明；重复来源 ID、重复 JSON 键和非有限数被拒绝。

静态结构检查、确定性脚本测试和模型行为验证分别记录。合同数量或 self_check 通过不表示合同已由模型执行；缺少运行记录的合同保持未执行状态。
