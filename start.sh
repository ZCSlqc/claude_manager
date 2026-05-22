#!/usr/bin/env bash
set -euo pipefail

ROOT="$PWD"

# ==================== PID 配置 ====================
PID_DIR="$ROOT/tmp"
mkdir -p "$PID_DIR"

PID_BACKEND="$PID_DIR/claude_manager_backend.pid"
PID_FRONTEND="$PID_DIR/claude_manager_frontend.pid"

VENV="$ROOT/.venv"

# ==================== 停止旧进程 ====================
echo "🔪 停止旧服务进程…"

if [ -f "$PID_BACKEND" ]; then
    kill -9 "$(cat "$PID_BACKEND")" 2>/dev/null || true
    rm -f "$PID_BACKEND"
fi

if [ -f "$PID_FRONTEND" ]; then
    kill -9 "$(cat "$PID_FRONTEND")" 2>/dev/null || true
    rm -f "$PID_FRONTEND"
fi

sleep 1

# ==================== 启动后端 ====================
cd backend
nohup "$VENV/bin/python3" -m uvicorn server:app --host 0.0.0.0 --port 8112 > /dev/null 2>&1 &
PID_BE=$!
echo "$PID_BE" > "$PID_BACKEND"
cd ..
sleep 2

curl -sf http://127.0.0.1:8112/health > /dev/null || {
    echo "❌ 后端启动失败"
    exit 1
}
echo "✅ 后端启动成功 PID: $PID_BE"

# ==================== 启动前端 ====================
cd frontend
nohup npx vite --host 0.0.0.0 --port 3112 > /dev/null 2>&1 &
PID_FE=$!
echo "$PID_FE" > "$PID_FRONTEND"
cd ..
sleep 2

curl -sf http://localhost:3112 > /dev/null || {
    echo "❌ 前端启动失败"
    exit 1
}
echo "✅ 前端启动成功 PID: $PID_FE"

# ==================== 完成 ====================
echo -e "\n🚀 Claude Manager 启动完成"
echo "   前端: http://localhost:3112"
echo "   后端: http://localhost:8112"
