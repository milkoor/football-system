"""Tests for system_a team_normalizer — covers 140+ team name mappings."""

import pytest
from scraper.team_normalizer import TeamNameNormalizer


class TestTeamNameNormalizer:
    """Tests for TeamNameNormalizer — simplified↔traditional team name conversion."""

    # ── to_traditional (简体→繁体) ──

    @pytest.mark.parametrize("simp,trad", [
        # 英格兰
        ("曼联", "曼聯"), ("阿森纳", "阿仙奴"), ("切尔西", "車路士"),
        ("热刺", "熱刺"), ("曼城", "曼城"),
        ("纽卡斯尔", "紐卡素"), ("布莱顿", "白禮頓"),
        ("富勒姆", "富咸"), ("水晶宫", "水晶宮"),
        ("埃弗顿", "愛華頓"), ("狼队", "狼隊"),
        ("伯恩茅斯", "般尼茅夫"), ("西汉姆", "韋斯咸"),
        ("阿斯顿维拉", "阿士東維拉"), ("诺丁汉森林", "諾定咸森林"),
        ("谢菲尔德联", "錫菲聯"), ("卢顿", "盧頓"),
        # 西班牙
        ("皇马", "皇家馬德里"), ("巴萨", "巴塞隆拿"),
        ("马竞", "馬德里體育會"), ("塞维利亚", "西維爾"),
        ("瓦伦西亚", "華倫西亞"), ("毕尔巴鄂", "畢爾包"),
        ("皇家社会", "皇家蘇斯達"), ("比利亚雷亚尔", "維拉利爾"),
        ("贝蒂斯", "貝迪斯"), ("奥萨苏纳", "奧沙辛拿"),
        # 意大利
        ("尤文图斯", "祖雲達斯"), ("国米", "國際米蘭"),
        ("AC米兰", "AC米蘭"), ("罗马", "羅馬"),
        ("那不勒斯", "拿玻里"), ("佛罗伦萨", "費倫天拿"),
        ("亚特兰大", "阿特蘭大"), ("拉齐奥", "拉素"),
        ("都灵", "拖連奴"), ("博洛尼亚", "博洛尼亞"),
        # 德国
        ("拜仁", "拜仁慕尼黑"), ("多特蒙德", "多蒙特"),
        ("莱比锡", "萊比錫"), ("勒沃库森", "利華古遜"),
        ("法兰克福", "法蘭克福"), ("弗赖堡", "費雷堡"),
        ("沃尔夫斯堡", "禾夫斯堡"), ("门兴", "慕遼加柏"),
        ("霍芬海姆", "賀芬咸"), ("斯图加特", "史特加"),
        # 法国
        ("巴黎", "巴黎聖日門"), ("马赛", "馬賽"),
        ("里昂", "里昂"), ("摩纳哥", "摩納哥"),
        ("里尔", "里爾"),
        # 日本
        ("川崎前锋", "川崎前鋒"), ("横滨水手", "橫濱水手"),
        ("鹿岛鹿角", "鹿島鹿角"), ("大阪钢巴", "大阪鋼巴"),
        ("浦和红钻", "浦和紅鑽"),
        # 荷甲
        ("阿贾克斯", "阿積士"), ("埃因霍温", "PSV燕豪芬"),
        ("费耶诺德", "費耶諾德"), ("阿尔克马尔", "阿爾克馬爾"),
        # 葡萄牙
        ("本菲卡", "賓菲加"), ("波尔图", "波圖"),
        ("葡萄牙体育", "士砵亭"),
        # 土耳其
        ("加拉塔萨雷", "加拉塔沙雷"), ("费内巴切", "費倫巴治"),
        ("贝西克塔斯", "比錫達斯"),
    ])
    def test_to_traditional(self, simp, trad):
        assert TeamNameNormalizer.to_traditional(simp) == trad

    # ── to_simplified (繁体→简体) ──

    @pytest.mark.parametrize("trad,simp", [
        ("曼聯", "曼联"), ("阿仙奴", "阿森纳"), ("車路士", "切尔西"),
        ("熱刺", "热刺"), ("紐卡素", "纽卡斯尔"),
        ("皇家馬德里", "皇马"), ("巴塞隆拿", "巴萨"),
        ("祖雲達斯", "尤文图斯"), ("國際米蘭", "国米"),
        ("拜仁慕尼黑", "拜仁"), ("多蒙特", "多特蒙德"),
        ("利華古遜", "勒沃库森"),
        ("巴黎聖日門", "巴黎"),
        ("阿積士", "阿贾克斯"),
        ("賓菲加", "本菲卡"),
    ])
    def test_to_simplified(self, trad, simp):
        assert TeamNameNormalizer.to_simplified(trad) == simp

    # ── normalize ──

    def test_normalize_to_traditional(self):
        assert TeamNameNormalizer.normalize("曼联", "tw") == "曼聯"
        assert TeamNameNormalizer.normalize("利物浦", "tw") == "利物浦"

    def test_normalize_to_simplified(self):
        assert TeamNameNormalizer.normalize("曼聯", "cn") == "曼联"
        assert TeamNameNormalizer.normalize("利物浦", "cn") == "利物浦"

    # ── 边缘情况 ──

    def test_empty_none(self):
        assert TeamNameNormalizer.to_traditional("") == ""
        assert TeamNameNormalizer.to_traditional(None) is None
        assert TeamNameNormalizer.to_simplified("") == ""
        assert TeamNameNormalizer.to_simplified(None) is None
        assert TeamNameNormalizer.normalize("", "tw") == ""
        assert TeamNameNormalizer.normalize(None, "tw") is None

    def test_pass_through_unknown(self):
        """Unknown team names should pass through unchanged."""
        assert TeamNameNormalizer.to_traditional("SomeUnknownTeam") == "SomeUnknownTeam"
        assert TeamNameNormalizer.to_simplified("SomeUnknownTeam") == "SomeUnknownTeam"
        assert TeamNameNormalizer.normalize("不存在的队名", "tw") == "不存在的队名"

    def test_already_traditional(self):
        """Already-traditional names should return as-is (no back-and-forth)."""
        assert TeamNameNormalizer.to_traditional("曼聯") == "曼聯"
        assert TeamNameNormalizer.to_traditional("車路士") == "車路士"

    def test_already_simplified_to_simplified(self):
        """Already-simplified names should return as-is."""
        assert TeamNameNormalizer.to_simplified("曼联") == "曼联"
