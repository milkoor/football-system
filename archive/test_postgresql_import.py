#!/usr/bin/env python3
"""测试从 PostgreSQL 导入数据的功能"""

import sys
from pathlib import Path

# 添加系统 B 的路径
sys.path.insert(0, str(Path(__file__).parent / 'system_b'))

try:
    from etl.reader import RawDataReader
    from etl.config_store import ConfigStore
    from etl.pipeline import ETLPipeline
    from config.settings import get_settings

    print("开始测试...")

    # 1. 测试配置加载
    print("1. 测试配置加载...")
    settings = get_settings()
    print(f"✓ 系统 A PostgreSQL 地址: {settings.system_a_database_url}")
    print(f"✓ 系统 B 数据库地址: {settings.database_url}")

    # 2. 测试数据读取
    print("\n2. 测试数据读取...")
    reader = RawDataReader()
    try:
        data = reader.read_from_postgresql()
        print(f"✓ 成功读取数据")
        print(f"  - 联赛数量: {len(data['leagues'])}")
        print(f"  - 赛季数量: {len(data['seasons'])}")
        print(f"  - 比赛记录组数: {len(data['matches_by_league_season'])}")
    except Exception as e:
        print(f"✗ 数据读取失败: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

    print("\n测试通过！系统 B 的 PostgreSQL 数据导入功能已准备就绪。")

except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)
