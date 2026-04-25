"""系统 A：配置文件"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 数据库
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://football:football_secure_pass@localhost:5432/football_data"
    )

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "足球数据系统 A API"
    api_version: str = "1.0.0"

    # 爬虫配置
    crawl_concurrency: int = 3
    request_delay_min: float = 1.0
    request_delay_max: float = 3.0
    batch_size: int = 10

    # 代理配置
    proxy_enabled: bool = False
    proxy_type: str = "socks5"  # socks5, http, oxylabs
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_username: str = ""
    proxy_password: str = ""

    # 目标网站
    titan_base_url: str = "https://vip.titan007.com"
    titan_schedule_url: str = "https://zq.titan007.com"

    # 日志
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()