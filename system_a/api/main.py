"""系统 A：FastAPI 入口"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.database import init_db

from api.routes import leagues, matches, odds, crawl, x_values, settlement
from admin.routes import router as admin_router

settings = get_settings()

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("正在启动足球数据系统 A...")
    try:
        init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化跳过: {e}")

    yield

    # 关闭时
    logger.info("足球数据系统 A 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(admin_router)  # 管理后台（HTML 页面）
app.include_router(leagues.router, prefix="/api", tags=["联赛"])
app.include_router(matches.router, prefix="/api", tags=["比赛"])
app.include_router(odds.router, prefix="/api", tags=["赔率"])
app.include_router(crawl.router, prefix="/api", tags=["爬虫"])
app.include_router(x_values.router, prefix="/api", tags=["X值"])
app.include_router(settlement.router, prefix="/api", tags=["结算"])


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "service": "足球数据系统 A",
        "version": settings.api_version,
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )