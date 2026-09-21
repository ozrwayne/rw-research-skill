# 验收

- `VERSION` 可直接读取，`references/version.md` 说明当前版本更新。
- `SKILL.md` 保留 `name`、`description`；内部模块可带 `metadata.internal`。
- 至少 10 条知识原子、5 条公理和 3 个行为测试。
- 每条意见有稳定 ID、稿件位置、原文、问题、改法、录用影响、状态和证据。
- 状态不是 `open` 时必须有下场说明；`withdrawn` 必须连接至少一个来源。
- 意见的提出者必须是已登记 Agent。
- `validate` 能发现重复 ID、无效状态、悬空来源和被改动的凭据。
- `gate` 对 PASS、REVIEW 和 BLOCK 使用不同退出码。
- 脚本不把意见数量或分数写成稿件质量结论。
- 判断学习使用独立旁车文件，不改变旧版 `review-ledger.json` 的读取和 Gate。
- 判断旁车进入综合前必须有问题图、用户初判、最强质疑、最强回应、五项核对和用户终判。
- “回应提到、命中、成立、正文仍需补报”使用四个独立字段。
- 回应成立但正文仍需补报时，不能使用 `answered` 或 `withdrawn` 处置。
- 对外交付前必须确认内部字段已排除并通过干净度检查。
- `mode=off` 返回 REVIEW，不把显式跳过写成学习 PASS。
- 旧版 Review Ledger 单元测试和判断旁车单元测试都通过。
- 零经验用户进入 `guided`，先做合成基线题，再看不同合成案例的 worked example。
- `guided` 的当前 Finding 必须完成 9 项引导审稿卡后才能进入综合。
- 反馈只指出漏证据、推断越界、严重程度和修改可执行性，不直接替换用户终判。
- `ready` 与 `mastery` 分开；交付完成不能自动写成掌握。
- `mastery` 不使用自定的分钟数或案例数；必须记录评定标准、来源、要求的独立案例数和评定人。
- 7 项 Review Quality Instrument 核心维度达到预设标准、无 critical miss、独立案例满足标准且评定人确认后，`mastery` 才可 PASS。
- Evidence Credential Store 能校验稳定 ID、来源、层级、必要依赖、状态、hash、悬空引用和循环依赖。
- 根来源只有在必要页面、章节和视觉凭据全部为 `verified` 后才可通过覆盖门。
- 根来源保存文件 SHA-256；当前文件 hash 变化时覆盖门和 Context Pack 都返回 BLOCK。
- `stale`、`superseded`、`revoked` 或 `needs_input` 的必要凭据阻断 Context Pack。
- Paper Context Pack 计算必要依赖闭包并加入父节点和相邻文字；超过上限时 BLOCK，不截断。
- Context Pack 的保守 token 上限超过预算时 BLOCK，不截断必要证据。
- Finding 的 `evidence_credential_ids` 与 `context_pack_id` 成对出现，Review Credential snapshot 保留两者。
- `validate-ledger` 能发现缺失、失效、hash 改变或 Finding 不匹配的 Context Pack。
- Evidence Credential Store 不设置凭据总数量上限；数量由材料和提取粒度决定。
- 大批凭据导入后，单条 Finding 的 Context Pack 仍只包含其必要依赖、父节点和相邻文字。
- 证据凭据 Gate PASS 不写成图表解释、统计判断或稿件质量已经正确。

- 负向回归覆盖重新哈希的伪造 Pack、缺失依赖、删来源、当前源文件变化、重复 Pack ID、空台账、跨 Finding 凭据和陈旧裁决。
- 独立案例重复不计为掌握；单 Agent 不构成 agent_consensus。
- 所有测试只用临时合成材料，不调用模型。

静态结构检查、确定性脚本测试和模型行为验证分别记录。合同数量或 self_check 通过不表示合同已由模型执行；缺少运行记录的合同保持未执行状态。
