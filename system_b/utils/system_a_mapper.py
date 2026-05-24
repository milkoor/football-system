"""
系统A到系统B的映射工具
用于同步系统A的联赛和赛季数据到系统B的存储
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from core.config_store import get_store
from core.models import MatchRecord
from modules.data_connector import get_connector


logger = logging.getLogger(__name__)


def get_league_display_name(league_data: Dict[str, Any]) -> str:
    """获取联赛显示名称（繁体中文优先，简体中文降级）"""
    name = league_data.get('league_name_tw', '')
    if not name or name.strip() == '':
        name = league_data.get('league_name_zh', '')
    if not name or name.strip() == '':
        name = league_data.get('league_name', f"联赛{league_data.get('id', '')}")
    return name.strip()


def find_league_by_name_fuzzy(leagues: List[Dict], search_name: str) -> Optional[Dict]:
    """模糊查找联赛"""
    if not search_name:
        return None

    for lg in leagues:
        for key in ('league_name_tw', 'league_name_zh', 'league_name'):
            if lg.get(key, '') == search_name:
                return lg

    for lg in leagues:
        for key in ('league_name_tw', 'league_name_zh', 'league_name'):
            lg_name = lg.get(key, '')
            if search_name in lg_name or lg_name in search_name:
                return lg

    return None


def extract_round_number(round_name: Optional[str]) -> int:
    """从轮次名称中提取数字，如 '第38轮' → 38"""
    if not round_name:
        return 0
    m = re.search(r'(\d+)', str(round_name))
    return int(m.group(1)) if m else 0


def extract_group_from_round(round_name: Optional[str]) -> str:
    """从轮次/组名中提取组别，如 'A组'、'附加赛'"""
    return (round_name or '').strip()


def get_season_groups(connector, league_id: int, season_label: str) -> Dict[str, str]:
    """获取指定联赛赛季的组别信息

    Args:
        connector: 数据连接器
        league_id: 系统A的联赛DB id（league_index.id）
        season_label: 赛季标签

    Returns:
        {group_id: group_name}
    """
    try:
        # 先获取联赛信息，将系统A的DB id映射为titan007的league_id
        response = connector._request("GET", f"/api/leagues/{league_id}")
        titan007_league_id = response.get("league_id")
        if not titan007_league_id:
            logger.warning(f"联赛 {league_id} 没有titan007 league_id")
            return {}
        return connector.get_sub_league_names(titan007_league_id, season_label)
    except Exception as e:
        logger.warning(f"获取赛季组别失败: league_id={league_id}, season={season_label}, error={e}")
        return {}


def auto_match_groups(current_groups: Dict[str, str], previous_groups: Dict[str, str]) -> Dict[str, str]:
    """自动匹配当前赛季和上赛季的组别（基于名称相似度）"""
    mapping = {}

    for cur_id, cur_name in current_groups.items():
        best_match = None
        best_score = 0.0

        for prev_id, prev_name in previous_groups.items():
            if not cur_name or not prev_name:
                continue
            common = len(set(cur_name) & set(prev_name))
            union = len(set(cur_name) | set(prev_name))
            score = common / union if union > 0 else 0

            if score > best_score:
                best_score = score
                best_match = prev_id

        if best_match and best_score > 0.3:
            mapping[cur_id] = best_match

    return mapping


def sync_league_to_system_b(store, connector, league_data: Dict[str, Any]) -> int:
    """
    将系统A的联赛同步到系统B

    Args:
        store: 系统B的配置存储实例
        connector: 系统A的数据连接器实例
        league_data: 系统A返回的联赛数据

    Returns:
        int: 系统B中的联赛ID

    Notes:
        - 处理联赛名称的降级逻辑（优先使用繁体中文，其次简体中文）
        - 处理联赛名称为空的情况
        - 正确映射大洲代码
        - 支持更新已存在联赛的名称
    """
    # 映射大陆到系统B的格式
    continent_map = {
        "国际": "",
        "欧洲": "EUR",
        "美洲": "AME",
        "亚洲": "ASI",
        "大洋洲": "",
        "非洲": "AFR"
    }

    continent = continent_map.get(league_data.get('country', ''), '')

    league_name = league_data.get('league_name_tw', '')
    if not league_name or league_name.strip() == '':
        league_name = league_data.get('league_name_zh', '')

    if not league_name or league_name.strip() == '':
        league_name = f"未命名联赛_{league_data.get('id', 'unknown')}"
        logger.warning(f"联赛ID {league_data.get('id')} 名称为空，使用默认名称: {league_name}")
    else:
        league_name = league_name.strip()

    existing_league = store.find_league_by_identity(league_name, None)

    if existing_league:
        league_id = existing_league.id
        if not existing_league.name_zh or existing_league.name_zh.strip() == "":
            store.update_league(league_id, name_zh=league_name)
        if continent and not existing_league.continent:
            store.update_league(league_id, continent=continent)
    else:
        league_id = store.create_league(
            continent=continent,
            code=f"LEAGUE_{league_data['id']}",
            name_zh=league_name,
            league_url_id=str(league_data.get('league_id', '')),
        )

    return league_id


def sync_season_to_system_b(store, league_id: int, season_label: str) -> int:
    """
    将系统A的赛季同步到系统B

    Args:
        store: 系统B的配置存储实例
        league_id: 系统B中的联赛ID
        season_label: 赛季标签（如 "2024-2025"）

    Returns:
        int: 系统B中的赛季ID

    Notes:
        - 支持解析 "YYYY-YYYY" 格式的赛季标签
        - 处理无法解析的赛季格式
        - 自动设置当前赛季
    """
    seasons = store.list_season_instances(league_id)

    existing_season = None
    for s in seasons:
        if s.label == season_label:
            existing_season = s
            break

    if existing_season:
        return existing_season.id

    year_start = datetime.now().year
    if "-" in season_label:
        try:
            year_start = int(season_label.split("-")[0])
        except:
            pass
    else:
        # 年格式（如 "2026"、"2025"）
        try:
            year_start = int(season_label)
        except:
            pass

    season_id = store.create_season_instance(
        league_id=league_id,
        label=season_label,
        year_start=year_start,
        year_end=year_start + 1
    )

    # 只有该联赛没有 current 赛季时才设为 current
    current, _ = store.get_current_previous_pair(league_id)
    if current is None:
        store.set_season_role(season_id, "current")

    return season_id


def import_matches_to_system_b(
    store,
    connector,
    matches: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, int]:
    """
    将系统A的比赛数据导入系统B，并在导入过程中计算X值

    流程:
    1. 对每场比赛计算X值（基于AH赔率变动）
    2. 将比赛记录分组存入系统B的match_records表

    Args:
        store: 系统B的配置存储实例
        connector: 系统A的数据连接器实例
        matches: 系统A的比赛数据列表
        progress_callback: 进度回调 (done, total)

    Returns:
        {'x_success': 成功计算的X值数,
         'x_skipped': 跳过(无赔率/不适合),
         'x_failed': 计算失败的X值数,
         'imported': 导入系统B的记录数}
    """
    from modules.x_calculator import XValueCalculator

    calculator = XValueCalculator(data_connector=connector)

    # 获取系统A所有启用的联赛列表，用于建立ID映射
    try:
        sa_leagues = {lg['id']: lg for lg in connector.get_leagues(enabled=True)}
    except Exception as e:
        logger.error(f"获取系统A联赛列表失败: {e}")
        sa_leagues = {}

    # 联赛/赛季缓存: (system_a_league_id, season_label) → (sb_league_id, sb_season_id, label)
    league_season_cache: Dict[tuple, tuple] = {}

    x_success = 0
    x_skipped = 0
    x_failed = 0

    # batch_records 在循环外部初始化，避免每批覆盖上一批
    batch_records: Dict[tuple, List[MatchRecord]] = {}

    total = len(matches)

    for idx, md in enumerate(matches):
        match_id = md.get('match_id')
        if not match_id:
            continue

        league_id_a = md.get('league_id')
        if not league_id_a:
            continue

        # season: 使用 or 处理 API 返回 null 的情况
        season_label = md.get('season') or '2024-2025'

        # 解析系统B的联赛/赛季ID（带缓存，key 包含赛季，不同赛季不共用缓存）
        cache_key = (league_id_a, season_label)
        if cache_key not in league_season_cache:
            league_data = sa_leagues.get(league_id_a)
            if not league_data:
                logger.warning(f"系统A联赛ID {league_id_a} 不在启用的联赛列表中，跳过")
                continue

            sb_league_id = sync_league_to_system_b(store, connector, league_data)
            sb_season_id = sync_season_to_system_b(store, sb_league_id, season_label)
            league_season_cache[cache_key] = (sb_league_id, sb_season_id, season_label)

        _, sb_season_id, _ = league_season_cache[cache_key]

        # 计算X值
        try:
            x_result = calculator.calculate_from_match(match_id)
        except Exception as e:
            logger.error(f"计算比赛 {match_id} 的X值失败: {e}")
            x_result = {"x_value": None, "status": "error", "calculation_note": str(e)}

        x_value = x_result.get('x_value')

        if x_value is not None:
            x_success += 1
        else:
            status = x_result.get('status', '')
            if status in ('no_data', 'not_suitable'):
                x_skipped += 1
            else:
                x_failed += 1

        # 提取轮次
        round_num = extract_round_number(md.get('round_name'))

        # 提取组别
        group_name = md.get('group_name') or extract_group_from_round(md.get('round_name'))

        # 结算字段 — 使用 or '' 防止 None 违反 NOT NULL 约束
        settlement_value = md.get('settlement_value')
        if settlement_value is None:
            settlement_value = 0.0

        # 每条比赛生成一条 HDP/Early 记录（X值计算基于AH盘口）
        key = (sb_season_id, "HDP", "Early")

        record = MatchRecord(
            round_num=round_num,
            home_team=md.get('home_team') or '',
            score=md.get('score_ft') or '',
            away_team=md.get('away_team') or '',
            x_value=x_value or 0.0,
            settlement=md.get('settlement') or '',
            link=f"https://vip.titan007.com/changeDetail/handicap.aspx?id={match_id}",
            play_type="HDP",
            settlement_value=settlement_value,
            settlement_direction=md.get('settlement_direction') or '',
            home_away_direction=md.get('home_away_direction') or '',
            target_team=md.get('target_team') or '',
            group=group_name,
        )

        if key not in batch_records:
            batch_records[key] = []
        batch_records[key].append(record)

        if progress_callback:
            progress_callback(idx + 1, total)

    # 循环结束后统一 upsert，避免 DELETE+INSERT 覆盖前一批数据
    imported = 0
    for (sid, play_type, timing), records in batch_records.items():
        try:
            n = store.upsert_match_records(sid, play_type, timing, records)
            imported += n
        except Exception as e:
            logger.error(
                f"保存比赛记录失败: season_id={sid}, play_type={play_type}, "
                f"timing={timing}, error={e}"
            )

    logger.info(
        f"导入完成: X值成功={x_success}, 跳过={x_skipped}, "
        f"失败={x_failed}, 导入记录={imported}"
    )

    return {
        'x_success': x_success,
        'x_skipped': x_skipped,
        'x_failed': x_failed,
        'imported': imported,
    }
