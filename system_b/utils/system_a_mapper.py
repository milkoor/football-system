"""
系统A到系统B的映射工具
用于同步系统A的联赛和赛季数据到系统B的存储
"""

import logging
from typing import Dict, Any

from etl.config_store import get_store
from modules.data_connector import get_connector


logger = logging.getLogger(__name__)


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

    # 获取联赛名称，确保不为空
    league_name = league_data.get('league_name_tw', '')
    if not league_name or league_name.strip() == '':
        league_name = league_data.get('league_name_zh', '')

    if not league_name or league_name.strip() == '':
        # 如果都为空，生成一个默认名称
        league_name = f"未命名联赛_{league_data.get('id', 'unknown')}"
        logger.warning(f"联赛ID {league_data.get('id')} 名称为空，使用默认名称: {league_name}")
    else:
        league_name = league_name.strip()

    # 创建或更新联赛
    existing_league = store.find_league_by_identity(
        league_name,
        None
    )

    if existing_league:
        league_id = existing_league.id
        # 如果现有联赛名字为空，更新为正确的名称
        if not existing_league.name_zh or existing_league.name_zh.strip() == "":
            store.update_league(league_id, name_zh=league_name)
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

    # 查找是否已存在
    existing_season = None
    for s in seasons:
        if s.label == season_label:
            existing_season = s
            break

    if existing_season:
        return existing_season.id

    # 解析赛季年份
    year_start = 2024
    if "-" in season_label:
        try:
            year_start = int(season_label.split("-")[0])
        except:
            pass

    season_id = store.create_season_instance(
        league_id=league_id,
        label=season_label,
        year_start=year_start,
        year_end=year_start + 1
    )

    # 设置为current赛季
    store.set_season_role(season_id, "current")

    return season_id
