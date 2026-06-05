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
echo "使用 npm 全局安装 @anthropic-ai/claude-code ..."

sudo npm install -g @anthropic-ai/claude-code

echo ""
echo -e "\033[0;32m[OK]\033[0m 安装完成，验证版本:"
claude --version

echo ""
echo "==================================="
echo "  安装完成！"
echo "  返回: claude --version"
echo "==================================="
