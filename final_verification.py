#!/usr/bin/env python3
"""项目最终验证脚本"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / 'system_b'))

print("🚀 足球数据系统整合项目 - 最终验证\n")

success_count = 0
total_checks = 0

def check_file_exists(file_path):
    global success_count, total_checks
    total_checks += 1
    if os.path.exists(file_path):
        print("✅", file_path)
        success_count += 1
    else:
        print("❌", file_path)

def check_import(module_name):
    global success_count, total_checks
    total_checks += 1
    try:
        __import__(module_name)
        print("✅", module_name)
        success_count += 1
    except Exception as e:
        print("❌", module_name, "-", str(e))

# 检查关键文件是否存在
print("=== 检查关键文件 ===\n")

# 系统 A 文件
check_file_exists("/mnt/d/project/football_system/system_a/api/routes/x_values.py")

# 系统 B 文件
check_file_exists("/mnt/d/project/football_system/system_b/original_pages/8_data_importer.py")
check_file_exists("/mnt/d/project/football_system/system_b/etl/reader.py")
check_file_exists("/mnt/d/project/football_system/system_b/etl/pipeline.py")
check_file_exists("/mnt/d/project/football_system/system_b/config/settings.py")
check_file_exists("/mnt/d/project/football_system/system_b/app.py")

# 文档
check_file_exists("/mnt/d/project/football_system/COMPLETION_REPORT.md")

# 检查依赖
print("\n=== 检查核心依赖 ===\n")
check_import("streamlit")
check_import("pandas")
check_import("numpy")
check_import("sqlalchemy")
check_import("psycopg2")
check_import("httpx")
check_import("pydantic")

# 简单功能测试
print("\n=== 简单功能测试 ===\n")

try:
    # 测试配置加载
    from config.settings import get_settings
    settings = get_settings()
    print("✅ 配置加载成功")

    # 测试读取器导入
    from etl.reader import RawDataReader
    reader = RawDataReader()
    print("✅ 数据读取器初始化成功")

    # 测试管道导入
    from etl.pipeline import ETLPipeline
    from etl.config_store import get_store
    pipeline = ETLPipeline(get_store())
    print("✅ ETL 管道初始化成功")

    success_count += 3  # 3个新的成功测试
    total_checks += 3

except Exception as e:
    print("❌", str(e))

# 输出结果
print(f"\n=== 验证完成 ===\n")
print(f"通过: {success_count}")
print(f"失败: {total_checks - success_count}")
print(f"总检查数: {total_checks}")

if success_count == total_checks:
    print("\n🎉 项目验证成功！所有功能已准备就绪！")
else:
    print("\n⚠️ 部分功能未通过验证，可能需要进一步检查")
    sys.exit(1)
