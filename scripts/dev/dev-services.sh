#!/usr/bin/env bash
# 本地前后端服务控制：start | stop | restart | status | open | start-open
# 用法：
#   ./scripts/dev/dev-services.sh start
#   ./scripts/dev/dev-services.sh restart
#   ./scripts/dev/dev-services.sh status

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TMUX_CFG="/exec-daemon/tmux.portal.conf"
BACKEND_SESSION="dev-backend"
FRONTEND_SESSION="dev-frontend"
BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:5173"
RUN_BACKEND="$ROOT/scripts/dev/run-backend.sh"
RUN_FRONTEND="$ROOT/scripts/dev/run-frontend.sh"

tmux_has() {
  tmux -f "$TMUX_CFG" has-session -t "=$1" 2>/dev/null
}

tmux_kill() {
  if tmux_has "$1"; then
    tmux -f "$TMUX_CFG" kill-session -t "$1" 2>/dev/null || true
  fi
}

free_port() {
  local port="$1"
  local pids
  pids="$(python3 - "$port" <<'PY'
import glob
import os
import sys

port = int(sys.argv[1])
want = f"{port:04X}"
inodes = set()
for tcp in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        lines = open(tcp, encoding="utf-8").read().splitlines()[1:]
    except OSError:
        continue
    for line in lines:
        parts = line.split()
        if len(parts) < 10:
            continue
        local, state, inode = parts[1], parts[3], parts[9]
        if state == "0A" and local.split(":")[-1].upper() == want:
            inodes.add(inode)
pids = set()
for fd in glob.glob("/proc/[0-9]*/fd/[0-9]*"):
    try:
        target = os.readlink(fd)
    except OSError:
        continue
    if target.startswith("socket:[") and target[8:-1] in inodes:
        pids.add(fd.split("/")[2])
print(" ".join(sorted(pids)))
PY
)"
  if [ -n "$pids" ]; then
    echo "[info] 释放端口 $port: $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

http_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$1" 2>/dev/null || echo 000
}

start_backend() {
  if [ "$(http_code "$BACKEND_URL/health")" = "200" ]; then
    echo "[ok] 后端已在运行: $BACKEND_URL/health"
    return 0
  fi
  free_port 8000
  tmux_kill "$BACKEND_SESSION"
  tmux -f "$TMUX_CFG" new-session -d -s "$BACKEND_SESSION" -c "$ROOT" -- bash -l
  tmux -f "$TMUX_CFG" send-keys -t "$BACKEND_SESSION:0.0" "$RUN_BACKEND" C-m
  echo "[..] 正在启动后端..."
  local i
  for i in $(seq 1 40); do
    if [ "$(http_code "$BACKEND_URL/health")" = "200" ]; then
      echo "[ok] 后端就绪: $BACKEND_URL  (health=200)"
      return 0
    fi
    sleep 1
  done
  echo "[err] 后端启动超时，请看: tmux -f $TMUX_CFG attach -t $BACKEND_SESSION"
  return 1
}

start_frontend() {
  if [ "$(http_code "$FRONTEND_URL/")" = "200" ]; then
    echo "[ok] 前端已在运行: $FRONTEND_URL"
    return 0
  fi
  free_port 5173
  tmux_kill "$FRONTEND_SESSION"
  tmux -f "$TMUX_CFG" new-session -d -s "$FRONTEND_SESSION" -c "$ROOT" -- bash -l
  tmux -f "$TMUX_CFG" send-keys -t "$FRONTEND_SESSION:0.0" "$RUN_FRONTEND" C-m
  echo "[..] 正在启动前端..."
  local i
  for i in $(seq 1 50); do
    if [ "$(http_code "$FRONTEND_URL/")" = "200" ]; then
      echo "[ok] 前端就绪: $FRONTEND_URL"
      return 0
    fi
    sleep 1
  done
  echo "[err] 前端启动超时，请看: tmux -f $TMUX_CFG attach -t $FRONTEND_SESSION"
  return 1
}

stop_all() {
  echo "[..] 停止前后端..."
  tmux_kill "$FRONTEND_SESSION"
  tmux_kill "$BACKEND_SESSION"
  free_port 5173
  free_port 8000
  echo "[ok] 已停止"
}

status_all() {
  local bh fh
  bh="$(http_code "$BACKEND_URL/health")"
  fh="$(http_code "$FRONTEND_URL/")"
  echo "后端  $BACKEND_URL/health  -> HTTP $bh"
  echo "前端  $FRONTEND_URL/         -> HTTP $fh"
  if tmux_has "$BACKEND_SESSION"; then echo "tmux  $BACKEND_SESSION: 存在"; else echo "tmux  $BACKEND_SESSION: 无"; fi
  if tmux_has "$FRONTEND_SESSION"; then echo "tmux  $FRONTEND_SESSION: 存在"; else echo "tmux  $FRONTEND_SESSION: 无"; fi
  if [ "$bh" = "200" ] && [ "$fh" = "200" ]; then
    echo "[ok] 两边都正常，可打开 $FRONTEND_URL/login"
    return 0
  fi
  echo "[warn] 有服务未就绪，可执行: $0 restart"
  return 1
}

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL/login" >/dev/null 2>&1 || true
  elif command -v google-chrome >/dev/null 2>&1; then
    google-chrome --new-window "$FRONTEND_URL/login" >/dev/null 2>&1 || true
  else
    echo "请手动打开: $FRONTEND_URL/login"
  fi
}

cmd="${1:-status}"
case "$cmd" in
  start)
    start_backend
    start_frontend
    status_all || true
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    sleep 1
    start_backend
    start_frontend
    status_all || true
    ;;
  status)
    status_all
    ;;
  open)
    open_browser
    status_all || true
    ;;
  start-open)
    start_backend
    start_frontend
    open_browser
    status_all || true
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status|open|start-open}"
    exit 2
    ;;
esac
