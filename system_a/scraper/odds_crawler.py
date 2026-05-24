"""赔率变动爬虫模块

从 vip.titan007.com 抓取赔率变化数据
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import time
import random
import re
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
            total=1,  # 减少重试次数，避免长时间等待
            backoff_factor=0.5,  # 缩短重试间隔
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
            odds_type: 赔率类型 (AH=亚盘, OU=大小球, 1x2=欧赔)

        Returns:
            页面 HTML 内容
        """
        type_map = {
            "AH": "handicap",
            "OU": "overunder",
            "1x2": "odd",
        }
        page_type = type_map.get(odds_type, "handicap")
        url = f"{self.BASE_URL}/changeDetail/{page_type}.aspx?id={match_id}&companyID=3"

        try:
            response = self.session.get(url, timeout=30)
            response.encoding = "utf-8"
            if "charset=gb2312" in response.text[:500].lower():
                response.encoding = "gb2312"
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"获取赔率页面失败: {url}, error={e}")
            return None

    def parse_odds_movements(
        self,
        html: str,
        match_id: int,
        odds_type: str = "AH",
    ) -> List[Dict[str, Any]]:
        """解析赔率变动数据

        网页列: 时间 | 比分 | 主队赔率 | 盘口 | 客队赔率 | 变化时间 | 状态
        - cell_texts[0] = 比赛已过时间 (如 "92", "93"，赛前为空)
        - cell_texts[1] = 比分
        - cell_texts[2] = 主队赔率
        - cell_texts[3] = 盘口
        - cell_texts[4] = 客队赔率
        - cell_texts[5] = 变化时间 (如 "8-24 02:24")
        - cell_texts[6] = 状态 ("滚"=滚盘, "早"=早盘)

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

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                try:
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    # 跳过首行(合并单元格)和表头
                    if len(cell_texts) == 1 and len(cell_texts[0]) > 50:
                        continue
                    if len(cell_texts) >= 2 and ("时间" in cell_texts[0] or "時間" in cell_texts[0]):
                        continue

                    elapsed_time = cell_texts[0] if len(cell_texts) > 0 else ""
                    score_at_time = cell_texts[1] if len(cell_texts) > 1 else ""
                    home_rate_str = cell_texts[2] if len(cell_texts) > 2 else ""

                    # 封盘行只有5列: 时间, 比分, 封, 变化时间, 状态
                    if home_rate_str == "封":
                        handicap_raw = ""
                        away_rate_str = ""
                        update_time_str = cell_texts[3] if len(cell_texts) > 3 else ""
                        raw_status = cell_texts[4] if len(cell_texts) > 4 else ""
                    else:
                        handicap_raw = cell_texts[3] if len(cell_texts) > 3 else ""
                        away_rate_str = cell_texts[4] if len(cell_texts) > 4 else ""
                        update_time_str = cell_texts[5] if len(cell_texts) > 5 else ""
                        raw_status = cell_texts[6] if len(cell_texts) > 6 else ""

                    # 判断状态: "滚"=滚盘, "早"=早盘
                    if raw_status == "滚":
                        status = "滚"
                    elif elapsed_time and elapsed_time.isdigit():
                        status = "滚"
                    else:
                        status = "早"

                    # 转换数值（"封"=封盘/暂停，不解析为数字）
                    try:
                        home_rate = float(home_rate_str) if home_rate_str and home_rate_str != "封" else None
                    except ValueError:
                        home_rate = None

                    try:
                        away_rate = float(away_rate_str) if away_rate_str and away_rate_str != "封" else None
                    except ValueError:
                        away_rate = None

                    # 标准化盘口
                    handicap_std = HandicapNormalizer.normalize(handicap_raw)

                    movement = {
                        "match_id": match_id,
                        "odds_type": odds_type,
                        "elapsed_time": elapsed_time,
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
    ) -> Dict[str, int]:
        """爬取单场比赛的赔率（旧接口，保留兼容）

        Args:
            match_id: 比赛 ID
            odds_types: 赔率类型列表

        Returns:
            每种类型的保存数量
        """
        return self.crawl_and_save(match_id, odds_types or ["AH"])

    def crawl_and_save(
        self,
        match_id: int,
        odds_types: List[str] = None,
    ) -> Dict[str, int]:
        """爬取单场比赛的赔率并保存

        流程:
        1. 检查是否已爬取 (crawl_status=completed 则跳过)
        2. 爬取赔率 HTML
        3. 解析赔率变动
        4. 保存到数据库
        5. 检查滚盘数据中是否有 elapsed_time > 90 → 标记 completed
        6. 否则标记为正常爬取状态

        Args:
            match_id: 比赛 ID
            odds_types: 赔率类型列表

        Returns:
            每种类型的保存数量
        """
        if odds_types is None:
            odds_types = ["AH"]

        # 先检查是否已经爬取过
        db = SessionLocal()
        try:
            match = db.query(Match).filter(Match.match_id == match_id).first()
            if match and match.crawl_status == "completed":
                logger.info(f"比赛 {match_id} 已爬取过，跳过")
                return {ot: 0 for ot in odds_types}
        finally:
            db.close()

        result = {}
        all_movements = []  # 收集所有赔率变动，用于赛后判断

        for odds_type in odds_types:
            html = self.get_odds_page(match_id, odds_type)
            if html:
                movements = self.parse_odds_movements(html, match_id, odds_type)
                if movements:
                    saved = self.save_odds_movements(match_id, movements, odds_type)
                    result[odds_type] = saved
                    all_movements.extend(movements)
                else:
                    result[odds_type] = 0
                    # 有页面但无数据 → nodata
                    self._update_match_status(match_id, "nodata")
                    continue
            else:
                result[odds_type] = 0
                self._update_match_status(match_id, "error")
                continue

            # 添加延迟
            time.sleep(random.uniform(0.5, 1.5))

        # 判断比赛是否已完成：滚盘数据中有 elapsed_time > 90
        is_completed = False
        for m in all_movements:
            try:
                if m.get("status") == "滚" and int(m["elapsed_time"]) > 90:
                    is_completed = True
                    break
            except (ValueError, TypeError):
                continue

        if is_completed:
            self._update_match_status(match_id, "completed")
            logger.info(f"比赛 {match_id} 已完赛 (elapsed_time > 90)，标记为 completed")
        # 未完赛：不设状态，保留 pending/error/nodata 下次重爬

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
                # 解析变化时间 (cell_texts[5]，如 "8-24 02:24")
                update_time = None
                if m.get("update_time_str"):
                    try:
                        update_time = datetime.strptime(
                            m["update_time_str"], "%m-%d %H:%M"
                        )
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
                    handicap_raw=m.get("handicap_raw"),
                    handicap_std=m.get("handicap_std"),
                    away_rate=m.get("away_rate"),
                )
                db.add(db_movement)
                saved_count += 1

            db.commit()
            logger.info(
                f"已保存 {match_id} {odds_type} 赔率变动 {saved_count} 条"
            )

        except Exception as e:
            logger.error(f"保存赔率变动失败: {e}")
            db.rollback()
        finally:
            db.close()

        return saved_count

    def is_match_completed(self, match_id: int) -> bool:
        """检查比赛是否已完成（通过赔率数据判断）"""
        db = SessionLocal()
        try:
            # 查询该比赛是否有 elapsed_time > 90 的滚盘记录
            row = db.query(OddsMovement).filter(
                OddsMovement.match_id == match_id,
                OddsMovement.status == "滚",
            ).order_by(
                OddsMovement.elapsed_time.desc()
            ).first()
            if row and row.elapsed_time:
                try:
                    return int(row.elapsed_time) > 90
                except ValueError:
                    pass
            return False
        finally:
            db.close()