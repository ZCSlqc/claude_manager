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

# ============ 复制 .claude 配置到 ~ ============
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_CLAUDE="$SCRIPT_DIR/.claude"
DST_CLAUDE="$HOME/.claude"

if [ -d "$SRC_CLAUDE" ]; then
    echo ""
    echo "复制 .claude 配置到 ~/.claude ..."

    if [ -d "$DST_CLAUDE" ]; then
        echo "  ~/.claude 已存在，合并文件..."
        if [ -f "$SRC_CLAUDE/settings.json" ]; then
            cp "$SRC_CLAUDE/settings.json" "$DST_CLAUDE/settings.json"
            echo "  - settings.json → ~/.claude/settings.json"
        fi
        if [ -f "$SRC_CLAUDE/CLAUDE.md" ]; then
            cp "$SRC_CLAUDE/CLAUDE.md" "$DST_CLAUDE/CLAUDE.md"
            echo "  - CLAUDE.md → ~/.claude/CLAUDE.md"
        fi
        if [ -d "$SRC_CLAUDE/skills" ]; then
            cp -r "$SRC_CLAUDE/skills" "$DST_CLAUDE/skills"
            echo "  - skills/ → ~/.claude/skills/"
        fi
    else
        cp -r "$SRC_CLAUDE" "$DST_CLAUDE"
        echo "  - 整体复制到 ~/.claude/"
    fi

    echo ""
    echo -e "\033[0;32m[OK]\033[0m .claude 配置已同步到 ~/.claude/"
else
    echo ""
    echo -e "\033[1;33m[WARN]\033[0m 未找到 .claude 目录，跳过配置同步"
fi

echo ""
echo "==================================="
echo "  安装完成！"
echo "  验证: claude --version"
echo "==================================="
