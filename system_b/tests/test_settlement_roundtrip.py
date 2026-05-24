"""Round-trip tests: AutoSettlementCalculator generates settlement text,
SettlementCalculator parses it back — verifying consistency (or documenting gaps).

Known issue: AutoSettlementCalculator outputs simplified Chinese (赢/输) while
SettlementCalculator expects traditional (贏/輸). This character mismatch means
the parser rejects generated text as "anomalous". These cases are marked xfail.
"""

import pytest
from modules.settlement_calculator import AutoSettlementCalculator
from core.settlement import SettlementCalculator
from core.models import MatchRecord


@pytest.fixture
def auto_calc():
    return AutoSettlementCalculator()


@pytest.fixture
def parser():
    return SettlementCalculator()


# ── Exhaustive HANDICAP_MAP coverage ─────────────────────────────────

class TestHandicapMapExhaustive:
    """Every entry in HANDICAP_MAP must normalize correctly."""

    ALL_ENTRIES = [
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
    ]

    @pytest.mark.parametrize("raw,expected", ALL_ENTRIES)
    def test_map_entry(self, auto_calc, raw, expected):
        assert auto_calc.normalize_handicap(raw) == expected

    def test_receive_all_map_entries(self, auto_calc):
        for raw, val in self.ALL_ENTRIES:
            if val == 0.0:
                continue
            assert auto_calc.normalize_handicap(f"受让{raw}") == -val

    def test_star_stripped(self, auto_calc):
        """* prefix is stripped before normalization (system_b only — system_a has this bug)."""
        assert auto_calc.normalize_handicap("*半球") == 0.5
        assert auto_calc.normalize_handicap("*平/半") == 0.25


# ── All HDP settlement branches ──────────────────────────────────────

class TestHDPAllBranches:
    """Cover every code path in calculate_hdp_settlement."""

    def test_invalid_score(self, auto_calc):
        r = auto_calc.calculate_hdp_settlement("", "半球", 0.85, 1.00)
        assert r["settlement"] == ""
        assert "error" in r

    def test_invalid_handicap(self, auto_calc):
        r = auto_calc.calculate_hdp_settlement("2-1", "xyz", 0.85, 1.00)
        assert r["settlement"] == ""
        assert "error" in r

    # ── has_star=True branch (away is favored) ──

    def test_star_away_win_full(self, auto_calc):
        """*半球, score 1-2: away nets +1 > 0.5 → 主赢."""
        r = auto_calc.calculate_hdp_settlement("1-2", "*半球", 1.00, 0.85)
        assert r["settlement"] == "主贏"
        assert r["settlement_value"] == 1.0
        assert r["home_away_direction"] == "away"

    def test_star_away_lose_full(self, auto_calc):
        """*半球, score 1-1: away nets 0 < 0.5 → 主输."""
        r = auto_calc.calculate_hdp_settlement("1-1", "*半球", 1.00, 0.85)
        assert r["settlement"] == "主輸"
        assert r["settlement_value"] == 1.0

    def test_star_away_push_exact(self, auto_calc):
        """*一球, score 1-2: away nets +1 = 1.0 → 走."""
        r = auto_calc.calculate_hdp_settlement("1-2", "*一球", 1.00, 0.85)
        assert r["settlement"] == "走"
        assert r["settlement_value"] == 0.0

    def test_star_away_half_win(self, auto_calc):
        """*半/一(0.75), score 1-2: away nets +1, diff=0.25 → 主贏半."""
        r = auto_calc.calculate_hdp_settlement("1-2", "*半/一", 1.00, 0.85)
        assert r["settlement"] == "主贏半"
        assert r["settlement_value"] == 0.5

    def test_star_away_half_lose(self, auto_calc):
        """*平/半(0.25), score 1-1: away nets 0, diff=0.25 → 主輸半."""
        r = auto_calc.calculate_hdp_settlement("1-1", "*平/半", 1.00, 0.85)
        assert r["settlement"] == "主輸半"
        assert r["settlement_value"] == 0.5

    # ── has_star=False branch (home is favored) ──

    def test_no_star_home_win_full(self, auto_calc):
        """半球, score 2-1: home nets +1 > 0.5 → 客赢."""
        r = auto_calc.calculate_hdp_settlement("2-1", "半球", 0.85, 1.00)
        assert r["settlement"] == "客贏"
        assert r["home_away_direction"] == "home"

    def test_no_star_home_lose_full(self, auto_calc):
        r = auto_calc.calculate_hdp_settlement("1-1", "半球", 0.85, 1.00)
        assert r["settlement"] == "客輸"

    def test_no_star_home_push_exact(self, auto_calc):
        r = auto_calc.calculate_hdp_settlement("2-1", "一球", 0.85, 1.00)
        assert r["settlement"] == "走"

    def test_no_star_home_half_win(self, auto_calc):
        """半/一(0.75), score 1-0: home nets +1, diff=0.25 → 客贏半."""
        r = auto_calc.calculate_hdp_settlement("1-0", "半/一", 0.85, 1.00)
        assert r["settlement"] == "客贏半"

    def test_no_star_home_half_lose(self, auto_calc):
        """平/半(0.25), score 0-0: home nets 0, diff=0.25 → 客輸半."""
        r = auto_calc.calculate_hdp_settlement("0-0", "平/半", 0.85, 1.00)
        assert r["settlement"] == "客輸半"

    # ── 受让 prefix (same as star, away favored) ──

    def test_receive_away_favored(self, auto_calc):
        """受让半球: same as *半球, away favored."""
        r = auto_calc.calculate_hdp_settlement("1-2", "受让半球", 1.00, 0.85)
        assert r["settlement"] == "主贏"
        assert r["home_away_direction"] == "away"

    # ── Cross-check system_a value ranges ──

    def test_value_never_exceeds_one(self, auto_calc):
        """All HDP results must have settlement_value in {0.0, 0.5, 1.0}."""
        test_cases = [
            ("2-1", "半球"), ("1-1", "半球"), ("2-1", "一球"),
            ("1-0", "半/一"), ("0-0", "平/半"),
            ("1-2", "*半球"), ("1-1", "*半球"), ("1-2", "*一球"),
        ]
        for score, handicap in test_cases:
            r = auto_calc.calculate_hdp_settlement(score, handicap, 0.85, 1.00)
            assert r["settlement_value"] in (0.0, 0.5, 1.0), (
                f"Invalid value {r['settlement_value']} for {score} + {handicap}"
            )


# ── All OU settlement branches ───────────────────────────────────────

class TestOUAllBranches:
    """Cover every code path in calculate_ou_settlement."""

    def test_invalid_score(self, auto_calc):
        r = auto_calc.calculate_ou_settlement("", "2.5")
        assert r["settlement"] == ""
        assert "error" in r

    def test_invalid_handicap(self, auto_calc):
        r = auto_calc.calculate_ou_settlement("2-1", "xyz")
        assert r["settlement"] == ""
        assert "error" in r

    def test_over_win(self, auto_calc):
        r = auto_calc.calculate_ou_settlement("2-1", "2.5")
        assert r["settlement"] == "大贏"
        assert r["settlement_value"] == 1.0

    def test_under_win(self, auto_calc):
        r = auto_calc.calculate_ou_settlement("1-1", "2.5")
        assert r["settlement"] == "小贏"
        assert r["settlement_value"] == 1.0

    def test_push(self, auto_calc):
        r = auto_calc.calculate_ou_settlement("1-1", "2.0")
        assert r["settlement"] == "走"

    def test_over_half_win(self, auto_calc):
        """2.75 line, total 3: diff=0.25 over → 大贏半."""
        r = auto_calc.calculate_ou_settlement("2-1", "2.75")
        assert r["settlement"] == "大贏半"
        assert r["settlement_value"] == 0.5

    def test_under_half_lose(self, auto_calc):
        """2.25 line, total 2: diff=0.25 under → 小輸半."""
        r = auto_calc.calculate_ou_settlement("1-1", "2.25")
        assert r["settlement"] == "小輸半"
        assert r["settlement_value"] == 0.5

    def test_over_full_win(self, auto_calc):
        """2.25 line, total 3: diff=0.75 over → 大赢 (full, not half)."""
        r = auto_calc.calculate_ou_settlement("2-1", "2.25")
        assert r["settlement"] == "大贏"

    def test_value_never_exceeds_one(self, auto_calc):
        """All OU results must have settlement_value in {0.0, 0.5, 1.0}."""
        test_cases = [
            ("2-1", "2.5"), ("1-1", "2.5"), ("1-1", "2.0"),
            ("2-1", "2.75"), ("1-1", "2.25"),
        ]
        for score, handicap in test_cases:
            r = auto_calc.calculate_ou_settlement(score, handicap)
            assert r["settlement_value"] in (0.0, 0.5, 1.0), (
                f"Invalid value {r['settlement_value']} for {score} + {handicap}"
            )


# ── Character encoding consistency ───────────────────────────────────

class TestCharacterEncoding:
    """The two settlement modules use different character sets for
    settlement text. This documents the current state."""

    SIMPLIFIED_WIN = "赢"
    SIMPLIFIED_LOSE = "输"
    TRADITIONAL_WIN = "贏"
    TRADITIONAL_LOSE = "輸"

    def test_auto_calc_uses_traditional(self, auto_calc):
        """AutoSettlementCalculator outputs traditional Chinese."""
        r = auto_calc.calculate_hdp_settlement("2-1", "半球", 0.85, 1.00)
        assert self.TRADITIONAL_WIN in r["settlement"]

    def test_parser_expects_traditional(self, parser):
        """SettlementCalculator's valid set uses traditional Chinese."""
        from core.settlement import _VALID_HDP, _VALID_OU
        for text in _VALID_HDP:
            assert self.TRADITIONAL_WIN in text or self.TRADITIONAL_LOSE in text or text == "走"
        for text in _VALID_OU:
            assert self.TRADITIONAL_WIN in text or self.TRADITIONAL_LOSE in text or text == "走"

    def test_roundtrip_characters_match(self, auto_calc, parser):
        """Generated text should be parseable by SettlementCalculator."""
        r = auto_calc.calculate_hdp_settlement("2-1", "半球", 0.85, 1.00)
        rec = MatchRecord(
            round_num=1, x_value=0.0,
            settlement=r["settlement"], play_type="HDP",
            home_team="主队测试", away_team="客队测试",
        )
        parser.calculate([rec])
        # If the characters matched, this would pass
        assert rec.settlement_value != 0.0, "Round-trip should preserve settlement value"
