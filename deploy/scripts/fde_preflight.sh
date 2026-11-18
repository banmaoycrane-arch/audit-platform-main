#!/usr/bin/env bash
# FDE 本地化部署预检：审计平台健康 +（可选）Ollama 可达
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deploy/.env"

BACKEND_URL="${FDE_BACKEND_URL:-http://127.0.0.1:8000}"
OLLAMA_URL="${FDE_OLLAMA_URL:-}"

pass=0
fail=0

ok() { echo "[PASS] $*"; pass=$((pass + 1)); }
ng() { echo "[FAIL] $*"; fail=$((fail + 1)); }
info() { echo "[INFO] $*"; }

info "仓库根目录: ${REPO_ROOT}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Z_]+=' "${ENV_FILE}" | sed 's/^/export /') 2>/dev/null || true
  ok "找到 deploy/.env"
else
  ng "缺少 deploy/.env（请 cp deploy/.env.example deploy/.env 并填写 SECRET_KEY）"
fi

if command -v docker >/dev/null 2>&1; then
  if docker compose -f "${COMPOSE_FILE}" ps -q backend 2>/dev/null | grep -q .; then
    ok "backend 容器已在运行"
  else
    info "backend 容器未运行（本地开发可用 pnpm dev:backend）"
  fi
else
  info "未安装 docker，跳过容器检查"
fi

if curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1; then
  ok "后端健康检查 ${BACKEND_URL}/health"
else
  ng "无法访问 ${BACKEND_URL}/health"
fi

if [[ -z "${OLLAMA_URL}" ]]; then
  if [[ -n "${AI_LOCAL_BASE_URL:-}" ]]; then
    OLLAMA_URL="${AI_LOCAL_BASE_URL}"
  elif [[ -n "${AI_BASE_URL:-}" ]]; then
    OLLAMA_URL="${AI_BASE_URL}"
  else
    OLLAMA_URL="http://127.0.0.1:11434/v1"
  fi
fi

OLLAMA_ROOT="${OLLAMA_URL%/}"
OLLAMA_ROOT="${OLLAMA_ROOT%/v1}"

if curl -sf "${OLLAMA_ROOT}/api/tags" >/dev/null 2>&1; then
  ok "Ollama 探活 ${OLLAMA_ROOT}/api/tags"
else
  ng "Ollama 不可达（检查 ${OLLAMA_ROOT} 或设置 FDE_OLLAMA_URL）"
fi

if [[ -d "${REPO_ROOT}/qdrant_local_storage" ]] || [[ -n "${QDRANT_LOCAL_PATH:-}" ]]; then
  ok "本地向量存储路径已配置或可写"
else
  info "开发环境默认 qdrant_local_storage；生产应在 Docker 卷 /data/qdrant"
fi

echo "----------------------------------------"
echo "合计 PASS=${pass} FAIL=${fail}"
if [[ "${fail}" -gt 0 ]]; then
  exit 1
fi
echo "FDE 预检通过"
exit 0