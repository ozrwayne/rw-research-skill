# 证据凭据结构来源

## W3C PROV

- W3C, *PROV-DM: The PROV Data Model*, 2013：provenance 记录实体、活动、责任主体、派生、集合和失效。https://www.w3.org/TR/prov-dm/
- W3C, *Constraints of the PROV Data Model*, 2013：用唯一性、事件顺序、不可能模式和类型约束检查 provenance 记录的一致性。https://www.w3.org/TR/prov-constraints/

本 Skill 对应使用：稳定 ID、来源实体、依赖关系、失效传播、审计记录和一致性检查。

## W3C Verifiable Credentials Data Model 2.0

- W3C, *Verifiable Credentials Data Model v2.0*, Recommendation, 2025：区分 claims、evidence、status、schema、issuer 和 verifier；并明确凭据可验证不等于其中主张为真。https://www.w3.org/TR/vc-data-model-2.0/

本 Skill 对应使用：凭据状态、支持证据、schema 和验证者规则。当前实现没有数字签名、issuer／holder／verifier 交换协议，也不宣称符合 W3C VC。

## RO-Crate

- Research Object Crate community, *RO-Crate Metadata Specification 1.2*, 2025：用稳定实体 ID、交叉引用、根数据实体和 provenance 描述聚合研究对象。https://www.researchobject.org/ro-crate/specification/1.2/

本 Skill 对应使用：根来源、子实体、扁平引用和研究材料聚合。当前 JSON 结构不是 RO-Crate JSON-LD，也不宣称符合 RO-Crate。

## 证据边界

这些标准支持来源、关系、状态和验证结构，不证明模型已经正确理解论文。图表语义、统计解释和审稿判断仍需领域规则、跨位置核对和人工复核。
