#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"
BACKEND="$ROOT/backend"

echo "=== Claude Manager 初始化 ==="

# 0. 检查/安装 uv
if ! command -v uv &>/dev/null; then
    echo "[0/6] 安装 uv..."
    pip install -q uv
fi

# 1. 后端 venv
if [ -d "$VENV" ]; then
    echo "[1/6] venv 已存在，跳过创建"
else
    echo "[1/6] 创建 Python venv..."
    python3 -m venv "$VENV"
fi

# 2. 安装后端依赖
if [ -f "$BACKEND/pyproject.toml" ]; then
    echo "[2/6] 安装后端依赖 (via pyproject.toml)..."
    cd "$BACKEND" && "$VENV/bin/uv" pip install -q .
else
    echo "[2/6] 安装后端依赖..."
    "$VENV/bin/pip" install -q fastapi uvicorn httpx loguru
fi

# 3. 前端依赖
if [ -d "$FRONTEND/node_modules" ]; then
    echo "[3/6] 前端依赖已存在，跳过安装"
else
    echo "[3/6] 安装前端依赖..."
    cd "$FRONTEND" && npm install
fi

# 4. 生成头像
echo "[4/6] 生成头像..."
cd "$BACKEND" && "$VENV/bin/python3" generate_avatars.py

# 5. 前端构建
echo "[5/6] 构建前端..."
cd "$FRONTEND" && npx vite build

# 6. 清理缓存
echo "[6/6] 清理缓存..."
find "$BACKEND" -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "=== 初始化完成 ==="
echo "  启动服务: bash $ROOT/start.sh"
