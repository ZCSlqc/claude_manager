#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"
BACKEND="$ROOT/backend"

# ============ 颜色输出 ============
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; }

# ============ 检查/安装 uv ============
if ! command -v uv &>/dev/null; then
    echo "[0/8] 安装 uv..."
    pip install -q uv
    ok "uv 安装完成"
else
    ok "uv 已安装 $(uv --version)"
fi

# ============ 检查 Python ============
if ! command -v python3 &>/dev/null; then
    err "python3 未安装，请先安装 Python >= 3.10"
    exit 1
fi
ok "Python $(python3 --version)"

# ============ 检查 Node.js ============
if ! command -v node &>/dev/null; then
    err "node 未安装，请先安装 Node.js >= 18"
    exit 1
fi
ok "Node.js $(node --version)"

# ============ 检查 claude CLI ============
if ! command -v claude &>/dev/null; then
    warn "claude CLI 未安装，前端运行不受影响，但无法执行任务"
fi
ok "claude CLI 已就绪 $(claude --version 2>/dev/null || echo '')"

# ============ 后端 venv ============
echo ""
echo "=== 后端 ==="
if [ -d "$VENV" ] && [ -f "$VENV/bin/python3" ]; then
    ok "venv 已存在"
else
    echo "[1/5] 创建 Python venv..."
    python3 -m venv "$VENV"
    ok "venv 创建完成"
fi

# ============ 安装后端依赖 ============
if [ -f "$BACKEND/pyproject.toml" ]; then
    echo "[2/5] 安装后端依赖 (via pyproject.toml)..."
    cd "$BACKEND" && "$VENV/bin/uv" pip install -q .
    ok "后端依赖安装完成"
else
    echo "[2/5] 安装后端依赖..."
    "$VENV/bin/pip" install -q fastapi uvicorn httpx loguru
    ok "后端依赖安装完成"
fi

# ============ 前端依赖 ============
echo ""
echo "=== 前端 ==="
if [ -d "$FRONTEND/node_modules" ]; then
    ok "前端依赖已存在"
else
    echo "[3/5] 安装前端依赖..."
    cd "$FRONTEND" && npm install
    ok "前端依赖安装完成"
fi

# ============ 生成头像 ============
echo "[4/5] 生成头像..."
cd "$BACKEND" && "$VENV/bin/python3" generate_avatars.py
ok "头像生成完成"

# ============ 前端构建 ============
echo "[5/5] 构建前端..."
cd "$FRONTEND" && npx vite build
ok "前端构建完成"

# ============ 清理缓存 ============
echo ""
echo "=== 清理 ==="
echo "[6/6] 清理 __pycache__..."
find "$BACKEND" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
ok "清理完成"

# ============ 完成 ============
echo ""
echo "==================================="
echo -e "${GREEN}✓ 初始化完成${NC}"
echo "==================================="
echo ""
echo "  启动服务: bash $ROOT/start.sh"
echo "  前端地址: http://localhost:3112"
echo "  后端地址: http://localhost:8112"
echo "  API 文档: http://localhost:8112/docs"
echo ""
