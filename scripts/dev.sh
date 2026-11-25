#!/usr/bin/env bash
# 一键起「后端 API + 前端 dev」。仅用于本地开发。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
export PYTHONPATH="src:."

if ! command -v pnpm >/dev/null 2>&1; then
  echo "缺少 pnpm：请先安装 Node 20+ 与 pnpm，并在 frontend/ 执行 pnpm install" >&2
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  echo "frontend/node_modules 不存在：请先 cd frontend && pnpm install" >&2
  exit 1
fi

python3 -c "import alembic, fastapi" 2>/dev/null || {
  echo "缺少 Python 依赖：请先 python3 -m pip install -e '.[dev]'" >&2
  exit 1
}

python3 - <<'PY' || exit 1
import sqlite3
from pathlib import Path
db = Path("storage/shoppivot.db")
if not db.is_file():
    print("storage/shoppivot.db 不存在，先执行 make seed", flush=True)
    raise SystemExit(1)
PY

echo "启动 API  http://127.0.0.1:${API_PORT}"
python3 -m uvicorn bootstrap.api:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
cleanup() {
  kill "$API_PID" 2>/dev/null || true
  wait "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${API_PORT}/api/v1/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if ! curl -sf "http://127.0.0.1:${API_PORT}/api/v1/healthz" >/dev/null 2>&1; then
  echo "API 启动失败：请查看上面的日志（端口 ${API_PORT} 是否被占用）" >&2
  exit 1
fi
echo "API 就绪；启动前端 http://127.0.0.1:${WEB_PORT}"
cd frontend
VITE_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}" pnpm dev --port "$WEB_PORT"
