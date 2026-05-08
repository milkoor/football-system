"""
测试 data_importer.py 合并后的结构
验证 file_download.py 的功能已经正确合并到 data_importer.py
"""
import pytest
import os
import ast
import importlib
from pathlib import Path


class TestDataImporterMerge:
    """测试 data_importer.py 的合并结构"""

    def setup_method(self):
        """测试前的准备"""
        self.file_path = Path(__file__).parent.parent / "original_pages" / "data_importer.py"
        assert self.file_path.exists(), f"data_importer.py 不存在于 {self.file_path}"

        # 读取文件内容
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

        # 解析AST
        self.tree = ast.parse(self.content)

    def test_has_download_odds_section(self):
        """测试是否存在“下载赔率”相关的中文字符串"""
        download_odds_keywords = [
            "下载赔率",
            "一键下载所有关注赔率",
            "待爬取赔率"
        ]

        found_keywords = []
        for keyword in download_odds_keywords:
            if keyword in self.content:
                found_keywords.append(keyword)

        # 至少应该找到一些关键字
        assert len(found_keywords) > 0, f"未找到下载赔率相关关键字，找到的: {found_keywords}"
        print(f"✓ 找到下载赔率相关关键字: {found_keywords}")

    def test_has_system_a_mapper_import(self):
        """测试是否导入了 system_a_mapper 的相关函数"""
        # 检查 import 语句
        has_import = False
        has_sync_league = False
        has_sync_season = False

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == 'utils.system_a_mapper':
                    has_import = True
                    for name in node.names:
                        if name.name == 'sync_league_to_system_b':
                            has_sync_league = True
                        if name.name == 'sync_season_to_system_b':
                            has_sync_season = True

        assert has_import, "未找到 'from utils.system_a_mapper import ...'"
        assert has_sync_league, "未导入 sync_league_to_system_b"
        assert has_sync_season, "未导入 sync_season_to_system_b"
        print("✓ 已正确导入 system_a_mapper 相关函数")

    def test_has_settlement_calculator_call(self):
        """测试是否有 SettlementCalculator 的调用"""
        # 检查 SettlementCalculator 的导入或使用
        has_settlement_import = False
        has_settlement_call = False

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                # 检查 from core.settlement import SettlementCalculator
                if node.module == 'etl.settlement':
                    for name in node.names:
                        if name.name == 'SettlementCalculator':
                            has_settlement_import = True
            elif isinstance(node, ast.Import):
                # 检查 import etl.settlement
                for name in node.names:
                    if 'settlement' in name.name:
                        has_settlement_import = True
            elif isinstance(node, ast.Call):
                # 检查 SettlementCalculator() 的调用
                if hasattr(node.func, 'id') and node.func.id == 'SettlementCalculator':
                    has_settlement_call = True
                elif hasattr(node.func, 'attr') and node.func.attr == 'SettlementCalculator':
                    has_settlement_call = True

        # 至少应该有导入或调用
        assert has_settlement_import or has_settlement_call, "未找到 SettlementCalculator 的使用"
        print("✓ 已包含 SettlementCalculator 的使用")

    def test_has_sync_league_to_system_b_call(self):
        """测试是否有 sync_league_to_system_b 的调用"""
        has_call = False

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'id') and node.func.id == 'sync_league_to_system_b':
                    has_call = True
                elif hasattr(node.func, 'attr') and node.func.attr == 'sync_league_to_system_b':
                    has_call = True

        assert has_call, "未找到 sync_league_to_system_b 的调用"
        print("✓ 已包含 sync_league_to_system_b 调用")

    def test_has_upsert_match_records_call(self):
        """测试是否有 upsert_match_records 的调用（创建 MatchRecord 并保存）"""
        has_call = False

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'upsert_match_records':
                    has_call = True

        assert has_call, "未找到 upsert_match_records 的调用"
        print("✓ 已包含 upsert_match_records 调用")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
