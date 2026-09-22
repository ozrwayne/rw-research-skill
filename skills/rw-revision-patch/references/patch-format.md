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
