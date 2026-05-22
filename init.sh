#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"

echo "=== Claude Manager 初始化 ==="

[ -d "$VENV" ] || { echo "[1/3] 创建 Python venv..."; python3 -m venv "$VENV"; }

echo "[2/3] 安装后端依赖..."
"$VENV/bin/pip" install -q fastapi uvicorn httpx loguru

echo "[3/3] 生成头像..."
cd "$ROOT/frontend/src/assets" && "$VENV/bin/python3" generate_avatars.py

echo "=== 初始化完成 ==="
