# Verdict 定义

- `VERIFIED`：来源原文在当前人群、时间、变量和强度下支持主张。
- `PARTIAL`：来源支持句子的一部分，或主张范围大于来源范围。
- `DISTORTED`：来源被夸大、反向、错误概括或改变了限定条件。
- `UNSUPPORTED`：来源中没有该信息，或来源设计不能支持该说法。
- `UNVERIFIABLE_ACCESS`：来源存在，但当前无法访问足够原文。
- `NOT_CHECKED`：尚未完成核验。
- `NOT_APPLICABLE`：该记录不是需要外部来源支持的事实性主张。

`VERIFIED`、`PARTIAL` 和 `DISTORTED` 必须保存至少一个来源对象。来源对象包括：

- `id`
- `source_pointer`
- `locator`
- `support_note`

不要把长篇原文复制进 Audit。保存短说明和可回到原文的位置。

## 来源版本绑定

支持性来源记录另存 `source_path` 和 `source_sha256`（64 位小写十六进制）。相对 `source_path` 以 Audit JSON 所在目录为基准；CLI 写入绝对路径。本地 `source_pointer` 自动固化文件 hash；远程指针需用 `--source-file` 指定已取得的原文快照。

`validate_audit(data, audit_path)` 重算文稿和已登记来源文件 hash，丢失或变化返回错误。`gate_status(data)` 仅做结构和处置判断；外部调用者必须先执行 `validate_audit`。旧版 VERIFIED 来源缺快照时保持 REVIEW，不因指针存在而宣告 PASS。NOT_APPLICABLE 必须在 notes 说明理由。快照 hash 不证明语义支持、来源身份或引用真实性。
