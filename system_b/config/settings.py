"""系统 B：配置文件"""

import os
from pydantic_settings import BaseSettings
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

    # 数据库（可选，系统 B 可以直接从系统 A API 获取数据）
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://football:football_secure_pass@localhost:5432/football_data"
    )

    # 定时任务配置
    sync_interval_hours: int = 24  # 自动同步间隔（小时）
    sync_enabled: bool = True  # 是否启用自动同步

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()