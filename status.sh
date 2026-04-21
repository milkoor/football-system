#!/bin/bash
# ============================================
# 足球博彩数据系统 - 状态查看脚本
# ============================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "📊 系统状态"
echo "========================================"
echo ""

# 使用 docker ps 或 docker-compose ps
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

sudo $COMPOSE ps

echo ""
echo "========================================"
echo "🌐 服务健康检查"
echo "========================================"

# 检查系统 A
if curl -s http://localhost:8000/health &>/dev/null; then
    echo "✅ 系统 A API:   http://localhost:8000"
else
    echo "❌ 系统 A API:   未运行"
fi

# 检查系统 B
if curl -s http://localhost:8501/_stcore/health &>/dev/null; then
    echo "✅ 系统 B 前端:  http://localhost:8501"
else
    echo "❌ 系统 B 前端:  未运行"
fi

# 检查数据库
if sudo docker inspect --format='{{.State.Health.Status}}' football_system_db 2>/dev/null | grep -q "healthy"; then
    echo "✅ PostgreSQL:   localhost:5432"
else
    echo "❌ PostgreSQL:   未运行"
fi

echo "========================================"