#!/usr/bin/env bash
# 在 tmux 会话内启动前端（绑定 0.0.0.0，方便端口转发）
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PATH="/home/ubuntu/.nvm/versions/node/v22.22.2/bin:/usr/local/bin:/usr/bin:/bin"
exec pnpm --dir frontend dev --host 0.0.0.0 --port 5173
