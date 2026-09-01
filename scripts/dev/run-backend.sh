#!/usr/bin/env bash
# 在 tmux 会话内启动后端（PATH 写死，避免 login shell 丢命令）
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PATH="/workspace/.venv/bin:/home/ubuntu/.nvm/versions/node/v22.22.2/bin:/usr/local/bin:/usr/bin:/bin"
if [ ! -f backend/.env ]; then
  cat > backend/.env <<'ENV'
SECRET_KEY=local-dev-secret-key-change-me-not-for-prod
SMS_RETURN_CODE_IN_DEV=true
CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
ENV
fi
exec pnpm dev:backend
