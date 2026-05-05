"""集成测试 - 直接测试设置页面"""

import os
import sys
import tempfile

sys.path.insert(0, '/mnt/d/project/football_system/system_a')


def test_admin_settings_get_post():
    """测试设置页面的 GET 和 POST 请求"""
    from unittest.mock import patch
    with patch('config.database.init_db') as mock_init_db:
        mock_init_db.return_value = None

        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)

        # 测试 GET 请求
        print("测试 GET /admin/settings...")
        response = client.get("/admin/settings")
        assert response.status_code == 200
        print("✓ GET 请求成功")

        # 检查响应内容
        content = response.text
        assert "系统配置" in content
        assert "爬虫配置" in content
        assert "代理配置" in content
        print("✓ 页面内容验证成功")

        # 测试 POST 请求
        print("\n测试 POST /admin/settings...")
        test_data = {
            "crawl_concurrency": "4",
            "request_delay_min": "1.5",
            "request_delay_max": "3.5",
            "batch_size": "15",
            "proxy_enabled": "true",
            "proxy_type": "http",
            "proxy_host": "proxy.example.com",
            "proxy_port": "8080",
            "proxy_username": "test_user",
            "proxy_password": "test_password",
            "log_level": "DEBUG"
        }

        response = client.post("/admin/settings", data=test_data)
        assert response.status_code == 200
        print("✓ POST 请求成功")

        # 检查是否包含成功消息
        content = response.text
        assert "配置已保存" in content
        print("✓ 成功消息显示正确")

        print("\n✅ 集成测试完成！设置页面功能正常")


if __name__ == '__main__':
    print("开始集成测试...")

    # 保存原始 .env 文件并创建测试 .env 文件
    original_env_path = '/mnt/d/project/football_system/system_a/.env'
    backup_env_path = '/mnt/d/project/football_system/system_a/.env.backup'

    if os.path.exists(original_env_path):
        import shutil
        shutil.copy(original_env_path, backup_env_path)

    # 创建一个简单的测试用 .env 文件
    test_env_content = """CRAWL_CONCURRENCY=3
REQUEST_DELAY_MIN=1.0
REQUEST_DELAY_MAX=3.0
BATCH_SIZE=10
PROXY_ENABLED=false
PROXY_HOST=
PROXY_PORT=0
LOG_LEVEL=INFO
"""

    with open(original_env_path, 'w', encoding='utf-8') as f:
        f.write(test_env_content)

    try:
        test_admin_settings_get_post()
    finally:
        # 恢复原始 .env 文件
        if os.path.exists(backup_env_path):
            import shutil
            shutil.copy(backup_env_path, original_env_path)
            os.unlink(backup_env_path)
        print("\n环境文件已恢复")
