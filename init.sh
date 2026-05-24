#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"

echo "=== Claude Manager 初始化 ==="

# 1. 后端 venv
if [ -d "$VENV" ]; then
    echo "[1/5] venv 已存在，跳过创建"
else
    echo "[1/5] 创建 Python venv..."
    python3 -m venv "$VENV"
fi

echo "[2/5] 安装后端依赖..."
"$VENV/bin/pip" install -q fastapi uvicorn httpx loguru

# 2. 前端依赖
if [ -d "$FRONTEND/node_modules" ]; then
    echo "[3/5] 前端依赖已存在，跳过安装"
else
    echo "[3/5] 安装前端依赖..."
    cd "$FRONTEND" && npm install
fi

# 3. 生成头像
echo "[4/5] 生成头像..."
cd "$ROOT/backend" && "$VENV/bin/python3" generate_avatars.py

# 4. 前端构建
echo "[5/5] 构建前端..."
cd "$FRONTEND" && npx vite build

echo ""
echo "=== 初始化完成 ==="
echo "  启动服务: bash $ROOT/start.sh"
