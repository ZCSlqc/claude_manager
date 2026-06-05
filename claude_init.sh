#!/usr/bin/env bash
set -euo pipefail

echo "=== Claude Code CLI 安装 ==="

# 检查是否已安装
if command -v claude &>/dev/null; then
    ver=$(claude --version 2>/dev/null || echo "未知")
    echo ""
    echo -e "\033[0;32m[OK]\033[0m claude CLI 已安装 ($ver)"
    exit 0
fi

echo ""
echo "正在安装 Claude Code CLI ..."

curl -fsSL https://claude.ai/install.sh | bash

echo ""
echo -e "\033[0;32m[OK]\033[0m 安装完成，验证版本:"
claude --version

echo ""
echo "==================================="
echo "  验证通过！"
echo "  返回: claude --version"
echo "==================================="
