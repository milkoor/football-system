"""Tests for system_a handicap_normalizer — covers all 50+ handicap terms."""

import pytest
from scraper.handicap_normalizer import HandicapNormalizer


class TestHandicapNormalizer:
    """Tests for HandicapNormalizer.normalize() — covering all terms in HANDICAP_MAP."""

    # ── 基础盘口 (basic terms) ──

    @pytest.mark.parametrize("text,expected", [
        ("平手", 0.0), ("平/半", 0.25), ("平手/半球", 0.25),
        ("半球", 0.5),
        ("半/一", 0.75), ("半球/一球", 0.75),
        ("一球", 1.0),
        ("一/球半", 1.25), ("一球/球半", 1.25),
        ("球半", 1.5),
    ])
    def test_basic_handicaps(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    # ── 繁体盘口 1.75~6.0 ──

    @pytest.mark.parametrize("text,expected", [
        ("球半/兩球", 1.75), ("兩球", 2.0),
        ("兩球/兩球半", 2.25), ("兩球半", 2.5),
        ("兩球半/三球", 2.75), ("三球", 3.0),
        ("三球/三球半", 3.25), ("三球半", 3.5),
        ("三球半/四球", 3.75), ("四球", 4.0),
        ("四球/四球半", 4.25), ("四球半", 4.5),
        ("四球半/五球", 4.75), ("五球", 5.0),
        ("五球/五球半", 5.25), ("五球半", 5.5),
        ("五球半/六球", 5.75), ("六球", 6.0),
    ])
    def test_traditional_handicaps(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    # ── 简体盘口 1.75~6.0 ──

    @pytest.mark.parametrize("text,expected", [
        ("球半/两", 1.75), ("球半/两球", 1.75), ("两球", 2.0),
        ("两球/两球半", 2.25), ("两球半", 2.5),
        ("两球半/三球", 2.75), ("三球", 3.0),
        ("三球/三球半", 3.25), ("三球半", 3.5),
        ("三球半/四球", 3.75), ("四球", 4.0),
        ("四球/四球半", 4.25), ("四球半", 4.5),
        ("四球半/五球", 4.75), ("五球", 5.0),
        ("五球/五球半", 5.25), ("五球半", 5.5),
        ("五球半/六球", 5.75), ("六球", 6.0),
    ])
    def test_simplified_handicaps(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    # ── 受让 (receive/underdog) 盘口 ──

    @pytest.mark.parametrize("text,expected", [
        ("受让平手", -0.0),
        ("受讓平手", -0.0),
        ("受平手", -0.0),
        ("受让半球", -0.5),
        ("受讓半球", -0.5),
        ("受半球", -0.5),
        ("受让平/半", -0.25),
        ("受讓平/半", -0.25),
        ("受平/半", -0.25),
        ("受让一球", -1.0),
        ("受让球半", -1.5),
        ("受让一/球半", -1.25),
        ("受让兩球半/三球", -2.75),
    ])
    def test_receive_handicaps(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    # ── 数字型盘口 ──

    @pytest.mark.parametrize("text,expected", [
        ("0.5", 0.5), ("1.0", 1.0), ("2.5", 2.5),
        ("1.25", 1.25), ("1.75", 1.75), ("3.0", 3.0),
        ("0.25", 0.25),
        ("2.5/3", 2.75), ("3/3.5", 3.25),
        ("1.5/2", 1.75), ("0.5/1", 0.75),
        ("3.5/4", 3.75), ("4.5/5", 4.75),
    ])
    def test_numeric_handicaps(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    def test_receive_numeric(self):
        assert HandicapNormalizer.normalize("受让1.5") == -1.5
        assert HandicapNormalizer.normalize("受让2.5/3") == -2.75
        assert HandicapNormalizer.normalize("受讓1.0") == -1.0

    # ── 边缘情况 ──

    @pytest.mark.parametrize("text,expected", [
        ("", None),
        (None, None),
        ("   ", None),
        (" 半球 ", 0.5),
        ("半  球", 0.5),
        ("xyz", None),
        ("abc/def", None),
        ("////", None),
    ])
    def test_edge_cases(self, text, expected):
        assert HandicapNormalizer.normalize(text) == expected

    # ── 空格处理 ──

    def test_whitespace_handling(self):
        assert HandicapNormalizer.normalize(" 半球 ") == 0.5
        assert HandicapNormalizer.normalize("平 / 半") == 0.25
        assert HandicapNormalizer.normalize(" 受让 半球 ") == -0.5

    # ── parse_handicap_raw ──

    def test_parse_handicap_raw(self):
        val, raw = HandicapNormalizer.parse_handicap_raw("半球")
        assert val == 0.5
        assert raw == "半球"

    def test_parse_handicap_raw_empty(self):
        val, raw = HandicapNormalizer.parse_handicap_raw("")
        assert val is None
        assert raw == ""
