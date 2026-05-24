"""数据连接器模块

从系统 A API 拉取数据
"""

import logging
from typing import Optional, List, Dict, Any
import httpx
import re

from config.settings import get_settings
from modules.x_calculator import XValueCalculator

logger = logging.getLogger(__name__)
settings = get_settings()


class DataConnector:
    """系统 A API 数据连接器"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.system_a_api_url
        self.client = httpx.Client(timeout=120.0)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{path}"
        try:
            response = self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API 请求失败: {url}, error={e}")
            raise

    def ping(self) -> bool:
        """检查 System A 连通性"""
        try:
            self._request("GET", "/health")
            return True
        except Exception:
            return False

    def get_leagues(self, **kwargs) -> List[Dict]:
        """获取联赛列表"""
        params = {k: v for k, v in kwargs.items() if v is not None}
        result = self._request("GET", "/api/leagues", params=params)
        return result

    def get_seasons(self, league_id: int, **kwargs) -> List[Dict]:
        """获取赛季列表"""
        params = {k: v for k, v in kwargs.items() if v is not None}
        result = self._request("GET", f"/api/seasons/{league_id}", params=params)
        return result

    def get_matches(
        self,
        league_id: Optional[int] = None,
        season: Optional[str] = None,
        crawl_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """获取比赛列表"""
        params = {
            "page": page,
            "page_size": page_size,
        }
        if league_id is not None:
            params["league_id"] = league_id
        if season:
            params["season"] = season
        if crawl_status:
            params["crawl_status"] = crawl_status

        result = self._request("GET", "/api/matches", params=params)
        return result

    def get_match_odds(
        self,
        match_id: int,
        odds_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """获取比赛赔率变动"""
        params = {}
        if odds_type:
            params["odds_type"] = odds_type
        if status:
            params["status"] = status

        result = self._request("GET", f"/api/matches/{match_id}/odds", params=params)
        return result.get("movements", [])

    def trigger_crawl(
        self,
        league_id: Optional[int] = None,
        season_label: Optional[str] = None,
        match_ids: Optional[List[int]] = None
    ) -> Dict:
        """触发爬虫任务"""
        data = {}
        if league_id is not None:
            data["league_id"] = league_id
        if season_label:
            data["season_label"] = season_label
        if match_ids:
            data["match_ids"] = match_ids

        result = self._request("POST", "/api/crawl/start", json=data)
        return result

    def get_crawl_stats(self) -> Dict:
        """获取爬虫统计"""
        result = self._request("GET", "/api/crawl/stats")
        return result

    def get_crawl_jobs(self, status: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """获取爬虫任务列表"""
        params = {}
        if status:
            params["status"] = status
        params["limit"] = limit
        result = self._request("GET", "/api/crawl/jobs", params=params)
        return result

    def get_crawl_job(self, job_id) -> Dict:
        """获取单个爬虫任务详情（支持数据库ID或job_uuid字符串）"""
        result = self._request("GET", f"/api/crawl/jobs/{job_id}")
        return result

    def stop_crawl_job(self, job_id: int) -> Dict:
        """停止爬虫任务"""
        result = self._request("POST", f"/api/crawl/stop/{job_id}")
        return result

    def clear_sync_data(self) -> Dict:
        """清除所有同步的数据"""
        result = self._request("POST", "/api/leagues/clear-all")
        return result

    def sync_leagues_from_site(self) -> Dict:
        """从网站同步联赛列表"""
        result = self._request("POST", "/api/leagues/sync-from-site")
        return result

    def sync_seasons_for_league(self, league_id: int, season_label: Optional[str] = None) -> Dict:
        """同步指定联赛的赛季赛程"""
        params = {}
        if season_label:
            params["season_label"] = season_label
        result = self._request("POST", f"/api/leagues/{league_id}/sync-seasons", params=params)
        return result

    def sync_all_seasons(self) -> Dict:
        """批量同步所有联赛的赛季赛程（单后台任务）"""
        result = self._request("POST", "/api/leagues/batch-sync-seasons")
        return result

    def get_season_stats(self) -> Dict:
        """获取赛季维度统计（总赛季数、已同步赛季数）"""
        result = self._request("GET", "/api/season-stats")
        return result

    # ============ 结算相关 ============

    def auto_settle_match(self, match_id: int) -> Dict:
        """自动结算单场比赛

        根据比赛比分和盘口自动计算结算结果
        """
        result = self._request("POST", f"/api/matches/{match_id}/auto-settle")
        return result

    def batch_auto_settle(self, league_id: int = None, season: str = None) -> Dict:
        """批量自动结算"""
        params = {}
        if league_id is not None:
            params["league_id"] = league_id
        if season:
            params["season"] = season
        result = self._request("POST", "/api/matches/auto-settle", params=params)
        return result

    def update_match_score(self, match_id: int, score_ft: str, score_ht: str = None) -> Dict:
        """更新比赛比分并自动结算"""
        data = {"score_ft": score_ft}
        if score_ht:
            data["score_ht"] = score_ht
        result = self._request("POST", f"/api/matches/{match_id}/score", json=data)
        return result

    def get_match_settlement(self, match_id: int) -> Dict:
        """获取比赛结算结果"""
        result = self._request("GET", f"/api/matches/{match_id}/settlement")
        return result

    def calculate_x_values(self, league_id: int, season_label: str) -> Dict:
        """批量计算指定联赛赛季的X值（本地计算，跳过已有比分的已完成比赛）"""
        matches_result = self.get_matches(
            league_id=league_id,
            season=season_label,
            page=1,
            page_size=200
        )

        matches = []
        if isinstance(matches_result, dict):
            if "matches" in matches_result:
                matches = matches_result["matches"]
            elif "data" in matches_result:
                matches = matches_result["data"]
            else:
                matches = []
        elif isinstance(matches_result, list):
            matches = matches_result

        completed = 0
        failed = 0
        skipped = 0

        calculator = XValueCalculator(data_connector=self)

        for match in matches:
            match_id = match["match_id"]
            try:
                odds = self.get_match_odds(match_id)
            except Exception as e:
                logger.error(f"获取比赛 {match_id} 的赔率失败: {e}")
                failed += 1
                continue

            # 检查是否有85分钟后的赔率数据 → 比赛已完成，跳过X值计算
            if self._has_completed_odds(odds):
                skipped += 1
                continue

            # 使用已获取的赔率计算X值，避免二次请求
            try:
                x_result = calculator.calculate_from_odds_data(match_id, odds)

                if x_result.get("status") == "success" and x_result.get("x_value") is not None:
                    completed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"计算比赛 {match_id} 的X值失败: {e}")
                failed += 1

        return {
            "message": f"X值计算任务完成，成功计算 {completed} 场，跳过 {skipped} 场(已完成)，失败 {failed} 场",
            "completed": completed,
            "skipped": skipped,
            "failed": failed
        }

    @staticmethod
    def _has_completed_odds(movements: List[Dict]) -> bool:
        """检查赔率数据中是否有85分钟后的记录（比赛已完成）"""
        for m in movements:
            elapsed = m.get('elapsed_time')
            if elapsed is not None:
                try:
                    if int(elapsed) >= 85:
                        return True
                except (ValueError, TypeError):
                    pass
        return False

    _sub_league_cache: Dict[tuple, Dict[str, str]] = {}  # {(titan007_league_id, season): name_map}

    def get_sub_league_names(self, league_id: int, season: str) -> Dict[str, str]:
        """获取指定联赛赛季的子联赛/组名称映射
        返回: {inst_id: group_name (繁体中文)}
        """
        cache_key = (league_id, season)
        if cache_key in self._sub_league_cache:
            return self._sub_league_cache[cache_key]

        import re
        import json

        info_url = "https://info.titan007.com"
        titan_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://zq.titan007.com/big/",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        def _parse_arr_sub_league(html: str) -> Dict[str, str]:
            """Parse arrSubLeague from JS file content"""
            sub_m = re.search(r'var\s+arrSubLeague\s*=\s*(\[.*?\]);', html, re.DOTALL)
            if not sub_m:
                return {}
            try:
                raw = sub_m.group(1).replace("'", '"')
                sub_list = json.loads(raw)
                name_map = {}
                for entry in sub_list:
                    if isinstance(entry, list) and len(entry) > 3:
                        inst_id = str(entry[0])
                        if len(entry) > 2 and entry[2]:
                            name_tw = entry[2]
                        elif len(entry) > 1 and entry[1]:
                            name_tw = entry[1]
                        else:
                            name_tw = f"组{inst_id}"
                        name_map[inst_id] = name_tw
                # If only 1 entry, this season has no real sub-groups → "全部" only
                if len(name_map) <= 1:
                    return {"0": "全部"}
                # Multiple entries → add "全部" as extra option alongside real groups
                name_map["0"] = "全部"
                return name_map
            except (json.JSONDecodeError, IndexError):
                return {}

        def _fetch_js(url: str) -> str | None:
            """Fetch a JS file with browser headers"""
            try:
                resp = self.client.get(url, timeout=15, headers=titan_headers)
                if resp.status_code == 200 and "对不起！你查看的页面不存在" not in resp.text:
                    return resp.text
            except Exception:
                pass
            return None

        result: Dict[str, str] = {}

        try:
            # Strategy 1: Try main season JS file
            html = _fetch_js(f"{info_url}/jsData/matchResult/{season}/s{league_id}.js")
            if html:
                result = _parse_arr_sub_league(html)

            # Strategy 2: Try main JS file without season
            if not result:
                html = _fetch_js(f"{info_url}/jsData/matchResult/s{league_id}.js")
                if html:
                    result = _parse_arr_sub_league(html)

            # Strategy 3: Fetch the season-specific SubLeague page to discover
            # the correct sub-league instance ID for this season.
            # Then fetch the sub-league JS file to get arrSubLeague.
            if not result:
                try:
                    # Try season-specific URL first (e.g., SubLeague/2025/25.html)
                    # Falls back to League page (redirects to current season's SubLeague)
                    urls_to_try = [
                        f"https://zq.titan007.com/big/SubLeague/{season}/{league_id}.html",
                        f"https://zq.titan007.com/big/League/{league_id}.html",
                    ]
                    page_html = None
                    for url in urls_to_try:
                        resp = self.client.get(url, timeout=15, headers=titan_headers, follow_redirects=True)
                        if resp.status_code == 200:
                            page_html = resp.text
                            break

                    if page_html:
                        pattern = re.escape("/jsData/matchResult/") + r"[^\"']*?" + re.escape(f"s{league_id}_") + r"(\d+)\.js"
                        found = re.search(pattern, page_html)
                        if found:
                            inst_id = found.group(1)
                            # Try target season's sub-league JS file
                            sub_url = f"{info_url}/jsData/matchResult/{season}/s{league_id}_{inst_id}.js"
                            sub_html = _fetch_js(sub_url)
                            if sub_html:
                                result = _parse_arr_sub_league(sub_html)
                            # Strategy 4: Try alternative season directory formats
                            # (e.g., JLeague uses "2026" not "2025-2026")
                            if not result and "-" in season:
                                alt_season = season.split("-")[1]
                                for alt in [alt_season, season.split("-")[0]]:
                                    if alt != season:
                                        sub_url = f"{info_url}/jsData/matchResult/{alt}/s{league_id}_{inst_id}.js"
                                        sub_html = _fetch_js(sub_url)
                                        if sub_html:
                                            result = _parse_arr_sub_league(sub_html)
                                            if result:
                                                break
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"获取子联赛名称失败 league_id={league_id}, season={season}: {e}")

        # Cache and return: fallback to "全部" when no data found
        if not result:
            result = {"0": "全部"}
        self._sub_league_cache[cache_key] = result
        return result

    def close(self):
        """关闭连接"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 全局连接器实例
_connector: Optional[DataConnector] = None


def get_connector() -> DataConnector:
    """获取数据连接器单例"""
    global _connector
    if _connector is None:
        _connector = DataConnector()
    return _connector