"""
测试X值本地计算功能
验证 data_connector.calculate_x_values 方法是否使用本地计算器
而非调用系统A的API
"""

import pytest
from unittest.mock import Mock, patch
from modules.data_connector import DataConnector
from modules.x_calculator import XValueCalculator


class TestDataConnectorCalculateXValues:
    """测试 calculate_x_values 方法"""

    def test_data_connector_has_calculate_x_values_method(self):
        """验证 data_connector 有 calculate_x_values 方法"""
        connector = DataConnector()
        assert hasattr(connector, 'calculate_x_values'), "DataConnector should have calculate_x_values method"
        assert callable(getattr(connector, 'calculate_x_values')), "calculate_x_values should be callable"

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_uses_local_calculator(self, mock_calculator_cls, mock_httpx_client):
        """验证 calculate_x_values 调用本地 XValueCalculator 而非系统A API"""
        # 设置 mock
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        # 模拟获取比赛列表和赔率数据
        mock_client_instance.request.side_effect = [
            # 第一次调用：获取比赛列表
            Mock(json=lambda: {'total': 2, 'matches': [{'match_id': 1}, {'match_id': 2}]}),
            # 第二次调用：获取比赛1的赔率
            Mock(json=lambda: {'movements': [{'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早'}]}),
            # 第三次调用：获取比赛2的赔率
            Mock(json=lambda: {'movements': [{'handicap_raw': '1.0', 'home_rate': 0.8, 'away_rate': 0.2, 'status': '早'}]}),
            # 第四次调用：保存比赛1的X值
            Mock(json=lambda: {'match_id': 1, 'x_value': 0.5}),
            # 第五次调用：保存比赛2的X值
            Mock(json=lambda: {'match_id': 2, 'x_value': 0.8}),
        ]

        # 模拟计算器
        mock_calculator = Mock()
        mock_calculator.calculate_from_match.side_effect = [
            {'match_id': 1, 'x_value': 0.5, 'status': 'success'},
            {'match_id': 2, 'x_value': 0.8, 'status': 'success'},
        ]
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()

        # 执行测试
        result = connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # 验证结果
        assert 'message' in result
        assert 'completed' in result
        assert 'failed' in result

        # 验证没有调用系统A的 /api/x-values/calculate 端点
        called_urls = [call.args[1] for call in mock_client_instance.request.call_args_list]
        assert '/api/x-values/calculate' not in [url for url in called_urls]

        # 验证调用了本地计算器
        assert mock_calculator_cls.called
        assert mock_calculator.calculate_from_match.call_count == 2

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.x_calculator.XValueCalculator')
    def test_calculate_x_values_fetches_odds_from_system_a(self, mock_calculator_cls, mock_httpx_client):
        """验证计算前从系统A获取赔率数据"""
        # 设置 mock
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': [{'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早'}]}),
            Mock(json=lambda: {'match_id': 1, 'x_value': 0.5}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_match.return_value = {'match_id': 1, 'x_value': 0.5, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # 验证获取赔率数据的调用
        called_urls = [call.args[1] for call in mock_client_instance.request.call_args_list]
        assert any('/api/matches' in url for url in called_urls)
        assert any('/odds' in url for url in called_urls)

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.x_calculator.XValueCalculator')
    def test_calculate_x_values_saves_via_crud(self, mock_calculator_cls, mock_httpx_client):
        """验证计算完成后通过 save_x_value 保存结果"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': [{'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早'}]}),
            Mock(json=lambda: {'match_id': 1, 'x_value': 0.5}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_match.return_value = {'match_id': 1, 'x_value': 0.5, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        with patch.object(connector, 'save_x_value') as mock_save:
            mock_save.return_value = {'match_id': 1, 'x_value': 0.5}

            connector.calculate_x_values(league_id=2064, season_label='2025-2026')

            # 验证保存方法被调用
            assert mock_save.called
            assert mock_save.call_count == 1

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.x_calculator.XValueCalculator')
    def test_calculate_x_values_handles_no_odds_gracefully(self, mock_calculator_cls, mock_httpx_client):
        """无赔率数据时优雅处理"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': []}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_match.return_value = {
            'match_id': 1,
            'status': 'no_data',
            'calculation_note': 'No odds data',
            'x_value': None
        }
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        result = connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        assert result['completed'] == 0
        assert result['failed'] == 1
