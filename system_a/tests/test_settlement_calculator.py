"""Tests for system_a settlement calculator — including float comparison regression.

Covers: normalize_handicap, calculate_hdp_settlement, calculate_ou_settlement,
parse_score, _empty_result
"""

import math
import pytest
from modules.settlement_calculator import AutoSettlementCalculator


@pytest.fixture
def calc():
    return AutoSettlementCalculator()


# ── normalize_handicap ──────────────────────────────────────────────

class TestNormalizeHandicap:
    def test_empty_none(self, calc):
        assert calc.normalize_handicap("") is None
        assert calc.normalize_handicap(None) is None

    @pytest.mark.parametrize("raw,expected", [
        ("平手", 0.0), ("平手盘", 0.0), ("0", 0.0),
        ("平/半", 0.25), ("平手/半球", 0.25),
        ("半球", 0.5),
        ("半/一", 0.75), ("半球/一球", 0.75),
        ("一球", 1.0),
        ("一/球半", 1.25), ("一球/球半", 1.25),
        ("球半", 1.5),
        ("球半/兩球", 1.75), ("兩球", 2.0),
        ("兩球/兩球半", 2.25), ("兩球半", 2.5),
        ("兩球半/三球", 2.75), ("三球", 3.0),
    ])
    def test_known_handicaps(self, calc, raw, expected):
        assert calc.normalize_handicap(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("受让半球", -0.5),
        ("受讓半球", -0.5),
        ("受半球", -0.5),
        ("受让平/半", -0.25),
        ("受讓平/半", -0.25),
        ("受平/半", -0.25),
        ("受让一球", -1.0),
        ("受让球半", -1.5),
    ])
    def test_receive_handicaps(self, calc, raw, expected):
        assert calc.normalize_handicap(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("2.5", 2.5),
        ("1.75", 1.75),
        ("0.5", 0.5),
        ("3.0", 3.0),
    ])
    def test_numeric_handicaps(self, calc, raw, expected):
        assert calc.normalize_handicap(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("2.5/3", 2.75),
        ("1.5/2", 1.75),
        ("0.5/1", 0.75),
    ])
    def test_fraction_handicaps(self, calc, raw, expected):
        assert calc.normalize_handicap(raw) == expected

    def test_receive_numeric(self, calc):
        assert calc.normalize_handicap("受让1.5") == -1.5


# ── parse_score ─────────────────────────────────────────────────────

class TestParseScore:
    def test_valid(self, calc):
        assert calc.parse_score("2-1") == (2, 1)
        assert calc.parse_score("0-0") == (0, 0)
        assert calc.parse_score("10-3") == (10, 3)

    def test_invalid(self, calc):
        assert calc.parse_score("") is None
        assert calc.parse_score(None) is None
        assert calc.parse_score("无效比分") is None
        assert calc.parse_score("2-1-3") is None
        assert calc.parse_score("abc-def") is None


# ── calculate_hdp_settlement ────────────────────────────────────────

class TestCalculateHDPSettlement:
    """Tests for HDP settlement — includes regression for float == 0.25 bug."""

    def test_home_win_by_more_than_handicap(self, calc):
        """主队让半球，比分2-1 — 主队净胜1 > 0.5 → 客赢"""
        r = calc.calculate_hdp_settlement("2-1", "半球", 0.85, 1.00)
        assert r["settlement"] == "客赢"
        assert r["settlement_value"] == 1.0
        assert r["settlement_direction"] == "win"
        assert r["home_away_direction"] == "home"

    def test_home_lose_against_handicap(self, calc):
        """主队让半球，比分1-1 — 主队净胜0 < 0.5 → 客输"""
        r = calc.calculate_hdp_settlement("1-1", "半球", 0.85, 1.00)
        assert r["settlement"] == "客输"
        assert r["settlement_value"] == 1.0
        assert r["settlement_direction"] == "lose"
        assert r["home_away_direction"] == "home"

    @pytest.mark.xfail(
        reason="BUG: system_a normalize_handicap does not strip '*' prefix; "
               "returns None for '*半球', causing settlement to fail. "
               "Fixed in system_b version."
    )
    def test_away_win_with_star(self, calc):
        """*半球（客队让半球），比分1-2 — 客队净胜1 > 0.5 → 主赢"""
        r = calc.calculate_hdp_settlement("1-2", "*半球", 1.00, 0.85)
        assert r["settlement"] == "主赢"
        assert r["settlement_value"] == 1.0
        assert r["settlement_direction"] == "win"
        assert r["home_away_direction"] == "away"

    def test_away_win_with_receive(self, calc):
        """受让半球（客队让半球），比分1-2 → 主赢"""
        r = calc.calculate_hdp_settlement("1-2", "受让半球", 1.00, 0.85)
        assert r["settlement"] == "主赢"
        assert r["settlement_value"] == 1.0
        assert r["home_away_direction"] == "away"

    def test_push_exact(self, calc):
        """主队让一球，比分2-1 — 净胜=1=盘口 → 走"""
        r = calc.calculate_hdp_settlement("2-1", "一球", 0.85, 1.00)
        assert r["settlement"] == "走"
        assert r["settlement_value"] == 0.0
        assert r["settlement_direction"] == ""

    # ── 半赢/半输 回归测试 (float == 0.25 bug) ──

    def test_half_win_quarter_handicap(self, calc):
        """主队让平/半(0.25)，比分1-0 — 净胜1.0, diff=0.75 → 全赢(客赢)"""
        r = calc.calculate_hdp_settlement("1-0", "平/半", 0.85, 1.00)
        assert r["settlement"] == "客赢"
        assert r["settlement_value"] == 1.0

    def test_half_lose_quarter_handicap(self, calc):
        """主队让平/半(0.25)，比分0-0 — 净胜0, diff=0.25 → 半输(客输半)"""
        r = calc.calculate_hdp_settlement("0-0", "平/半", 0.85, 1.00)
        assert r["settlement"] == "客输半"
        assert r["settlement_value"] == 0.5
        assert r["settlement_direction"] == "lose"

    def test_half_win_half_one_handicap(self, calc):
        """主队让半/一(0.75)，比分1-0 — 净胜1.0, diff=0.25 → 半赢(客赢半)"""
        r = calc.calculate_hdp_settlement("1-0", "半/一", 0.85, 1.00)
        assert r["settlement"] == "客赢半"
        assert r["settlement_value"] == 0.5
        assert r["settlement_direction"] == "win"

    def test_half_win_one_quarter_handicap(self, calc):
        """主队让一/球半(1.25)，比分2-0 — 净胜2.0, diff=0.75 → 全赢(客赢)"""
        r = calc.calculate_hdp_settlement("2-0", "一/球半", 0.85, 1.00)
        assert r["settlement"] == "客赢"
        assert r["settlement_value"] == 1.0

    def test_half_win_one_quarter_handicap_marginal(self, calc):
        """主队让一/球半(1.25)，比分2-1 — 净胜1.0, diff=0.25 → 半输(客输半)"""
        r = calc.calculate_hdp_settlement("2-1", "一/球半", 0.85, 1.00)
        assert r["settlement"] == "客输半"
        assert r["settlement_value"] == 0.5

    # ── 已知浮点Bug回归：净胜球与盘口差可能因浮点误差导致0.25比较失败 ──

    def test_float_precision_regression_1(self, calc):
        """盘口0.5/1 (0.75), 比分1-0 — diff应该≈0.25，半赢分支必须命中"""
        r = calc.calculate_hdp_settlement("1-0", "0.5/1", 0.85, 1.00)
        assert r["settlement"] in ("客赢半", "客赢")
        # diff = |1.0 - 0.75| = 0.25, should hit half-win
        assert r["settlement"] == "客赢半", (
            f"FLOAT BUG REGRESSION: expected 客赢半, got {r['settlement']}. "
            f"diff={abs(1.0 - 0.75)} should be detected as ≈0.25"
        )

    def test_float_precision_regression_2(self, calc):
        """盘口1.5/2 (1.75), 比分2-0 — diff = |2.0 - 1.75| ≈ 0.25"""
        r = calc.calculate_hdp_settlement("2-0", "1.5/2", 0.85, 1.00)
        assert r["settlement"] == "客赢半", (
            f"FLOAT BUG: diff = |2.0 - 1.75| should be 0.25 but float may differ"
        )

    def test_float_precision_regression_3(self, calc):
        """盘口2.5/3 (2.75), 比分3-0 — diff = |3.0 - 2.75| ≈ 0.25"""
        r = calc.calculate_hdp_settlement("3-0", "2.5/3", 0.85, 1.00)
        assert r["settlement"] == "客赢半"

    def test_float_precision_regression_4(self, calc):
        """盘口2.5/3 (2.75), 比分1-0 — diff = |1.0 - 2.75| ≈ 1.75 > 0.25, should be full loss"""
        r = calc.calculate_hdp_settlement("1-0", "2.5/3", 0.85, 1.00)
        assert r["settlement"] == "客输"
        assert r["settlement_value"] == 1.0

    # ── 数学证明：浮点误差场景 ──

    def test_all_marginal_diff_scenarios(self, calc):
        """For all fraction handicaps, test the exact-diff-0.25 scenario to ensure float bug doesn't exist."""
        test_cases = [
            # (handicap_raw, handicap_value, score, expected_settlement)
            ("平/半", 0.25, "0-0", "客输半"),  # home lets 0.25, draw
            ("平/半", 0.25, "1-0", "客赢"),    # home lets 0.25, home wins
            ("半/一", 0.75, "1-0", "客赢半"),  # home lets 0.75, home wins by 1
            ("半/一", 0.75, "2-0", "客赢"),    # home lets 0.75, home wins by 2
            ("一/球半", 1.25, "1-0", "客输半"), # home lets 1.25, home wins by 1
            ("一/球半", 1.25, "1-0", "客输半"), # home lets 1.25, home wins by 1, diff=0.25
            ("球半/兩球", 1.75, "2-0", "客赢半"), # home lets 1.75, home wins by 2, diff=0.25
            ("球半/兩球", 1.75, "3-0", "客赢"),   # home lets 1.75, home wins by 3
            ("兩球/兩球半", 2.25, "2-0", "客输半"), # home lets 2.25, home wins by 2
            ("兩球/兩球半", 2.25, "2-0", "客输半"), # home lets 2.25, home wins by 2, diff=0.25
            ("兩球半/三球", 2.75, "3-0", "客赢半"), # home lets 2.75, home wins by 3, diff=0.25
            ("兩球半/三球", 2.75, "4-0", "客赢"),   # home lets 2.75, home wins by 4
        ]
        for raw, _, score, expected in test_cases:
            r = calc.calculate_hdp_settlement(score, raw, 0.85, 1.00)
            assert r["settlement"] == expected, (
                f"FLOAT BUG for {raw} + {score}: expected {expected}, got {r['settlement']}"
            )

    def test_invalid_score(self, calc):
        r = calc.calculate_hdp_settlement("无效", "半球", 0.85, 1.00)
        assert "error" in r
        assert r["settlement"] == ""

    def test_invalid_handicap(self, calc):
        r = calc.calculate_hdp_settlement("2-1", "xyz", 0.85, 1.00)
        assert "error" in r
        assert r["settlement"] == ""


# ── calculate_ou_settlement ─────────────────────────────────────────

class TestCalculateOUSettlement:
    """Tests for OU settlement — includes regression for float == 0.25 bug."""

    def test_over_win(self, calc):
        r = calc.calculate_ou_settlement("2-1", "2.5")
        assert r["settlement"] == "大赢"
        assert r["settlement_value"] == 1.0
        assert r["settlement_direction"] == "win"

    def test_under_win(self, calc):
        r = calc.calculate_ou_settlement("1-1", "2.5")
        assert r["settlement"] == "小赢"
        assert r["settlement_value"] == 1.0

    def test_push(self, calc):
        r = calc.calculate_ou_settlement("1-1", "2.0")
        assert r["settlement"] == "走"
        assert r["settlement_value"] == 0.0

    def test_over_half_win(self, calc):
        """盘口2.75，总进球3 — diff=0.25 → 大赢半"""
        r = calc.calculate_ou_settlement("2-1", "2.75")
        assert r["settlement"] == "大赢半"
        assert r["settlement_value"] == 0.5

    def test_under_half_lose(self, calc):
        """盘口2.25，总进球2 — diff=0.25 → 小输半"""
        r = calc.calculate_ou_settlement("1-1", "2.25")
        assert r["settlement"] == "小输半"
        assert r["settlement_value"] == 0.5

    def test_float_precision_ou_regression(self, calc):
        """OU float bug regression: 盘口2.5/3 (2.75), 总进球3, diff=0.25 → 大赢半"""
        r = calc.calculate_ou_settlement("2-1", "2.5/3")
        assert r["settlement"] == "大赢半", (
            f"FLOAT BUG OU: expected 大赢半, got {r['settlement']}"
        )

    def test_ou_marginal_all(self, calc):
        test_cases = [
            ("2.25", "2-0", "小输半"),   # total=2, diff=0.25
            ("2.25", "2-1", "大赢"),     # total=3, diff=0.75 — full win
            ("2.75", "2-1", "大赢半"),   # total=3, diff=0.25
            ("2.75", "2-2", "大赢"),     # total=4, diff=1.25
            ("2.75", "1-1", "小赢"),     # total=2 < 2.75, diff=0.75 — full under win
        ]
        for handicap, score, expected in test_cases:
            r = calc.calculate_ou_settlement(score, handicap)
            assert r["settlement"] == expected, (
                f"OU FLOAT BUG: handicap={handicap} score={score} expected={expected} got={r['settlement']}"
            )

    def test_invalid_score(self, calc):
        r = calc.calculate_ou_settlement("无效", "2.5")
        assert "error" in r
