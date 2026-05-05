"""测试管理后台设置页面功能"""

import os
import tempfile
import shutil
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# 导入 app（需要先确保 system_a 目录在 Python 路径中）
import sys
sys.path.insert(0, '/mnt/d/project/football_system/system_a')


class TestAdminSettings:
    """测试管理后台设置页面"""

    def setup_method(self):
        """测试前准备：创建临时 .env 文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_env_path = '/mnt/d/project/football_system/system_a/.env'
        self.backup_env_path = os.path.join(self.temp_dir, '.env.backup')

        # 如果有原始 .env 文件，备份
        if os.path.exists(self.original_env_path):
            shutil.copy(self.original_env_path, self.backup_env_path)

        # 创建测试客户端
        # 注意：app 需要在 mock 后再导入
        self.client = None

    def teardown_method(self):
        """测试后清理：恢复原始 .env 文件"""
        # 恢复原始 .env 文件
        if os.path.exists(self.backup_env_path):
            shutil.copy(self.backup_env_path, self.original_env_path)
        elif os.path.exists(self.original_env_path):
            os.remove(self.original_env_path)

        # 清理临时目录
        shutil.rmtree(self.temp_dir)

        # 清除已导入的模块缓存
        for module in list(sys.modules.keys()):
            if module.startswith('config.') or module.startswith('admin.') or module.startswith('api.'):
                del sys.modules[module]

    def _create_test_env_file(self, env_content):
        """创建测试用的 .env 文件"""
        with open(self.original_env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)

    @patch('config.database.init_db')
    def test_get_settings_page_returns_real_config(self, mock_init_db):
        """测试 GET /admin/settings 返回真实配置值（来自 Settings 实例）"""
        mock_init_db.return_value = None

        # 创建一个测试用的 .env 文件
        test_env_content = """CRAWL_CONCURRENCY=7
REQUEST_DELAY_MIN=0.5
REQUEST_DELAY_MAX=2.0
BATCH_SIZE=25
PROXY_ENABLED=true
PROXY_TYPE=http
PROXY_HOST=192.168.1.1
PROXY_PORT=8888
LOG_LEVEL=DEBUG
TITAN_BASE_URL=https://test.example.com
"""
        self._create_test_env_file(test_env_content)

        # 清除设置缓存（如果已导入）
        if 'config.settings' in sys.modules:
            from config.settings import get_settings
            get_settings.cache_clear()

        # 现在导入 app
        from api.main import app
        self.client = TestClient(app)

        # 访问设置页面
        response = self.client.get("/admin/settings")
        assert response.status_code == 200
        content = response.text

        # 验证页面是否包含测试配置值（而不是 hardcoded 的值）
        assert '7' in content  # crawl_concurrency
        assert '0.5' in content  # request_delay_min
        assert '2.0' in content  # request_delay_max
        assert '25' in content  # batch_size
        assert '192.168.1.1' in content  # proxy_host
        assert '8888' in content  # proxy_port
        assert 'DEBUG' in content  # log_level
        assert 'https://test.example.com' in content  # titan_base_url

    @patch('config.database.init_db')
    def test_post_settings_updates_env_file(self, mock_init_db):
        """测试 POST /admin/settings 更新 .env 文件"""
        mock_init_db.return_value = None

        # 创建初始 .env 文件
        initial_env_content = """CRAWL_CONCURRENCY=3
PROXY_ENABLED=false
PROXY_HOST=
PROXY_PORT=0
"""
        self._create_test_env_file(initial_env_content)

        # 清除设置缓存（如果已导入）
        if 'config.settings' in sys.modules:
            from config.settings import get_settings
            get_settings.cache_clear()

        # 现在导入 app
        from api.main import app
        self.client = TestClient(app)

        # 准备测试数据（表单格式）
        test_data = {
            "proxy_enabled": "true",
            "proxy_host": "test.proxy.com",
            "proxy_port": "8080",
            "crawl_concurrency": "5"
        }

        # 发送 POST 请求
        response = self.client.post("/admin/settings", data=test_data)
        assert response.status_code == 200

        # 验证响应包含成功消息
        assert "配置已保存" in response.text

        # 验证 .env 文件已更新
        with open(self.original_env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()

        assert 'PROXY_ENABLED=true' in env_content
        assert 'PROXY_HOST=test.proxy.com' in env_content
        assert 'PROXY_PORT=8080' in env_content
        assert 'CRAWL_CONCURRENCY=5' in env_content

    @patch('config.database.init_db')
    def test_post_settings_preserves_other_fields(self, mock_init_db):
        """测试 POST 只修改部分字段时，其他配置项不被删除"""
        mock_init_db.return_value = None

        # 首先确保 .env 文件有一些初始配置
        initial_env_content = """DATABASE_URL=postgresql://test:test@localhost:5432/test_db
API_PORT=8000
LOG_LEVEL=INFO
CRAWL_CONCURRENCY=3
# 这是一条注释
PROXY_ENABLED=false

# 空行后
PROXY_HOST=old.proxy.com
"""
        self._create_test_env_file(initial_env_content)

        # 清除设置缓存（如果已导入）
        if 'config.settings' in sys.modules:
            from config.settings import get_settings
            get_settings.cache_clear()

        # 现在导入 app
        from api.main import app
        self.client = TestClient(app)

        # 只修改部分字段
        test_data = {
            "crawl_concurrency": "4",
            "proxy_enabled": "false",
            "proxy_host": "new.proxy.com"
        }

        # 发送 POST 请求
        response = self.client.post("/admin/settings", data=test_data)
        assert response.status_code == 200

        # 验证 .env 文件已更新目标字段，同时保留其他字段
        with open(self.original_env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()

        # 验证修改后的字段
        assert 'CRAWL_CONCURRENCY=4' in env_content
        assert 'PROXY_ENABLED=false' in env_content
        assert 'PROXY_HOST=new.proxy.com' in env_content

        # 验证其他字段没有被删除
        assert 'DATABASE_URL=postgresql://test:test@localhost:5432/test_db' in env_content
        assert 'API_PORT=8000' in env_content
        assert 'LOG_LEVEL=INFO' in env_content

        # 验证注释和空行被保留
        assert '# 这是一条注释' in env_content
        assert '\n\n' in env_content or '\n# 空行后' in env_content

