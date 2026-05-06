"""测试自动同步设置界面"""

import os


def test_settings_page_has_sync_section():
    """验证设置页面包含自动同步相关中文字符串"""
    settings_py_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/settings.py"
    )

    with open(settings_py_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_auto_sync = "自动同步" in content
    has_timed_sync = "定时同步" in content

    assert has_auto_sync or has_timed_sync, \
        "设置页面应包含'自动同步'或'定时同步'相关文字"


def test_settings_page_reads_sync_enabled():
    """验证设置页面源码包含 sync_enabled"""
    settings_py_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/settings.py"
    )

    with open(settings_py_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "sync_enabled" in content, \
        "设置页面应引用 sync_enabled"


def test_settings_page_reads_sync_interval():
    """验证设置页面源码包含 sync_interval_hours"""
    settings_py_path = os.path.join(
        os.path.dirname(__file__),
        "../original_pages/settings.py"
    )

    with open(settings_py_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "sync_interval_hours" in content, \
        "设置页面应引用 sync_interval_hours"
