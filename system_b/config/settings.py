"""系统 B：配置文件"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 系统 A API 地址
    system_a_api_url: str = os.getenv(
        "SYSTEM_A_API_URL",
        "http://localhost:8000"
    )

    # Streamlit 配置
    streamlit_server_port: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    streamlit_server_address: str = "0.0.0.0"

    # 系统 B 本地 SQLite 数据库路径（默认使用 SQLite）
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./football_quant.db")

    # 系统 A PostgreSQL 数据库连接
    system_a_database_url: str = os.getenv(
        "SYSTEM_A_DATABASE_URL",
        "postgresql://football:football_secure_pass@localhost:5432/football_data"
    )

    # 定时任务配置
    sync_interval_hours: int = 24  # 自动同步间隔（小时）
    sync_enabled: bool = True  # 是否启用自动同步

    # 日志
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()