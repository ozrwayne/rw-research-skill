# Patch JSON

```json
{
  "schema_version": "rw-revision-patch/v1",
  "base_document_hash": "manifest 中的 hash",
  "operations": [
    {
      "op": "replace",
      "block_id": "B0002",
      "expected_hash": "旧块 hash",
      "new_text": "替换后的完整块正文",
      "reason": "为什么修改",
      "issue_ids": ["REV-001"]
    }
  ]
}
```

规则：

- `base_document_hash` 必须与 anchored 文稿一致。
- 每个 `block_id` 只能出现一次。
- `expected_hash` 来自 manifest。
- `new_text` 是完整替换块，不是搜索替换片段。
- `reason` 不能为空。
- `issue_ids` 必须是非空字符串数组；无审稿编号的修改使用本次确认的本地修改编号。

## 应用确认

`check` 输出 `patch_sha256`。展示整个 Patch 和修改范围并取得批准后，将对应的完整 SHA-256 传给 `apply --confirm-patch-sha256`。Patch 任一字节变化都需重新确认。该参数绑定批准版本，不认证操作者身份；调用方负责取得实际用户批准。

输入、manifest、patch、output、report 的路径及文件别名必须分离，`--force` 不豁免原稿保护。manifest 的 source_path 也受保护。

## v2 显式删除

```json
{
  "schema_version": "rw-revision-patch/v2",
  "base_document_hash": "manifest 中的 hash",
  "operations": [{
    "op": "delete",
    "block_id": "B0002",
    "expected_hash": "旧块 hash",
    "reason": "该段内容已由 B0001 完整承担；删除后的上下文已复核",
    "issue_ids": ["REV-002"]
  }]
}
```

- `delete` 必须省略 `new_text`，即使 null 或空字符串也拒绝。`replace` 仍要求非空正文；v1 不接受 delete。
- 删除整块 marker 和其后的正文跨度，保留前言及其他块的字节、ID 和顺序，不重新编号。
- v2 可混合 replace 与 delete，每块仍只允许一个操作。删掉的块同样计入 60% 修改范围门。
- 保守拒绝含 ATX／Setext 标题形态或水平分隔线的块（含代码中类似行）；此类边界先做结构审阅，不尝试自动猜测。拒绝删光所有块。
- 保留来源、文稿、manifest、补丁 hash、用户批准和全批验证门；删除无需替代文字。
- v2 报告标记 `op`，删除的 `new_hash` 为 null，并报告 `deleted_blocks` 与 `remaining_blocks`。这些数量不证明论证完整。
- 输出文稿后重新 anchor 到新的 manifest，才继续下一批修改；旧 manifest 对新文稿应报过期。
- 合并跨块内容时批准整个 replace + delete 组合，检查残留引用和逻辑连接。工具不自动证明删除合理。
