"""
测试X值本地计算功能
验证 data_connector.calculate_x_values 方法使用本地计算器
而非调用系统A的API
"""

import pytest
from unittest.mock import Mock, patch, call
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

        # 模拟获取比赛列表和赔率数据（无elapsed_time≥85，不跳过）
        mock_client_instance.request.side_effect = [
            # 第一次调用：获取比赛列表
            Mock(json=lambda: {'total': 2, 'matches': [{'match_id': 1}, {'match_id': 2}]}),
            # 第二次调用：获取比赛1的赔率
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早', 'elapsed_time': ''}
            ]}),
            # 第三次调用：获取比赛2的赔率
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '1.0', 'home_rate': 0.8, 'away_rate': 0.2, 'status': '早', 'elapsed_time': ''}
            ]}),
        ]

        # 模拟计算器
        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.side_effect = [
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

        # 验证调用了本地计算器（通过 calculate_from_odds_data）
        assert mock_calculator_cls.called
        assert mock_calculator.calculate_from_odds_data.call_count == 2

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_fetches_odds_from_system_a(self, mock_calculator_cls, mock_httpx_client):
        """验证计算前从系统A获取赔率数据"""
        # 设置 mock
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早', 'elapsed_time': ''}
            ]}),
            Mock(json=lambda: {'match_id': 1, 'x_value': 0.5}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.return_value = {'match_id': 1, 'x_value': 0.5, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # 验证获取赔率数据的调用
        called_urls = [call.args[1] for call in mock_client_instance.request.call_args_list]
        assert any('/api/matches' in url for url in called_urls)
        assert any('/odds' in url for url in called_urls)

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_counts_success(self, mock_calculator_cls, mock_httpx_client):
        """验证计算完成后的计数正确"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'away_rate': 0.1, 'status': '早', 'elapsed_time': ''}
            ]}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.return_value = {'match_id': 1, 'x_value': 0.5, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()

        result = connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # X值计算成功，不保存到系统A
        assert result['completed'] == 1
        assert result['failed'] == 0

        # 验证没有调用 /api/x-values 的 POST
        called_urls = [call.args[1] for call in mock_client_instance.request.call_args_list]
        assert not any('/api/x-values' in url for url in called_urls)

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_handles_no_odds_gracefully(self, mock_calculator_cls, mock_httpx_client):
        """无赔率数据时优雅处理"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        # get_match_odds 返回空 movements
        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1}]}),
            Mock(json=lambda: {'movements': []}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.return_value = {
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

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_skips_completed_matches(self, mock_calculator_cls, mock_httpx_client):
        """验证elapsed_time≥85的比赛被跳过（比赛已完成）"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        # 三场比赛：已完成(94分钟)、无时间(可计算)、已完成(90分钟)
        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {
                'total': 3, 'matches': [
                    {'match_id': 1, 'score_ft': '1-0'},
                    {'match_id': 2, 'score_ft': ''},
                    {'match_id': 3, 'score_ft': '2-2'},
                ]
            }),
            # match 1 odds: 有elapsed_time=94
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'elapsed_time': '94', 'status': '滚'},
                {'handicap_raw': '0.5', 'home_rate': 0.85, 'elapsed_time': '30', 'status': '早'},
            ]}),
            # match 2 odds: 无elapsed_time≥85
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'elapsed_time': '', 'status': '早'},
            ]}),
            # match 3 odds: 有elapsed_time=90
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.75', 'home_rate': 0.8, 'elapsed_time': '90', 'status': '滚'},
                {'handicap_raw': '0.75', 'home_rate': 0.75, 'elapsed_time': '45', 'status': '即'},
            ]}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.return_value = {'match_id': 2, 'x_value': 0.3, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        result = connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # 只有match 2被计算，match 1和3被跳过
        assert result['completed'] == 1
        assert result['skipped'] == 2
        assert result['failed'] == 0
        assert mock_calculator.calculate_from_odds_data.call_count == 1

    @patch('modules.data_connector.httpx.Client')
    @patch('modules.data_connector.XValueCalculator')
    def test_calculate_x_values_skips_excludes_matches_without_elapsed_time(self, mock_calculator_cls, mock_httpx_client):
        """验证缺少elapsed_time字段的比赛不会被跳过"""
        mock_client_instance = Mock()
        mock_httpx_client.return_value = mock_client_instance

        mock_client_instance.request.side_effect = [
            Mock(json=lambda: {'total': 1, 'matches': [{'match_id': 1, 'score_ft': '3-0'}]}),
            Mock(json=lambda: {'movements': [
                {'handicap_raw': '0.5', 'home_rate': 0.9, 'status': '早'},
            ]}),
        ]

        mock_calculator = Mock()
        mock_calculator.calculate_from_odds_data.return_value = {'match_id': 1, 'x_value': 0.5, 'status': 'success'}
        mock_calculator_cls.return_value = mock_calculator

        connector = DataConnector()
        result = connector.calculate_x_values(league_id=2064, season_label='2025-2026')

        # 没有elapsed_time，不跳过，正常计算
        assert result['completed'] == 1
        assert result['skipped'] == 0
        assert result['failed'] == 0