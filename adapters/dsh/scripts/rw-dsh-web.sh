#!/usr/bin/env bash
# 用 DSH web profile 起一个带 RW Skill 的界面。
#
#   adapters/dsh/scripts/rw-dsh-web.sh
#   adapters/dsh/scripts/rw-dsh-web.sh --port 8080
#
# 补丁在这里生成的临时文件里，退出时删掉。绝对路径不进仓库。
#
# 注意：web profile 里 DSH 自带的 skill-filesystem 行被 web-app bundle 关掉了，
# 本机发现由 agent preset 负责。这个补丁插的是宿主全局层的独立 provider，
# 它的 catalog 会并进每个 agent 的 scope，所以两种 profile 用同一份补丁。
set -euo pipefail

ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

exec "$DSH_BIN" --profile web --patch "$PATCH_FILE" "$@"
