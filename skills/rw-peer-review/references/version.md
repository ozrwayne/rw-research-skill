# 版本

当前版本：`v0.9.2`。

范围：独立 `rw-peer-review`。没有合并到主线 `release/rwskill/`。

## v0.9.2 更新

- 修复 Context Pack 投影、闭包、来源文件和预算的重验；空记录不再误报完成。
- 绑定当前 Finding 内容与裁决凭据；检查替代谱系、不同 Agent 共识和独立学习案例。
- 拒绝歧义 JSON、非有限数和错误数据类型；迭代遍历长依赖图。
- 新增临时合成负向回归。此版本是本次本地审计修复，发布状态以最终部署核验为准。

## v0.9.1 更新

- 增加内部 Judgment Learning 旁车，分开记录问题图、用户初判、最强质疑、最强回应、核对和终判。
- 增加零经验引导、合成基线题、worked example、Review Quality Instrument 质量检查和外部预设 mastery 标准。
- 增加 Evidence Credential Store。凭据总数量不设上限，数量由材料和提取粒度决定。
- 增加来源、页面、章节、段落、图表、caption、legend、footnote、方法定义、结果和 Supplement 的层级、依赖、状态与 hash。
- 增加来源文件 SHA-256、失效传播、批量导入、循环依赖和跨来源层级检查。
- 增加 Paper Context Pack。单次模型上下文按必要依赖闭包、父节点和相邻文字选择，并使用可配置的凭据数量与 token 预算。
- Review Ledger 的 Finding 增加可选 `evidence_credential_ids` 和 `context_pack_id`，Review Credential 保存对应快照。

## 状态

- 本地结构、脚本、隐私和回归检查通过。
- 尚未提交、推送或发布。
- 结构检查通过不表示图表解释、统计判断或稿件质量正确。
