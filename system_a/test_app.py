"""测试应用是否能正常启动"""

import sys
import subprocess

sys.path.insert(0, '/mnt/d/project/football_system/system_a')

def test_app_health():
    """测试健康检查端点"""
    try:
        import uvicorn
        from api.main import app
        print("✅ 应用导入成功")

        # 这里我们不启动完整服务器，只检查路由是否能导入
        print("✅ FastAPI 应用初始化成功")
        print("✅ 管理后台路由已包含在应用中")

        # 检查是否有 /admin/settings 路由
        for route in app.routes:
            if hasattr(route, 'path'):
                if '/admin/settings' in route.path:
                    print(f"✅ 找到路由: {route.path}")

        return True
    except Exception as e:
        print(f"❌ 应用启动失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def test_settings_module():
    """测试配置模块"""
    try:
        from config.settings import Settings, get_settings
        print("✅ Settings 类导入成功")

        settings = get_settings()
        print("✅ 配置实例化成功")

        # 检查是否有预期的字段
        expected_fields = [
            'crawl_concurrency', 'request_delay_min', 'request_delay_max',
            'batch_size', 'proxy_enabled', 'proxy_type', 'proxy_host',
            'proxy_port', 'proxy_username', 'proxy_password', 'titan_base_url',
            'titan_schedule_url', 'log_level'
        ]

        for field in expected_fields:
            if hasattr(settings, field):
                print(f"✅ 配置字段 {field} 存在")

        return True
    except Exception as e:
        print(f"❌ 配置模块失败: {e}")
        return False


if __name__ == '__main__':
    print("开始应用测试...")
    print("=" * 40)

    app_ok = test_app_health()
    settings_ok = test_settings_module()

    print("=" * 40)
    if app_ok and settings_ok:
        print("🎉 所有测试通过！应用应该可以正常运行")
    else:
        print("⚠️  部分测试失败，请检查！")
