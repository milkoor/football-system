"""自动结算计算器

根据比赛比分和盘口自动计算结算结果

结算逻辑：
1. HDP (让球盘):
   - 根据初始盘口的 * 标记判断哪方是让球方
   - 有 * 或 受 标记 = 客队让球（计算客队）
   - 无 * 标记 = 主队让球（计算主队）
   - 计算净胜球 = 进球数 - 失球数
   - 净胜球 > 盘口 → 赢
   - 净胜球 < 盘口 → 输
   - 净胜球 = 盘口 → 走
   - 净胜球 = 盘口 ± 0.25 → 半赢/半输

2. OU (大小球):
   - 总进球数 > 盘口 → 大赢
   - 总进球数 < 盘口 → 小赢
   - 总进球数 = 盘口 → 走
   - 总进球数 = 盘口 ± 0.25 → 半赢/半输
"""

import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from config.database import SessionLocal
from config.models import Match, OddsMovement

logger = logging.getLogger(__name__)


class AutoSettlementCalculator:
    """自动结算计算器"""

    # 盘口标准化映射
    HANDICAP_MAP = {
        "平手": 0.0, "平手盘": 0.0, "0": 0.0,
        "平/半": 0.25, "平手/半球": 0.25,
        "半球": 0.5,
        "半/一": 0.75, "半球/一球": 0.75,
        "一球": 1.0,
        "一/球半": 1.25, "一球/球半": 1.25,
        "球半": 1.5,
        "球半/兩球": 1.75, "兩球": 2.0,
        "兩球/兩球半": 2.25, "兩球半": 2.5,
        "兩球半/三球": 2.75, "三球": 3.0,
    }

    def normalize_handicap(self, handicap_raw: str) -> Optional[float]:
        """标准化盘口"""
        if not handicap_raw:
            return None

        t = handicap_raw.strip().replace(" ", "")

        # 处理受让
        is_receive = False
        if "受让" in t or "受讓" in t or "受" in t:
            is_receive = True
            t = t.replace("受让", "").replace("受讓", "").replace("受", "")

        # 查表
        if t in self.HANDICAP_MAP:
            value = self.HANDICAP_MAP[t]
            return -value if is_receive else value

        # 尝试解析数字型盘口
        try:
            if "/" in t:
                parts = t.split("/")
                value = (float(parts[0]) + float(parts[1])) / 2
            else:
                value = float(t)
            return -value if is_receive else value
        except (ValueError, IndexError):
            pass

        return None

    def parse_score(self, score_str: str) -> Optional[Tuple[int, int]]:
        """解析比分字符串，如 "2-1" -> (2, 1)"""
        if not score_str:
            return None

        try:
            parts = score_str.split("-")
            if len(parts) == 2:
                home = int(parts[0].strip())
                away = int(parts[1].strip())
                return (home, away)
        except (ValueError, IndexError):
            pass

        return None

    def calculate_hdp_settlement(
        self,
        score: str,
        handicap_raw: str,
        home_rate: float,
        away_rate: float,
    ) -> Dict[str, Any]:
        """计算让球盘结算

        Returns:
            {
                "settlement": "主赢" / "主赢半" / "主输半" / "主输" / "客赢" / "客赢半" / "客输半" / "客输" / "走",
                "settlement_value": 1.0 / 0.5 / 0.0,
                "settlement_direction": "win" / "lose" / "",
                "home_away_direction": "home" / "away" / "",
                "target_team": "主队名" / "客队名" / ""
            }
        """
        # 解析比分
        score_tuple = self.parse_score(score)
        if not score_tuple:
            return self._empty_result("比分解析失败")

        home_score, away_score = score_tuple

        # 解析盘口
        handicap = self.normalize_handicap(handicap_raw)
        if handicap is None:
            return self._empty_result("盘口解析失败")

        # 判断哪方让球
        # 有 * 或 受 标记 = 客队让球（客队是优势方）
        has_star = "*" in handicap_raw or "受" in handicap_raw

        if has_star:
            # 客队让球，计算客队净胜球
            net_goals = away_score - home_score
            target_is_home = False
            direction_prefix = "主"
            target_team_field = "away"
        else:
            # 主队让球，计算主队净胜球
            net_goals = home_score - away_score
            target_is_home = True
            direction_prefix = "客"
            target_team_field = "home"

        # 比较净胜球与盘口
        if net_goals > handicap:
            # 赢
            result = f"{direction_prefix}赢"
            direction = "win"
            value = 1.0
        elif net_goals < handicap:
            # 输
            result = f"{direction_prefix}输"
            direction = "lose"
            value = 1.0
        else:
            # 走盘
            result = "走"
            direction = ""
            value = 0.0

        # 处理半赢半输（净胜球与盘口差0.25的情况）
        diff = abs(net_goals - handicap)
        if diff == 0.25:
            if net_goals > handicap:
                # 半赢
                result = f"{direction_prefix}赢半"
                direction = "win"
                value = 0.5
            else:
                # 半输
                result = f"{direction_prefix}输半"
                direction = "lose"
                value = 0.5
        elif diff == 0.5:
            # 这种情况应该是全赢或全输，但某些盘口可能有特殊处理
            pass

        return {
            "settlement": result,
            "settlement_value": value,
            "settlement_direction": direction,
            "home_away_direction": target_team_field,
            "target_team": "" if target_is_home else "",  # 后续从数据库获取
        }

    def calculate_ou_settlement(
        self,
        score: str,
        handicap_raw: str,
    ) -> Dict[str, Any]:
        """计算大小球结算

        Returns:
            {
                "settlement": "大赢" / "大赢半" / "大输半" / "大输" / "小赢" / "小赢半" / "小输半" / "小输" / "走",
                "settlement_value": 1.0 / 0.5 / 0.0,
                "settlement_direction": "win" / "lose" / "",
                "home_away_direction": "home" / "away" / "",
                "target_team": "" (大小球不需要指定队伍)
            }
        """
        # 解析比分
        score_tuple = self.parse_score(score)
        if not score_tuple:
            return self._empty_result("比分解析失败")

        home_score, away_score = score_tuple
        total_goals = home_score + away_score

        # 解析盘口（大小球的盘口是大球的水位）
        handicap = self.normalize_handicap(handicap_raw)
        if handicap is None:
            return self._empty_result("盘口解析失败")

        # 比较总进球数与盘口
        if total_goals > handicap:
            result = "大赢"
            direction = "win"
            value = 1.0
        elif total_goals < handicap:
            result = "小赢"
            direction = "win"
            value = 1.0
        else:
            result = "走"
            direction = ""
            value = 0.0

        # 处理半赢半输
        diff = abs(total_goals - handicap)
        if diff == 0.25:
            if total_goals > handicap:
                result = "大赢半"
                direction = "win"
                value = 0.5
            else:
                result = "小输半"
                direction = "lose"
                value = 0.5
        elif diff == 0.5:
            if total_goals > handicap:
                result = "大赢"
                direction = "win"
                value = 1.0
            else:
                result = "小赢"
                direction = "win"
                value = 1.0

        return {
            "settlement": result,
            "settlement_value": value,
            "settlement_direction": direction,
            "home_away_direction": "",  # 大小球不需要
            "target_team": "",
        }

    def _empty_result(self, error: str) -> Dict[str, Any]:
        """返回空结果"""
        return {
            "settlement": "",
            "settlement_value": 0.0,
            "settlement_direction": "",
            "home_away_direction": "",
            "target_team": "",
            "error": error,
        }

    def auto_settle_match(self, match_id: int) -> Dict[str, Any]:
        """自动结算单场比赛

        从数据库获取比赛信息、赔率数据，计算结算结果并更新数据库
        """
        db = SessionLocal()

        try:
            # 获取比赛信息
            match = db.query(Match).filter(Match.match_id == match_id).first()
            if not match:
                return self._empty_result("比赛不存在")

            # 检查是否有比分
            if not match.score_ft:
                return self._empty_result("暂无比分")

            # 获取初始盘口（最早的那条赔率记录）
            earliest_odds = db.query(OddsMovement).filter(
                OddsMovement.match_id == match_id,
                OddsMovement.odds_type == "AH",
            ).order_by(OddsMovement.update_time.asc()).first()

            if not earliest_odds:
                return self._empty_result("暂无盘口数据")

            # 计算HDP结算
            hdp_result = self.calculate_hdp_settlement(
                score=match.score_ft,
                handicap_raw=earliest_odds.handicap_raw or "",
                home_rate=earliest_odds.home_rate or 0.0,
                away_rate=earliest_odds.away_rate or 0.0,
            )

            # 设置目标队伍
            if hdp_result.get("home_away_direction") == "home":
                hdp_result["target_team"] = match.home_team
            elif hdp_result.get("home_away_direction") == "away":
                hdp_result["target_team"] = match.away_team

            # 更新数据库
            match.settlement = hdp_result.get("settlement", "")
            match.settlement_value = hdp_result.get("settlement_value", 0.0)
            match.settlement_direction = hdp_result.get("settlement_direction", "")
            match.home_away_direction = hdp_result.get("home_away_direction", "")
            match.target_team = hdp_result.get("target_team", "")

            db.commit()

            logger.info(f"比赛 {match_id} 自动结算完成: {hdp_result.get('settlement')}")

            return {
                "match_id": match_id,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "score": match.score_ft,
                "handicap": earliest_odds.handicap_raw,
                **hdp_result,
            }

        except Exception as e:
            logger.error(f"自动结算失败: match_id={match_id}, error={e}")
            return self._empty_result(str(e))
        finally:
            db.close()

    def batch_auto_settle(self, league_id: int = None, season: str = None) -> Dict[str, Any]:
        """批量自动结算

        对指定联赛/赛季下所有有比分但未结算的比赛进行自动结算
        """
        db = SessionLocal()

        try:
            query = db.query(Match).filter(
                Match.score_ft.isnot(None),  # 有比分
                Match.settlement.is_(None),  # 未结算
            )

            if league_id:
                query = query.filter(Match.league_id == league_id)
            if season:
                query = query.filter(Match.season == season)

            matches = query.all()

            success = 0
            failed = 0
            results = []

            for match in matches:
                result = self.auto_settle_match(match.match_id)
                if "error" not in result:
                    success += 1
                else:
                    failed += 1
                results.append(result)

            return {
                "total": len(matches),
                "success": success,
                "failed": failed,
                "results": results,
            }

        finally:
            db.close()


if __name__ == "__main__":
    # 测试
    calc = AutoSettlementCalculator()

    # 测试让球盘
    result = calc.calculate_hdp_settlement(
        score="2-1",
        handicap_raw="半球",  # 主队让半球
        home_rate=0.85,
        away_rate=1.00,
    )
    print("主队让半球，比分2-1:", result)

    result = calc.calculate_hdp_settlement(
        score="1-2",
        handicap_raw="*半球",  # 客队让半球（标*）
        home_rate=1.00,
        away_rate=0.85,
    )
    print("客队让半球（*），比分1-2:", result)

    result = calc.calculate_hdp_settlement(
        score="2-1",
        handicap_raw="球半",  # 主队让球半
        home_rate=0.85,
        away_rate=1.00,
    )
    print("主队让球半，比分2-1:", result)