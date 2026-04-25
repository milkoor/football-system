"""赔率变动爬虫模块

从 vip.titan007.com 抓取赔率变化数据
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import time
import random
from typing import Optional, Dict, List, Any
from datetime import datetime

from scraper.handicap_normalizer import HandicapNormalizer
from config.database import SessionLocal
from config.models import OddsMovement, Match

logger = logging.getLogger(__name__)


class OddsCrawler:
    """赔率变动爬虫"""

    BASE_URL = "https://vip.titan007.com"

    def __init__(
        self,
        concurrency: int = 3,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        proxy_config: Optional[Dict] = None,
    ):
        self.concurrency = concurrency
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.proxy_config = proxy_config
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        """初始化带有重试机制的 Session"""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "http://vip.titan007.com/"
        })

        # 配置代理
        if self.proxy_config and self.proxy_config.get("enabled"):
            proxy_type = self.proxy_config.get("type", "http")
            proxy_host = self.proxy_config.get("host", "")
            proxy_port = self.proxy_config.get("port", 0)
            proxy_user = self.proxy_config.get("username", "")
            proxy_pass = self.proxy_config.get("password", "")

            if proxy_host and proxy_port:
                if proxy_user and proxy_pass:
                    proxy_url = f"{proxy_type}://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
                else:
                    proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
                session.proxies = {
                    "http": proxy_url,
                    "https": proxy_url,
                }
                logger.info(f"代理已配置: {proxy_type}://{proxy_host}:{proxy_port}")

        return session

    def _random_delay(self):
        """随机延时"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def get_odds_page(self, match_id: int, odds_type: str = "AH") -> Optional[str]:
        """获取赔率变动页面

        Args:
            match_id: 比赛 ID
            odds_type: 赔率类型 (AH=亚盘, OU=大小, 1x2=欧赔)

        Returns:
            HTML 页面内容
        """
        # odds_type 映射
        type_map = {
            "AH": "handicap",  # 亚盘
            "OU": "overunder",  # 大小
            "1x2": "odd",  # 欧赔
        }

        page_type = type_map.get(odds_type, "handicap")
        url = f"{self.BASE_URL}/changeDetail/{page_type}.aspx?id={match_id}&companyID=3"

        try:
            self._random_delay()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"获取赔率页面失败: match_id={match_id}, error={e}")
            return None

    def parse_odds_movements(
        self,
        html: str,
        match_id: int,
        odds_type: str = "AH",
    ) -> List[Dict[str, Any]]:
        """解析赔率变动数据

        Args:
            html: 页面 HTML
            match_id: 比赛 ID
            odds_type: 赔率类型

        Returns:
            赔率变动记录列表
        """
        from bs4 import BeautifulSoup

        movements = []
        soup = BeautifulSoup(html, "lxml")

        # 查找赔率表格
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 5:
                    continue

                try:
                    # 解析每一行数据
                    # 格式: 时间, 比分, 主队赔率, 盘口, 客队赔率, 状态
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # 跳过表头
                    if "时间" in cell_texts[0] or "時間" in cell_texts[0]:
                        continue

                    # 基本解析（具体格式需要根据实际页面调整）
                    # 根据我们看到的数据，状态字段可能不存在，需要根据位置推断
                    update_time_str = cell_texts[0] if len(cell_texts) > 0 else ""
                    score_at_time = cell_texts[1] if len(cell_texts) > 1 else ""
                    home_rate_str = cell_texts[2] if len(cell_texts) > 2 else ""
                    handicap_raw = cell_texts[3] if len(cell_texts) > 3 else ""
                    away_rate_str = cell_texts[4] if len(cell_texts) > 4 else ""

                    # 根据我们看到的数据，状态字段不存在，全部标记为"早"
                    # 因为目前只有赛前数据
                    status = "早"

                    # 转换数值
                    try:
                        home_rate = float(home_rate_str) if home_rate_str else None
                    except ValueError:
                        home_rate = None

                    try:
                        away_rate = float(away_rate_str) if away_rate_str else None
                    except ValueError:
                        away_rate = None

                    # 标准化盘口
                    handicap_std = HandicapNormalizer.normalize(handicap_raw)

                    movement = {
                        "match_id": match_id,
                        "odds_type": odds_type,
                        "elapsed_time": "",  # 赛前为空
                        "score_at_time": score_at_time,
                        "update_time_str": update_time_str,
                        "status": status,
                        "home_rate": home_rate,
                        "handicap_raw": handicap_raw,
                        "handicap_std": handicap_std,
                        "away_rate": away_rate,
                    }

                    movements.append(movement)

                except Exception as e:
                    logger.warning(f"解析赔率行失败: {e}")
                    continue

        return movements

    def crawl_match_odds(
        self,
        match_id: int,
        odds_types: List[str] = None,
    ) -> Dict[str, List[Dict]]:
        """抓取单场比赛的所有赔率变动

        Args:
            match_id: 比赛 ID
            odds_types: 赔率类型列表，默认 [AH, OU, 1x2]

        Returns:
            按类型分组的赔率变动数据
        """
        if odds_types is None:
            odds_types = ["AH", "OU", "1x2"]

        result = {}
        for odds_type in odds_types:
            html = self.get_odds_page(match_id, odds_type)
            if html:
                movements = self.parse_odds_movements(html, match_id, odds_type)
                result[odds_type] = movements
            else:
                result[odds_type] = []

        return result

    def save_odds_movements(
        self,
        match_id: int,
        movements: List[Dict[str, Any]],
        odds_type: str = "AH",
    ) -> int:
        """保存赔率变动到数据库

        Args:
            match_id: 比赛 ID
            movements: 赔率变动列表
            odds_type: 赔率类型

        Returns:
            保存的记录数
        """
        db = SessionLocal()
        saved_count = 0

        try:
            # 先删除该比赛、该类型的旧数据
            db.query(OddsMovement).filter(
                OddsMovement.match_id == match_id,
                OddsMovement.odds_type == odds_type,
            ).delete()

            # 解析并保存新数据
            for m in movements:
                # 解析时间
                update_time = None
                if m.get("update_time_str"):
                    try:
                        # 尝试解析常见时间格式
                        update_time = datetime.strptime(
                            m["update_time_str"], "%m-%d %H:%M"
                        )
                        # 设置为当前年份
                        now = datetime.now()
                        update_time = update_time.replace(year=now.year)
                    except ValueError:
                        pass

                db_movement = OddsMovement(
                    match_id=match_id,
                    odds_type=odds_type,
                    is_half_time=False,
                    elapsed_time=m.get("elapsed_time", ""),
                    score_at_time=m.get("score_at_time", ""),
                    update_time=update_time,
                    status=m.get("status", "早"),
                    home_rate=m.get("home_rate"),
                    handicap_raw=m.get("handicap_raw", ""),
                    handicap_std=m.get("handicap_std"),
                    away_rate=m.get("away_rate"),
                )
                db.add(db_movement)
                saved_count += 1

            db.commit()
            logger.info(
                f"已保存 {saved_count} 条 {odds_type} 赔率数据, match_id={match_id}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"保存赔率数据失败: match_id={match_id}, error={e}")
            raise
        finally:
            db.close()

        return saved_count

    def is_match_completed(self, match_id: int) -> bool:
        """判断比赛是否已完成

        Args:
            match_id: 比赛 ID

        Returns:
            是否已完成
        """
        db = SessionLocal()
        try:
            match = db.query(Match).filter(Match.match_id == match_id).first()
            if match:
                # 如果有比分，认为比赛已完成
                score_ft = match.score_ft or ""
                if score_ft.strip():
                    return True
            return False
        finally:
            db.close()

    def crawl_and_save(
        self,
        match_id: int,
        odds_types: List[str] = None,
    ) -> Dict[str, int]:
        """抓取并保存赔率数据

        Args:
            match_id: 比赛 ID
            odds_types: 赔率类型列表

        Returns:
            每种类型的保存数量
        """
        if odds_types is None:
            odds_types = ["AH"]

        # 先检查比赛是否已完成
        if self.is_match_completed(match_id):
            logger.info(f"比赛 {match_id} 已完成，跳过赔率下载")
            # 即使不下载，也要确保状态标记为 completed
            self._update_match_status(match_id, "completed")
            return {ot: 0 for ot in odds_types}

        result = {}
        for odds_type in odds_types:
            html = self.get_odds_page(match_id, odds_type)
            if html:
                movements = self.parse_odds_movements(html, match_id, odds_type)
                if movements:
                    saved = self.save_odds_movements(match_id, movements, odds_type)
                    result[odds_type] = saved

                    # 更新比赛的爬取状态
                    self._update_match_status(match_id, "completed")
                else:
                    result[odds_type] = 0
                    self._update_match_status(match_id, "nodata")
            else:
                result[odds_type] = 0
                self._update_match_status(match_id, "error")

            # 添加延迟
            time.sleep(random.uniform(0.5, 1.5))

        return result

    def _update_match_status(self, match_id: int, status: str):
        """更新比赛爬取状态"""
        db = SessionLocal()
        try:
            match = db.query(Match).filter(Match.match_id == match_id).first()
            if match:
                match.crawl_status = status
                match.last_synced = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"更新比赛状态失败: match_id={match_id}, error={e}")
        finally:
            db.close()