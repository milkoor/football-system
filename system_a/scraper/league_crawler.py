"""联赛赛程爬虫模块

从 zq.titan007.com / info.titan007.com 抓取联赛赛程
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import json
import logging
import time
import random
from typing import Optional, Dict, List, Any
from datetime import datetime

from scraper.team_normalizer import TeamNameNormalizer
from scraper.mock_data import MOCK_LEAGUES, MOCK_MATCHES

logger = logging.getLogger(__name__)


class LeagueCrawler:
    """联赛赛程爬虫"""

    BASE_URL = "https://zq.titan007.com"
    INFO_URL = "https://info.titan007.com"

    def __init__(
        self,
        concurrency: int = 3,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
    ):
        self.concurrency = concurrency
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.session = self._init_session()
        self.sub_id_cache = {}

    def _init_session(self) -> requests.Session:
        """初始化 Session"""
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
            "Referer": "http://zq.titan007.com/big/"
        })

        return session

    def _random_delay(self):
        """随机延时"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _get_html(self, url: str) -> Optional[str]:
        """获取 HTML 页面"""
        try:
            self._random_delay()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"获取页面失败: {url}, error={e}")
            return None

    def get_league_list(self) -> List[Dict[str, Any]]:
        """获取联赛列表

        Returns:
            联赛信息列表
        """
        leagues = []

        # 新的联赛数据 URL
        url = f"{self.INFO_URL}/jsData/leftData/leftData.js"
        html = self._get_html(url)

        if html:
            leagues = self._parse_league_list(html)

        # 如果没有获取到真实数据，返回模拟数据
        if not leagues:
            logger.warning("无法获取真实联赛数据，使用模拟数据")
            leagues = MOCK_LEAGUES

        return leagues

    def _parse_league_list(self, html: str) -> List[Dict[str, Any]]:
        """解析联赛列表"""
        leagues = []
        league_ids = set()

        # 匹配 arrArea 数组格式
        # 格式: arrArea[0] = [['国际赛事',...[[75,'世界杯','世界盃','World Cup',2],...]]
        # 匹配所有 arrArea[索引] = [...];
        area_pattern = r'arrArea\[(\d+)\]\s*=\s*(\[.*?\]);'
        area_matches = re.findall(area_pattern, html, re.DOTALL)

        for area_idx, area_data in area_matches:
            # 在每个区域数据中查找联赛信息
            # 格式: [联赛ID,'联赛中文名,'联赛英文名,其他参数
            league_pattern = r'\[(\d+),\s*\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\''
            # 使用更简单的模式来匹配联赛信息
            # 简化版本: [id, 'name1', 'name2', 'name3',
            league_simple_pattern = r'\[(\d+)\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\''

            # 查找所有联赛
            league_matches = re.findall(league_simple_pattern, area_data)

            for league_id, name1, name2, name3 in league_matches:
                league_id_int = int(league_id)

                # 避免重复
                if league_id_int in league_ids:
                    continue

                league_ids.add(league_id_int)

                # 尝试获取国家名称
                country = ""
                # 从区域名称中推断国家
                area_names = {
                    0: "国际",
                    1: "欧洲",
                    2: "美洲",
                    3: "亚洲",
                    4: "大洋洲",
                    5: "非洲",
                }
                country = area_names.get(int(area_idx), "")

                # 确定联赛名称
                # name1 通常是英文名称，name2是繁体中文，name3是简体中文
                league_name_tw = name2 if name2 else name1
                league_name_zh = name3 if name3 else name2 if name2 else name1

                leagues.append({
                    "league_id": league_id_int,
                    "name": league_name_tw,
                    "country": country,
                })

        # 如果找到的联赛太少，可能模式不对，再尝试其他方法
        if len(leagues) < 5:
            # 试试更简单的模式：只匹配数字开始
            # 格式: [数字,'名字
            simple_pattern = r'\[(\d+)\s*,\s*\'([^\']*)\''
            simple_matches = re.findall(simple_pattern, html)

            for league_id, name in simple_matches:
                league_id_int = int(league_id)

                if league_id_int not in league_ids:
                    leagues.append({
                        "league_id": league_id_int,
                        "name": name,
                        "country": "",
                    })

        return leagues

    def get_season_schedules(
        self,
        league_id: int,
        season: str = None,
    ) -> List[Dict[str, Any]]:
        """获取指定联赛的赛季赛程

        Args:
            league_id: 联赛 ID
            season: 赛季，如 "2024-2025"

        Returns:
            比赛记录列表
        """
        matches = []

        # 从联赛页提取一个 sample 数据 URL，用它解析 arrSubLeague
        # 联赛页通常只暴露最新赛季的最后一个 sub-league（如附加赛决赛）
        # 我们需要抓取所有 sub-league（主联赛 + 冠军组/保级组/附加赛等）合并
        # sub_leagues: [(instance_id, name_en, is_main_league), ...]
        sub_leagues: list[tuple[int, str, bool]] = []
        try:
            # 当指定赛季时，优先尝试 SubLeague 页面（可获取该赛季正确的子联赛实例）
            # 例如日职联 2025 使用子联赛实例 943，但 2026 使用 3540/3541
            urls_to_try = []
            if season:
                urls_to_try.append(f"{self.BASE_URL}/big/SubLeague/{season}/{league_id}.html")
            urls_to_try.append(f"{self.BASE_URL}/big/League/{league_id}.html")

            resp = None
            for url in urls_to_try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    break

            if resp and resp.status_code == 200:
                pattern = re.escape(f"/jsData/matchResult/") + r"([^\"']*?)" + re.escape(f"s{league_id}_") + r"(\d+)\.js"
                found = re.search(pattern, resp.text)
                if found:
                    sample_url = f"{self.INFO_URL}{found.group(0).split('?')[0]}"
                    sample_html = self._get_html(sample_url)
                    if sample_html and "对不起！你查看的页面不存在" not in sample_html:
                        sub_m = re.search(r'var\s+arrSubLeague\s*=\s*(\[.*?\]);', sample_html, re.DOTALL)
                        if sub_m:
                            try:
                                raw = sub_m.group(1).replace("'", '"')
                                sub_list = json.loads(raw)
                                # arrSubLeague entry: [id, nameZh, nameTw, nameEn, isMainLeague(0/1), totalRounds, ...]
                                for entry in sub_list:
                                    if isinstance(entry, list) and len(entry) > 4:
                                        sub_leagues.append((
                                            entry[0],
                                            entry[3] if len(entry) > 3 else "",
                                            entry[4] == 1,
                                        ))
                            except (json.JSONDecodeError, IndexError):
                                pass
        except Exception as e:
            logger.debug(f"获取联赛 {league_id} 页面失败: {e}")

        # 抓取所有 sub-league 并合并（按 match_id 去重）
        # 为避免不同 sub-league 的轮次（如 R_1）冲突，给非主联赛 sub-league 加唯一前缀
        if sub_leagues and season:
            # 找出"基础联赛"：第一个 isMainLeague=1 且英文名为 'League' 的（如 23 场 38 轮的常规赛）
            # 如果没有，第一个 isMainLeague=1 的视作基础联赛，不加前缀
            base_inst = None
            for inst_id, name_en, is_main in sub_leagues:
                if is_main and name_en == "League":
                    base_inst = inst_id
                    break
            if base_inst is None:
                for inst_id, name_en, is_main in sub_leagues:
                    if is_main:
                        base_inst = inst_id
                        break

            # 并发抓取所有 sub-league HTML（IO 密集，6 线程已足够）
            import concurrent.futures as _cf

            def _fetch(inst_id):
                url = f"{self.INFO_URL}/jsData/matchResult/{season}/s{league_id}_{inst_id}.js"
                return inst_id, self._get_html(url)

            inst_html: dict = {}
            with _cf.ThreadPoolExecutor(max_workers=min(6, len(sub_leagues))) as pool:
                for inst_id, html in pool.map(_fetch, [s[0] for s in sub_leagues]):
                    inst_html[inst_id] = html

            seen_ids: set = set()
            # 保留 sub_leagues 顺序以保证去重时 base 联赛先入
            for inst_id, name_en, _is_main in sub_leagues:
                html = inst_html.get(inst_id)
                if not html or "对不起！你查看的页面不存在" in html:
                    continue
                sub_matches = self._parse_schedule_js(html, league_id, season)
                prefix = "" if inst_id == base_inst else f"S{inst_id}_"
                for m in sub_matches:
                    mid = m.get("match_id")
                    if mid in seen_ids:
                        continue
                    if prefix:
                        m["round_name"] = f"{prefix}{m.get('round_name', 'R_1')}"
                    matches.append(m)
                    seen_ids.add(mid)
            logger.info(
                f"联赛 {league_id} {season}: 抓取 {len(sub_leagues)} 个 sub-league，"
                f"合并去重后 {len(matches)} 场"
            )

        # 回退到旧格式
        if not matches and season:
            url = f"{self.INFO_URL}/jsData/matchResult/{season}/s{league_id}.js"
            html = self._get_html(url)
            if html and "对不起！你查看的页面不存在" not in html:
                matches = self._parse_schedule_js(html, league_id, season)

        if not matches:
            logger.warning(f"没有找到赛季 {season} 的数据，尝试不带赛季的URL")
            url = f"{self.INFO_URL}/jsData/matchResult/s{league_id}.js"
            html = self._get_html(url)
            if html and "对不起！你查看的页面不存在" not in html:
                matches = self._parse_schedule_js(html, league_id, season or str(datetime.now().year))

        if not matches:
            logger.warning(f"无法获取联赛 {league_id} 的真实赛程数据，使用模拟数据")
            matches = MOCK_MATCHES.get(league_id, [])

        return matches

    def batch_fetch_seasons(self, tasks: List[tuple[int, str]]) -> Dict[str, List[Dict]]:
        """批量抓取多个联赛赛季的比赛数据（并发、无 random_delay）

        Args:
            tasks: [(league_id, season), ...]

        Returns:
            {"{league_id}_{season}": [match_dict, ...]}
        """
        import concurrent.futures as _cf
        import re as _re
        import requests as _req

        result: Dict[str, List[Dict]] = {}
        session = _req.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://zq.titan007.com/",
        })

        def _fetch_one(lid: int, season: str) -> tuple[str, str | None]:
            key = f"{lid}_{season}"
            url = f"{self.INFO_URL}/jsData/matchResult/{season}/s{lid}.js"
            try:
                resp = session.get(url, timeout=30)
                if resp.status_code == 200 and "对不起！你查看的页面不存在" not in resp.text:
                    return key, resp.text
                # 尝试无赛季 URL
                url2 = f"{self.INFO_URL}/jsData/matchResult/s{lid}.js"
                resp2 = session.get(url2, timeout=30)
                if resp2.status_code == 200 and "对不起！你查看的页面不存在" not in resp2.text:
                    return key, resp2.text
            except Exception:
                pass
            return key, None

        with _cf.ThreadPoolExecutor(max_workers=10) as pool:
            fut_map = {pool.submit(_fetch_one, lid, season): (lid, season) for lid, season in tasks}
            for fut in _cf.as_completed(fut_map):
                key, html = fut.result()
                if html:
                    lid, season = fut_map[fut]
                    parsed = self._parse_schedule_js(html, lid, season)
                    if parsed:
                        result[key] = parsed

        session.close()
        logger.info(f"batch_fetch_seasons: 请求 {len(tasks)} 个赛季, 成功 {len(result)}")
        return result

    def _parse_schedule_js(
        self,
        html: str,
        league_id: int,
        season: str,
    ) -> List[Dict[str, Any]]:
        """解析赛程 JS 数据"""
        matches = []

        try:
            # 首先尝试解析队伍信息
            team_map = {}
            # 格式: var arrTeam = [[teamId, teamNameZh, teamNameTw, ...], ...]
            team_pattern = r'var\s+arrTeam\s*=\s*(\[.*?\]);'
            team_match = re.search(team_pattern, html, re.DOTALL)
            if team_match:
                team_json = team_match.group(1)
                # 先处理空字符串 ''
                team_json = team_json.replace("''", '""')
                # 处理单引号字符串
                team_json = re.sub(r"'([^']+)'", r'"\1"', team_json)
                # 处理特殊值
                team_json = team_json.replace("undefined", "null")
                team_json = re.sub(r',,\s*]', ']', team_json)
                team_json = re.sub(r',,\s*,', ',', team_json)
                try:
                    team_data = json.loads(team_json)
                    for team in team_data:
                        if isinstance(team, list) and len(team) >= 4:
                            team_id = team[0]
                            team_name_tw = team[2] if team[2] else team[1]
                            team_map[team_id] = team_name_tw
                except json.JSONDecodeError as e:
                    logger.warning(f"解析队伍数据失败: {e}")
                    pass

            # 尝试从 jh 对象中获取比赛数据（新格式）
            # 格式: jh["R_1"] = [[matchId, leagueId, ..., homeTeamId, awayTeamId, score, ...], ...]
            jh_pattern = r'jh\["([^"]+)"\]\s*=\s*(\[.*?\]);'
            jh_matches = re.findall(jh_pattern, html, re.DOTALL)

            for round_name, jh_data in jh_matches:
                # 解析这个轮次的比赛数据
                json_str = jh_data
                # 1. 先处理空字符串 ''
                json_str = json_str.replace("''", '""')
                # 2. 处理单引号字符串
                json_str = re.sub(r"'([^']+)'", r'"\1"', json_str)
                # 3. 处理特殊值
                json_str = json_str.replace("undefined", "null")
                # 4. 处理多余的逗号
                json_str = re.sub(r',,\s*]', ']', json_str)
                json_str = re.sub(r',,\s*,', ',', json_str)

                try:
                    data = json.loads(json_str)

                    # 检测是否为淘汰赛配对结构（升级附加赛/季后赛常见）
                    # 正赛: [[matchId, leagueId, ..., time(str), home_id, away_id, score, ...], ...]
                    # 淘汰赛: [[home_id, away_id, home_wins, away_wins, [leg1_match], [leg2_match]], ...]
                    # 区分依据: 正赛 item[3] 是时间字符串，淘汰赛 item[4]/item[5] 是 sub-list
                    flat_items = []
                    for item in data:
                        if not isinstance(item, list):
                            continue
                        # 淘汰赛配对：里面有 sub-list 形式的 leg
                        has_sub_list = any(isinstance(x, list) and len(x) >= 7 for x in item)
                        if has_sub_list:
                            # 提取每个 leg 作为独立 match
                            for sub in item:
                                if isinstance(sub, list) and len(sub) >= 7:
                                    flat_items.append(sub)
                        else:
                            flat_items.append(item)

                    for item in flat_items:
                        if not isinstance(item, list) or len(item) < 10:
                            continue

                        try:
                            # 新格式：[matchId, leagueId, -, time, homeTeamId, awayTeamId, score, halfScore, ...]
                            match_id = item[0] if len(item) > 0 else None
                            if not match_id:
                                continue

                            # 获取队伍名称
                            home_team_id = item[4] if len(item) > 4 else None
                            away_team_id = item[5] if len(item) > 5 else None
                            home_team = team_map.get(home_team_id, str(home_team_id)) if home_team_id else ""
                            away_team = team_map.get(away_team_id, str(away_team_id)) if away_team_id else ""

                            # 简繁转换
                            home_team = TeamNameNormalizer.to_traditional(home_team)
                            away_team = TeamNameNormalizer.to_traditional(away_team)

                            match_record = {
                                "match_id": match_id,
                                "league_id": league_id,
                                "league_name": "",
                                "season": season,
                                "round_name": round_name,
                                "match_time_str": item[3] if len(item) > 3 else "",
                                "home_team": home_team,
                                "away_team": away_team,
                                "score_ft": item[6] if len(item) > 6 else "",
                            }

                            matches.append(match_record)

                        except (IndexError, ValueError) as e:
                            logger.debug(f"解析比赛记录失败: {e}")
                            continue

                except json.JSONDecodeError:
                    continue

            # 如果新格式没有找到数据，尝试旧格式 arrMatch
            if not matches:
                # 尝试匹配比赛数组（旧格式）
                # 格式: var arrMatch = [[matchId, leagueId, leagueName, ..., homeTeam, awayTeam, ...], ...]
                pattern = r'var\s+arrMatch\s*=\s*(\[.*?\]);'
                match = re.search(pattern, html, re.DOTALL)

                if match:
                    json_str = match.group(1)
                    # 预处理：处理未加引号的键
                    json_str = re.sub(r'(\w+)=', r'"\1":', json_str)

                    # 处理单引号字符串和空字符串
                    json_str = json_str.replace("''", '""')
                    json_str = re.sub(r"'([^']+)'", r'"\1"', json_str)

                    # 处理 undefined 和其他 JS 特殊值
                    json_str = json_str.replace("undefined", "null")

                    # 处理多余的逗号
                    json_str = re.sub(r',,\s*]', ']', json_str)
                    json_str = re.sub(r',,\s*,', ',', json_str)

                    data = json.loads(json_str)

                    for item in data:
                        if not isinstance(item, list) or len(item) < 10:
                            continue

                        try:
                            # 根据实际数据结构调整索引
                            # 常见格式：[matchId, leagueId, leagueName, season, round, time, home, away, score, ...]
                            match_record = {
                                "match_id": item[0] if len(item) > 0 else None,
                                "league_id": league_id,
                                "league_name": item[2] if len(item) > 2 else "",
                                "season": season or (item[3] if len(item) > 3 else ""),
                                "round_name": item[4] if len(item) > 4 else "",
                                "match_time_str": item[5] if len(item) > 5 else "",
                                "home_team": TeamNameNormalizer.to_traditional(item[6]) if len(item) > 6 else "",
                                "away_team": TeamNameNormalizer.to_traditional(item[7]) if len(item) > 7 else "",
                                "score_ft": item[8] if len(item) > 8 else "",
                            }

                            if match_record["match_id"]:
                                matches.append(match_record)

                        except (IndexError, ValueError) as e:
                            logger.debug(f"解析比赛记录失败: {e}")
                            continue

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"解析赛程数据失败: {e}")

        return matches

    def get_available_seasons(self, league_id: int) -> List[str]:
        """获取联赛的可用赛季列表

        Args:
            league_id: 联赛 ID

        Returns:
            可用赛季列表，按时间从新到旧排序
        """
        seasons = []
        current_year = datetime.now().year

        # 尝试最近几个赛季（YYYY-YYYY格式，如 2025-2026）
        for year_offset in range(0, 5):
            start_year = current_year - year_offset
            end_year = start_year + 1
            season_label = f"{start_year}-{end_year}"

            url = f"{self.INFO_URL}/jsData/matchResult/{season_label}/s{league_id}.js"
            html = self._get_html(url)

            if html and "对不起！你查看的页面不存在" not in html:
                if self._has_match_data(html):
                    seasons.append(season_label)
                    logger.info(f"发现可用赛季(YYYY-YYYY): {season_label}")

        # 尝试年格式（日职联等使用，如 2026, 2025）
        if not seasons:
            for year_offset in range(0, 5):
                year = current_year - year_offset
                season_label = str(year)
                url = f"{self.INFO_URL}/jsData/matchResult/{season_label}/s{league_id}.js"
                html = self._get_html(url)
                if html and "对不起！你查看的页面不存在" not in html:
                    if self._has_match_data(html):
                        seasons.append(season_label)
                        logger.info(f"发现可用赛季(year-only): {season_label}")

        # 如果没有找到常规赛季，尝试不带赛季的URL（世界杯等特殊赛事）
        if not seasons:
            url = f"{self.INFO_URL}/jsData/matchResult/s{league_id}.js"
            html = self._get_html(url)
            if html and "对不起！你查看的页面不存在" not in html:
                if self._has_match_data(html):
                    seasons.append(str(current_year))
                    logger.info(f"发现不带赛季的赛事数据: {current_year}")

        # 如果还是没有找到，尝试一些常见的旧赛季
        if not seasons:
            for season in ["2024-2025", "2023-2024", "2022-2023"]:
                url = f"{self.INFO_URL}/jsData/matchResult/{season}/s{league_id}.js"
                html = self._get_html(url)
                if html and "对不起！你查看的页面不存在" not in html:
                    if self._has_match_data(html):
                        seasons.append(season)
                        logger.info(f"发现可用赛季: {season}")

        return seasons if seasons else ["2024-2025", "2023-2024"]

    def _has_match_data(self, html: str) -> bool:
        """检查HTML内容中是否有比赛数据

        Args:
            html: HTML内容

        Returns:
            是否有比赛数据
        """
        # 检查是否有 jh 对象
        if re.search(r'jh\["R_\d+"\]', html):
            return True
        # 检查是否有 arrMatch 数组
        if re.search(r'var\s+arrMatch', html):
            return True
        return False

    def sync_league(self, league_id: int, season: str) -> int:
        """同步单个联赛的赛程

        Args:
            league_id: 联赛 ID
            season: 赛季

        Returns:
            同步的比赛数量
        """
        matches = self.get_season_schedules(league_id, season)
        logger.info(f"联赛 {league_id} {season} 赛季获取到 {len(matches)} 场比赛")
        return len(matches)

    def fetch_all_seasons(self) -> Dict[int, List[str]]:
        """从 titan007 一次性抓取所有联赛的可用赛季列表

        解析 infoHeaderFn.js 文件，该文件包含所有联赛的所有可用赛季。
        避免逐个联赛调用 get_available_seasons（需要 5-8 HTTP 请求/联赛）。

        如果 HTTP 请求被 WAF 阻断，使用缓存的 season 数据作为 fallback。

        Returns:
            {league_titan_id: [season_label1, season_label2, ...]}
        """
        import re as _re
        import json as _json
        import os as _os

        url = "https://zq.titan007.com/jsData/infoHeaderFn.js"
        html = self._get_html(url)
        if not html:
            logger.warning("infoHeaderFn.js 请求失败，尝试使用缓存文件")
            cache_path = _os.path.join(_os.path.dirname(__file__), "..", "data", "seasons_cache.json")
            if _os.path.exists(cache_path):
                with open(cache_path) as f:
                    return _json.load(f)
            logger.error("缓存文件不存在，返回空数据")
            return {}

        result: Dict[int, List[str]] = {}
        for m in _re.finditer(r'\"(\d+),([^,\"]+),(\d+),(\d+),(.*?)\"', html):
            try:
                lid = int(m.group(1))
                seasons_str = m.group(5)
                seasons = [s.strip() for s in seasons_str.split(",") if s.strip()]
                if seasons:
                    result[lid] = seasons
            except (ValueError, IndexError):
                continue

        # 保存缓存供下次使用
        try:
            cache_dir = _os.path.dirname(__file__) + "/../data"
            _os.makedirs(cache_dir, exist_ok=True)
            with open(_os.path.join(cache_dir, "seasons_cache.json"), "w") as f:
                _json.dump(result, f)
        except Exception as e:
            logger.warning(f"保存赛季缓存失败: {e}")

        logger.info(f"fetch_all_seasons: 共获取 {len(result)} 个联赛的赛季信息")
        return result