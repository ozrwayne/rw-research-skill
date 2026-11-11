# Cross-model evaluation

这里保存 RW Research Skill 的跨模型评测工具和合成评测记录。

- `protocol.md`：范围、门槛和证据边界。
- `document-review-protocol.md`：真实文档审阅和 provider 平衡规则。
- `models.json`：模型入口。
- `development-fixtures-v1.json`：第一次完整运行使用的开发任务。
- `fixtures.json`：第 2 组任务。
- `results/`：完整模型输出、判分和摘要。

检查任务和模型配置：

```bash
python3 scripts/cross_model_eval.py check
```

运行需要本机已有 Codex 和 Claude 登录状态。每个任务会分别运行带 Skill 和不带 Skill 条件。运行 ID 不能覆盖。

```bash
python3 scripts/cross_model_eval.py run \
  --run-id YYYY-MM-DD-cross-model \
  --repetitions 1 \
  --workers 4
```

CI 只检查评测定义和确定性工具，不发起付费模型调用。

运行前检查本机 CLI 和登录状态：

```bash
python3 scripts/cross_model_review.py preflight
```

Claude Desktop 和 Claude CLI 的登录状态可能不同。如果结果显示 Claude CLI 没有登录，运行一次 `claude auth login`，按 Claude 订阅账号完成登录。这个流程不要求在项目中保存 API key。

## 当前本地模型表

- Codex `gpt-5.6-sol`；
- Codex `gpt-5.6-terra`；
- Codex `gpt-5.6-luna`；
- Claude `claude-opus-4-8`。

Codex 使用本机 Codex CLI 登录状态。Claude 使用本机 Claude CLI 登录状态。脚本不要求用户在项目中写入 API key。

历史结果目录保存每次运行当时的模型表和 hash。修改 `models.json` 不会改变旧结果代表的模型。

## 真实文档审阅

真实文档审阅与合成评测分开。它接受 `.md`、`.txt` 和 `.docx`，默认加载 `rw-research-referee`、`rw-phd-write` 和 `rw-phd-tone`。输出目录必须在这个公开仓库之外。

```bash
python3 scripts/cross_model_review.py run \
  --document /path/to/chapter1.docx \
  --brief /path/to/review-brief.md \
  --output-dir /path/to/private-review-records \
  --run-id chapter1-2026-07-20
```

也可以用 `--task` 直接传入短任务，或重复使用 `--skill` 和 `--model` 选择 Skill 与模型。只选 1 家 provider 时，必须显式加入 `--allow-single-provider`。

汇总分成 3 类：

- `cross-provider findings`：至少 1 个 Codex 模型和 Claude 锚定到相同原文；
- `Codex-family findings`：至少 2 个 Codex 模型锚定到相同原文，但 Claude 没有锚定该处；
- `model-specific findings`：只由 1 个模型提出。

脚本不把 3 个 Codex 模型当成 3 票。它也不判断哪个模型正确。用户需要回到原文、来源和导师意见决定是否修改。
