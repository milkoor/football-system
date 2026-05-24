"""测试自动同步设置界面"""

import os


def test_sync_page_has_auto_sync_section():
    """验证数据导入页面包含自动同步相关中文字符串"""
    page_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/data_importer.py"
    )

    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "自动同步设定" in content, \
        "数据导入页面应包含'自动同步设定'相关文字"


def test_sync_page_reads_auto_enable():
    """验证数据导入页面源码包含启用自动同步"""
    page_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/data_importer.py"
    )

    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "启用自动同步" in content, \
        "数据导入页面应引用启用自动同步"


def test_sync_page_reads_sync_interval():
    """验证数据导入页面源码包含同步间隔设置"""
    page_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/data_importer.py"
    )

    with open(page_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "同步间隔" in content, \
        "数据导入页面应引用同步间隔"
