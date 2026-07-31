# 可选工具登记表

`rw-research-lab-router` 可以读取用户提供的 CSV 工具登记表，但不要求私人 Research Lab 存在。

```bash
python3 scripts/read_tool_registry.py \
  --path /path/to/tool-registry.csv \
  --as-of 2026-07-31
```

读取结果保留工具名称、版本、许可证、运行环境、最后测试日期、测试级别、测试结果、对应 RW Skill 和来源。`CURRENT`、`STALE` 和 `UNKNOWN` 只描述登记日期与读取日期的关系，不证明工具当前可运行。

登记表与源码、README 或实际测试不一致时，分别保存两组事实，交给人工复核。不要把登记表复制进公开包，也不要把私人路径、研究材料或凭证写入 Skill 输出。
