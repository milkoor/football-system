"""爬虫模块

包含：
- 联赛赛程爬虫 (LeagueCrawler)
- 赔率变动爬虫 (OddsCrawler)
- 盘口标准化 (HandicapNormalizer)
- 队名标准化 (TeamNameNormalizer)
"""

from scraper.league_crawler import LeagueCrawler
from scraper.odds_crawler import OddsCrawler
from scraper.handicap_normalizer import HandicapNormalizer
from scraper.team_normalizer import TeamNameNormalizer

__all__ = [
    "LeagueCrawler",
    "OddsCrawler",
    "HandicapNormalizer",
    "TeamNameNormalizer",
]