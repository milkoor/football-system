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
        """测试是否存在完整同步相关的中文字符串"""
        sync_keywords = [
            "完整同步",
            "赛程",
        ]

        found_keywords = []
        for keyword in sync_keywords:
            if keyword in self.content:
                found_keywords.append(keyword)

        # 至少应该找到一些关键字
        assert len(found_keywords) > 0, f"未找到完整同步相关关键字，找到的: {found_keywords}"
        print(f"OK 找到完整同步相关关键字: {found_keywords}")

    def test_has_system_a_mapper_import(self):
        """测试是否导入了 system_a_mapper 的 import_matches_to_system_b 函数"""
        has_import = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == 'utils.system_a_mapper':
                    for name in node.names:
                        if name.name == 'import_matches_to_system_b':
                            has_import = True
        assert has_import, "未找到 'from utils.system_a_mapper import import_matches_to_system_b'"

    def test_has_settlement_calculator_call(self):
        """SettlementCalculator 调用已下沉到 utils.system_a_mapper，data_importer.py 不再直接使用"""
        # 该测试保留为占位，验证不再有直接的 SettlementCalculator 引用
        has_settlement_call = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'id') and node.func.id == 'SettlementCalculator':
                    has_settlement_call = True
        assert not has_settlement_call, "SettlementCalculator 已下沉到 utils.system_a_mapper，data_importer 不应直接调用"

    def test_has_sync_league_to_system_b_call(self):
        """sync_league_to_system_b 调用已下沉到 utils.system_a_mapper.import_matches_to_system_b"""
        has_call = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'id') and node.func.id == 'sync_league_to_system_b':
                    has_call = True
        assert not has_call, "sync_league_to_system_b 已下沉，data_importer 不应直接调用"

    def test_has_upsert_match_records_call(self):
        """upsert_match_records 调用已下沉到 utils.system_a_mapper.import_matches_to_system_b"""
        has_call = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'upsert_match_records':
                    has_call = True
        assert not has_call, "upsert_match_records 已下沉，data_importer 不应直接调用"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
