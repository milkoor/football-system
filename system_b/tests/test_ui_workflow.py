"""UI文案和流程衔接测试

验证：
1. system_sync 页面包含"一键同步所有联赛"
2. system_sync 页面不包含"檔案下載"（已合并到数据导入）
3. data_importer 页面包含"报表看板"而非"信号看板"
"""

import unittest


class TestUIWorkflow(unittest.TestCase):
    """测试UI文案一致性和流程衔接"""

    def test_system_sync_has_one_click_button(self):
        """验证system_sync页面包含'一键同步所有联赛'"""
        with open('/mnt/d/project/football_system/system_b/app_pages/system_sync.py', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('一键同步所有联赛', content, "system_sync页面应包含'一键同步所有联赛'按钮")

    def test_system_sync_no_outdated_text(self):
        """验证system_sync页面不包含'檔案下載'"""
        with open('/mnt/d/project/football_system/system_b/app_pages/system_sync.py', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertNotIn('檔案下載', content, "system_sync页面不应包含过时的'檔案下載'文案")

    def test_data_importer_has_correct_etl_tip(self):
        """验证data_importer页面包含'报表看板'而非'信号看板'"""
        with open('/mnt/d/project/football_system/system_b/original_pages/data_importer.py', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('报表看板', content, "data_importer页面应包含'报表看板'")
        self.assertNotIn('信号看板', content, "data_importer页面不应包含'信号看板'")


if __name__ == '__main__':
    unittest.main()
