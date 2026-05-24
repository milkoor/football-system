"""测试系统B的结算模块通过API调用系统A"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import httpx
from modules.settlement_calculator import AutoSettlementCalculator
from config.settings import get_settings


@pytest.fixture
def calculator():
    """创建结算计算器实例"""
    return AutoSettlementCalculator()


@pytest.fixture
def mock_settings():
    """创建模拟配置"""
    settings = get_settings()
    settings.system_a_api_url = "http://localhost:8000"
    return settings


class TestSystemBSettlementAPI:
    """测试系统B结算模块的API调用"""

    def _mock_httpx_client(self, mock_client_class, status_code=200, json_return=None, side_effect=None):
        """辅助函数：模拟httpx.Client的上下文管理器"""
        if json_return is None:
            json_return = {}

        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_return

        # 模拟client实例
        mock_client = Mock()
        if side_effect:
            mock_client.post.side_effect = side_effect
            mock_client.get.side_effect = side_effect
        else:
            mock_client.post.return_value = mock_response
            mock_client.get.return_value = mock_response

        # 模拟上下文管理器
        mock_client_class.return_value.__enter__.return_value = mock_client

        return mock_client

    @patch("httpx.Client")
    def test_single_match_auto_settle(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试单场自动结算：验证调用 POST /api/matches/{match_id}/auto-settle"""
        # 预期响应
        expected_response = {
            "match_id": 123,
            "home_team": "曼联",
            "away_team": "利物浦",
            "score": "2-1",
            "settlement": "主赢",
            "settlement_value": 1.0,
            "settlement_direction": "win",
            "home_away_direction": "home",
            "target_team": "曼联",
        }

        # 模拟client
        mock_client = self._mock_httpx_client(mock_client_class, 200, expected_response)

        # 执行测试
        result = calculator.auto_settle_match(123)

        # 验证调用
        mock_client.post.assert_called_once_with(
            f"{mock_settings.system_a_api_url}/api/matches/123/auto-settle"
        )

        # 验证结果
        assert result == expected_response

    @patch("httpx.Client")
    def test_batch_auto_settle(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试批量自动结算：验证调用 POST /api/matches/auto-settle"""
        # 预期响应
        expected_response = {
            "total": 2,
            "success": 2,
            "failed": 0,
            "results": [
                {
                    "match_id": 123,
                    "home_team": "曼联",
                    "away_team": "利物浦",
                    "score": "2-1",
                    "settlement": "主赢",
                    "settlement_value": 1.0,
                },
                {
                    "match_id": 124,
                    "home_team": "切尔西",
                    "away_team": "阿森纳",
                    "score": "1-1",
                    "settlement": "走",
                    "settlement_value": 0.0,
                },
            ],
        }

        # 模拟client
        mock_client = self._mock_httpx_client(mock_client_class, 200, expected_response)

        # 执行测试
        result = calculator.batch_auto_settle(league_id=2064, season="2025-2026")

        # 验证调用
        mock_client.post.assert_called_once_with(
            f"{mock_settings.system_a_api_url}/api/matches/auto-settle",
            json={"league_id": 2064, "season": "2025-2026"},
        )

        # 验证结果
        assert result == expected_response

    @patch("httpx.Client")
    def test_get_settlement_result(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试获取结算结果：验证 GET /api/matches/{match_id}/settlement"""
        # 预期响应
        expected_response = {
            "match_id": 123,
            "home_team": "曼联",
            "away_team": "利物浦",
            "score": "2-1",
            "settlement": "主赢",
            "settlement_value": 1.0,
            "settlement_direction": "win",
            "home_away_direction": "home",
            "target_team": "曼联",
        }

        # 模拟client
        mock_client = self._mock_httpx_client(mock_client_class, 200, expected_response)

        # 执行测试
        result = calculator.get_settlement_result(123)

        # 验证调用
        mock_client.get.assert_called_once_with(
            f"{mock_settings.system_a_api_url}/api/matches/123/settlement"
        )

        # 验证结果
        assert result == expected_response

    @patch("httpx.Client")
    def test_update_score_and_settle(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试更新比分并结算：验证 POST /api/matches/{match_id}/score"""
        # 预期响应
        expected_response = {
            "match_id": 123,
            "home_team": "曼联",
            "away_team": "利物浦",
            "score": "2-1",
            "settlement": "主赢",
            "settlement_value": 1.0,
        }

        # 模拟client
        mock_client = self._mock_httpx_client(mock_client_class, 200, expected_response)

        # 执行测试
        result = calculator.update_score_and_settle(123, "2-1")

        # 验证调用
        mock_client.post.assert_called_once_with(
            f"{mock_settings.system_a_api_url}/api/matches/123/score",
            json={"score": "2-1"},
        )

        # 验证结果
        assert result == expected_response

    @patch("httpx.Client")
    def test_api_call_failure(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试API调用失败时的错误处理"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        # 模拟client
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # 执行测试
        result = calculator.auto_settle_match(123)

        # 验证结果
        assert "error" in result
        assert "API调用失败" in result["error"]
        assert "500" in result["error"]

    @patch("httpx.Client")
    def test_api_connection_error(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试API连接失败时的错误处理"""
        # 模拟连接错误
        mock_client = Mock()
        mock_client.get.side_effect = httpx.ConnectError("无法连接到服务器")
        mock_client_class.return_value.__enter__.return_value = mock_client

        # 执行测试
        result = calculator.get_settlement_result(123)

        # 验证结果
        assert "error" in result
        assert "连接失败" in result["error"]

    @patch("httpx.Client")
    def test_score_update_and_settle_failure(
        self, mock_client_class: Mock, calculator: AutoSettlementCalculator, mock_settings
    ):
        """测试更新比分并结算失败的错误处理"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "无效的比分格式"

        # 模拟client
        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        # 执行测试
        result = calculator.update_score_and_settle(123, "invalid-score")

        # 验证结果
        assert "error" in result
        assert "API调用失败" in result["error"]
        assert "400" in result["error"]


class TestLocalSettlementFunctions:
    """测试本地结算函数（纯计算逻辑，不依赖数据库或API）"""

    def test_calculate_hdp_settlement_home_win(self, calculator: AutoSettlementCalculator):
        """测试让球盘计算：主队让半球，比分2-1"""
        result = calculator.calculate_hdp_settlement(
            score="2-1", handicap_raw="半球", home_rate=0.85, away_rate=1.00
        )
        # 主队让球，净胜1 > 0.5，结果应该是客贏（即下主队的赢）
        assert result["settlement"] == "客贏"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "win"
        assert result["home_away_direction"] == "home"

    def test_calculate_hdp_settlement_away_win_with_star(
        self, calculator: AutoSettlementCalculator
    ):
        """测试让球盘计算：客队让半球（带*标记），比分1-2"""
        result = calculator.calculate_hdp_settlement(
            score="1-2", handicap_raw="*半球", home_rate=1.00, away_rate=0.85
        )
        # 客队让球，客队净胜1 > 0.5，结果应该是主贏
        assert result["settlement"] == "主贏"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "win"
        assert result["home_away_direction"] == "away"

    def test_calculate_hdp_settlement_half_win(self, calculator: AutoSettlementCalculator):
        """测试让球盘计算：主队让平/半，比分1-0"""
        result = calculator.calculate_hdp_settlement(
            score="1-0", handicap_raw="平/半", home_rate=0.85, away_rate=1.00
        )
        # 主队让球，净胜1 > 0.25，结果应该是客贏
        assert result["settlement"] == "客贏"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "win"
        assert result["home_away_direction"] == "home"

    def test_calculate_hdp_settlement_draw_with_handicap(
        self, calculator: AutoSettlementCalculator
    ):
        """测试让球盘计算：主队让半球，比分1-1"""
        result = calculator.calculate_hdp_settlement(
            score="1-1", handicap_raw="半球", home_rate=0.85, away_rate=1.00
        )
        # 主队让球，净胜0 < 0.5，结果应该是客輸
        assert result["settlement"] == "客輸"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "lose"
        assert result["home_away_direction"] == "home"

    def test_calculate_ou_settlement_over_win(self, calculator: AutoSettlementCalculator):
        """测试大小球计算：盘口2.5，总进球3，应大贏"""
        result = calculator.calculate_ou_settlement(score="2-1", handicap_raw="2.5")
        assert result["settlement"] == "大贏"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "win"

    def test_calculate_ou_settlement_under_win(self, calculator: AutoSettlementCalculator):
        """测试大小球计算：盘口2.5，总进球2，应小贏"""
        result = calculator.calculate_ou_settlement(score="1-1", handicap_raw="2.5")
        assert result["settlement"] == "小贏"
        assert result["settlement_value"] == 1.0
        assert result["settlement_direction"] == "win"

    def test_calculate_ou_settlement_over_half_win(
        self, calculator: AutoSettlementCalculator
    ):
        """测试大小球计算：盘口2.75，总进球3，应大贏半"""
        result = calculator.calculate_ou_settlement(score="2-1", handicap_raw="2.75")
        assert result["settlement"] == "大贏半"
        assert result["settlement_value"] == 0.5
        assert result["settlement_direction"] == "win"

    def test_calculate_ou_settlement_under_half_lose(
        self, calculator: AutoSettlementCalculator
    ):
        """测试大小球计算：盘口2.25，总进球2，应小輸半"""
        result = calculator.calculate_ou_settlement(score="1-1", handicap_raw="2.25")
        assert result["settlement"] == "小輸半"
        assert result["settlement_value"] == 0.5
        assert result["settlement_direction"] == "lose"

    def test_calculate_ou_settlement_push(self, calculator: AutoSettlementCalculator):
        """测试大小球计算：盘口2.0，总进球2，应走盘"""
        result = calculator.calculate_ou_settlement(score="1-1", handicap_raw="2.0")
        assert result["settlement"] == "走"
        assert result["settlement_value"] == 0.0
        assert result["settlement_direction"] == ""

    def test_normalize_handicap_receive(self, calculator: AutoSettlementCalculator):
        """测试盘口标准化：受让盘"""
        handicap = calculator.normalize_handicap("受让半球")
        assert handicap == -0.5

    def test_normalize_handicap_with_star(self, calculator: AutoSettlementCalculator):
        """测试盘口标准化：带*标记的盘口"""
        handicap = calculator.normalize_handicap("*半球")
        assert handicap == 0.5

    def test_parse_score_valid(self, calculator: AutoSettlementCalculator):
        """测试比分解析：有效比分"""
        score = calculator.parse_score("2-1")
        assert score == (2, 1)

    def test_parse_score_invalid(self, calculator: AutoSettlementCalculator):
        """测试比分解析：无效格式"""
        score = calculator.parse_score("无效比分")
        assert score is None
