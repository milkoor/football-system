#!/bin/bash
# ============================================
# 足球博彩数据系统 - 一键停止脚本
# ============================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

echo "🛑 停止服务..."
sudo $COMPOSE down
echo "✅ 已停止所有服务"