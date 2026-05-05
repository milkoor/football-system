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

系统B结算模块：
- 移除对系统A模块的直接导入
- 通过httpx调用系统A REST API
- 使用settings.system_a_api_url作为base URL
- 同时提供同步和异步接口
"""

import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import httpx

from config.settings import get_settings

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

    def __init__(self):
        """初始化"""
        self.settings = get_settings()
        self.base_url = self.settings.system_a_api_url

    def normalize_handicap(self, handicap_raw: str) -> Optional[float]:
        """标准化盘口"""
        if not handicap_raw:
            return None

        t = handicap_raw.strip().replace(" ", "")

        # 处理*标记（保留*信息供后续判断哪方让球使用，但在标准化时去除）
        has_star = "*" in t
        t = t.replace("*", "")

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
        has_star = "*" in handicap_raw or "受" in handicap_raw or "受让" in handicap_raw

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

    # ========== 同步接口 ==========

    def auto_settle_match(self, match_id: int) -> Dict[str, Any]:
        """自动结算单场比赛

        通过API调用系统A的自动结算功能
        """
        try:
            url = f"{self.base_url}/api/matches/{match_id}/auto-settle"
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"自动结算失败: match_id={match_id}, status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"自动结算HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"自动结算请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"自动结算失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    def batch_auto_settle(self, league_id: int = None, season: str = None) -> Dict[str, Any]:
        """批量自动结算

        通过API调用系统A的批量自动结算功能
        """
        try:
            url = f"{self.base_url}/api/matches/auto-settle"
            params = {}
            if league_id:
                params["league_id"] = league_id
            if season:
                params["season"] = season

            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=params)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"批量自动结算失败: league_id={league_id}, season={season}, "
                        f"status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"批量自动结算HTTP错误: error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"批量自动结算请求错误: error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"批量自动结算失败: error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    def get_settlement_result(self, match_id: int) -> Dict[str, Any]:
        """获取结算结果

        通过API调用系统A获取比赛的结算结果
        """
        try:
            url = f"{self.base_url}/api/matches/{match_id}/settlement"
            with httpx.Client(timeout=60.0) as client:
                response = client.get(url)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"获取结算结果失败: match_id={match_id}, status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"获取结算结果HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"获取结算结果请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取结算结果失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    def update_score_and_settle(self, match_id: int, score: str) -> Dict[str, Any]:
        """更新比分并结算

        通过API调用系统A更新比分并自动结算
        """
        try:
            url = f"{self.base_url}/api/matches/{match_id}/score"
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json={"score": score})

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"更新比分失败: match_id={match_id}, score={score}, "
                        f"status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"更新比分HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"更新比分请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"更新比分失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    # ========== 异步接口 ==========

    async def async_auto_settle_match(self, match_id: int) -> Dict[str, Any]:
        """异步自动结算单场比赛"""
        try:
            url = f"{self.base_url}/api/matches/{match_id}/auto-settle"
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"自动结算失败: match_id={match_id}, status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"自动结算HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"自动结算请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"自动结算失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    async def async_batch_auto_settle(self, league_id: int = None, season: str = None) -> Dict[str, Any]:
        """异步批量自动结算"""
        try:
            url = f"{self.base_url}/api/matches/auto-settle"
            params = {}
            if league_id:
                params["league_id"] = league_id
            if season:
                params["season"] = season

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=params)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"批量自动结算失败: league_id={league_id}, season={season}, "
                        f"status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"批量自动结算HTTP错误: error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"批量自动结算请求错误: error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"批量自动结算失败: error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    async def async_get_settlement_result(self, match_id: int) -> Dict[str, Any]:
        """异步获取结算结果"""
        try:
            url = f"{self.base_url}/api/matches/{match_id}/settlement"
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"获取结算结果失败: match_id={match_id}, status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"获取结算结果HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"获取结算结果请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"获取结算结果失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")

    async def async_update_score_and_settle(self, match_id: int, score: str) -> Dict[str, Any]:
        """异步更新比分并结算"""
        try:
            url = f"{self.base_url}/api/matches/{match_id}/score"
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json={"score": score})

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"更新比分失败: match_id={match_id}, score={score}, "
                        f"status={response.status_code}, detail={response.text}"
                    )
                    return self._empty_result(
                        f"API调用失败: {response.status_code} - {response.text}"
                    )

        except httpx.HTTPStatusError as e:
            logger.error(f"更新比分HTTP错误: match_id={match_id}, error={e}")
            return self._empty_result(f"HTTP错误: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"更新比分请求错误: match_id={match_id}, error={e}")
            return self._empty_result(f"连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"更新比分失败: match_id={match_id}, error={e}")
            return self._empty_result(f"系统错误: {str(e)}")
