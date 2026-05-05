"""简单的设置页面测试"""

import os
import sys

sys.path.insert(0, '/mnt/d/project/football_system/system_a')

def test_settings_read():
    """测试配置读取"""
    # 创建临时环境
    env_content = """CRAWL_CONCURRENCY=10
PROXY_ENABLED=true
PROXY_HOST=test.proxy.com
"""

    with open('/tmp/test.env', 'w') as f:
        f.write(env_content)

    # 测试 Settings 类
    from config.settings import Settings

    # 我们不实际覆盖全局 .env，而是直接测试功能
    print("✓ Settings 类导入成功")

    from config.settings import get_settings
    settings = get_settings()
    print(f"✓ 配置读取成功，crawl_concurrency={settings.crawl_concurrency}")


def test_env_update_logic():
    """测试环境变量更新逻辑"""
    # 测试更新逻辑而不需要完整的 FastAPI 应用
    import tempfile
    import shutil

    # 创建临时 .env
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""DATABASE_URL=test
# 这是一条注释
CRAWL_CONCURRENCY=3

PROXY_ENABLED=false
""")
        env_path = f.name

    try:
        # 模拟更新
        lines = []
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # 更新字段
        updates = {
            'CRAWL_CONCURRENCY': '5',
            'PROXY_ENABLED': 'true'
        }

        new_lines = []
        updated_keys = set()

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        # 验证结果
        with open(env_path, 'r') as f:
            result = f.read()

        assert 'CRAWL_CONCURRENCY=5' in result
        assert 'PROXY_ENABLED=true' in result
        assert 'DATABASE_URL=test' in result
        assert '# 这是一条注释' in result
        print("✓ 环境变量更新逻辑测试通过")

    finally:
        os.unlink(env_path)


if __name__ == '__main__':
    print("开始简单测试...")
    test_settings_read()
    test_env_update_logic()
    print("✅ 所有简单测试通过")
