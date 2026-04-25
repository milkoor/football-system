"""数据库初始化脚本"""

import sys
sys.path.insert(0, "/home/mk/project/football_system/system_a")

from config.database import engine, Base
from config.models import (
    LeagueIndex,
    Season,
    Match,
    OddsMovement,
    XValueResult,
    CrawlJob,
)


def init_database():
    """初始化所有数据库表"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成！")


def drop_database():
    """删除所有数据库表（危险操作）"""
    print("警告：即将删除所有数据库表！")
    Base.metadata.drop_all(bind=engine)
    print("数据库表已删除！")


def reset_database():
    """重置数据库"""
    drop_database()
    init_database()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化工具")
    parser.add_argument("--reset", action="store_true", help="重置数据库")
    parser.add_argument("--drop", action="store_true", help="删除所有表")

    args = parser.parse_args()

    if args.drop:
        drop_database()
    elif args.reset:
        reset_database()
    else:
        init_database()