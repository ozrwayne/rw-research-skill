#!/usr/bin/env bash
# 用 DSH headless profile 跑一次 RW 研究任务。
#
#   adapters/dsh/scripts/rw-dsh-headless.sh "帮我把这个研究问题拆成检索式"
#
# 需要本机已经装好 dsh 并完成模型登录或配置。凭据不经过这个脚本。
set -euo pipefail

ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$#" -lt 1 ]; then
  echo "用法: $(basename "$0") \"研究任务\"" >&2
  exit 2
fi

DSH_BIN="${RW_DSH_BIN:-dsh}"
if ! command -v "$DSH_BIN" >/dev/null 2>&1; then
  echo "找不到 $DSH_BIN。装一个：npm i -g @deepseek-ai/dsh@next，或设 RW_DSH_BIN。" >&2
  exit 127
fi

PATCH_FILE="$(mktemp -t rw-dsh-patch.XXXXXX).yml"
trap 'rm -f "$PATCH_FILE"' EXIT

PATCH_ARGS=(--out "$PATCH_FILE")
if [ -n "${RW_DSH_WITH_MCP:-}" ]; then
  PATCH_ARGS+=(--with-mcp "$RW_DSH_WITH_MCP")
fi
python3 "$ADAPTER_DIR/scripts/rw_dsh_patch.py" "${PATCH_ARGS[@]}"

exec "$DSH_BIN" --profile headless --patch "$PATCH_FILE" "$@"
