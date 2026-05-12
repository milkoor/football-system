"""数据连接器模块

从系统 A API 拉取数据
"""

import logging
from typing import Optional, List, Dict, Any
import httpx

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

    def get_x_values(self, **kwargs) -> List[Dict]:
        """获取 X 值计算结果"""
        params = {k: v for k, v in kwargs.items() if v is not None}
        result = self._request("GET", "/api/x-values", params=params)
        return result

    def save_x_value(self, x_result: Dict) -> Dict:
        """保存 X 值计算结果"""
        data = {
            "match_id": x_result.get("match_id"),
            "home_team": x_result.get("home_team"),
            "away_team": x_result.get("away_team"),
            "score": x_result.get("score"),
            "target_team": x_result.get("target_team"),
            "has_star_mark": x_result.get("has_star_mark"),
            "x_value": x_result.get("x_value"),
            "status": x_result.get("status", "success"),
            "calculation_note": x_result.get("calculation_note"),
            "movement_url": x_result.get("movement_url"),
        }
        result = self._request("POST", "/api/x-values", json=data)
        return result

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
        """同步指定联赛的赛季赛程

        Args:
            league_id: 联赛ID
            season_label: (可选) 赛季标签，此参数被忽略，系统A会自动同步所有可用赛季
        """
        result = self._request("POST", f"/api/leagues/{league_id}/sync-seasons")
        return result

    def sync_all_seasons(self) -> Dict:
        """批量同步所有联赛的赛季赛程（单后台任务）"""
        result = self._request("POST", "/api/leagues/batch-sync-seasons")
        return result

    def get_season_stats(self) -> Dict:
        """获取赛季维度统计（总赛季数、已同步赛季数）"""
        result = self._request("GET", "/api/seasons/stats")
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
        """批量计算指定联赛赛季的X值（本地计算）"""
        # 获取该联赛赛季的所有比赛
        matches_result = self.get_matches(
            league_id=league_id,
            season=season_label,
            page=1,
            page_size=200  # 足够大的数量，确保获取所有比赛
        )

        matches = []
        # 处理可能的分页结构 - 系统A返回 {total: X, matches: [...]}
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

        calculator = XValueCalculator(data_connector=self)

        for match in matches:
            match_id = match["match_id"]
            try:
                # 本地计算X值
                x_result = calculator.calculate_from_match(match_id)

                if x_result.get("status") == "success" and x_result.get("x_value") is not None:
                    # 保存结果到系统A
                    self.save_x_value(x_result)
                    completed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"计算比赛 {match_id} 的X值失败: {e}")
                failed += 1

        return {
            "message": f"X值计算任务完成，成功计算 {completed} 场比赛，失败 {failed} 场",
            "completed": completed,
            "failed": failed
        }

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