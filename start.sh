#!/bin/bash
# ============================================
# 足球博彩数据系统 - 一键启动脚本
# ============================================

set -e

echo "========================================"
echo "⚽ 足球博彩数据系统 - 启动中..."
echo "========================================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    exit 1
fi

# 使用 docker compose 或 docker-compose
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

# 项目目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "📦 构建 Docker 镜像..."
echo "----------------------------------------"
sudo $COMPOSE build

echo ""
echo "🚀 启动服务..."
echo "----------------------------------------"
sudo $COMPOSE up -d

echo ""
echo "⏳ 等待服务就绪..."
echo "----------------------------------------"

# 等待数据库
echo -n "  数据库..."
for i in {1..30}; do
    if sudo docker inspect --format='{{.State.Health.Status}}' football_system_db 2>/dev/null | grep -q "healthy"; then
        echo " ✅"
        break
    fi
    sleep 1
    echo -n "."
done

# 等待系统 A
echo -n "  系统 A (API)..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &>/dev/null; then
        echo " ✅"
        break
    fi
    sleep 1
    echo -n "."
done

# 等待系统 B
echo -n "  系统 B (前端)..."
for i in {1..30}; do
    if curl -s http://localhost:8501/_stcore/health &>/dev/null; then
        echo " ✅"
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "========================================"
echo "✅ 启动完成！"
echo "========================================"
echo ""
echo "📍 访问地址："
echo "   • 系统 A API:  http://localhost:8000"
echo "   • 系统 B 前端: http://localhost:8501"
echo "   • PostgreSQL:  localhost:5432"
echo ""
echo "📋 管理命令："
echo "   • 查看日志:   sudo $COMPOSE logs -f"
echo "   • 停止服务:   sudo $COMPOSE down"
echo "   • 重启服务:   sudo $COMPOSE restart"
echo "========================================"