"""关注名单管理模块

功能：
- 添加联赛赛季到关注名单
- 从关注名单移除
- 获取关注名单
- 检查是否在关注名单中
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FollowListManager:
    """关注名单管理器"""

    def __init__(self, storage_path: str = "data/follow_list.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._follow_list: List[Dict[str, Any]] = self._load()
        # Index for O(1) lookups by league_id
        self._league_index: Dict[int, Dict[str, Any]] = {
            item["league_id"]: item for item in self._follow_list
        }

    def _load(self) -> List[Dict[str, Any]]:
        """从文件加载关注名单"""
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"加载关注名单失败: {e}")
            return []

    def _save(self):
        """保存关注名单到文件"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._follow_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存关注名单失败: {e}")

    def add(
        self,
        league_id: int,
        league_name: str,
        country: str = ""
    ) -> bool:
        """添加联赛到关注名单"""
        # 检查是否已存在 (O(1) lookup)
        if league_id in self._league_index:
            logger.warning(f"已在关注名单中: {league_name}")
            return False

        new_item = {
            'league_id': league_id,
            'league_name': league_name,
            'country': country,
            'added_at': None,
            'seasons': [],  # 后续会自动填充近2个赛季
            'group_mapping': {}  # 赛季分组映射配置
        }
        self._follow_list.append(new_item)
        self._league_index[league_id] = new_item
        self._save()
        logger.info(f"添加到关注名单: {league_name}")
        return True

    def remove(self, league_id: int) -> bool:
        """从关注名单移除联赛"""
        original_len = len(self._follow_list)
        self._follow_list = [
            item for item in self._follow_list
            if item.get('league_id') != league_id
        ]

        if len(self._follow_list) < original_len:
            # Remove from index
            if league_id in self._league_index:
                del self._league_index[league_id]
            self._save()
            logger.info(f"从关注名单移除: {league_id}")
            return True
        return False

    def is_following(self, league_id: int) -> bool:
        """检查联赛是否在关注名单中"""
        return league_id in self._league_index

    def get_all(self) -> List[Dict[str, Any]]:
        """获取关注名单"""
        return self._follow_list.copy()

    def clear(self):
        """清空关注名单"""
        self._follow_list = []
        self._league_index.clear()
        self._save()
        logger.info("清空关注名单")

    def get_league(self, league_id: int) -> Optional[Dict[str, Any]]:
        """获取单个关注联赛的信息"""
        item = self._league_index.get(league_id)
        return item.copy() if item else None

    def update_seasons(self, league_id: int, seasons: List[str]) -> bool:
        """更新联赛的同步赛季列表"""
        item = self._league_index.get(league_id)
        if item:
            item['seasons'] = seasons
            self._save()
            logger.info(f"更新联赛 {league_id} 赛季列表: {seasons}")
            return True
        return False

    def update_group_mapping(self, league_id: int, mapping: Dict[str, str]) -> bool:
        """更新联赛的分组映射配置
        mapping格式: {"当前赛季组别": "对应上赛季组别"}
        例如: {"A组": "A组", "保级赛": "保级附加赛"}
        """
        item = self._league_index.get(league_id)
        if item:
            item['group_mapping'] = mapping
            self._save()
            logger.info(f"更新联赛 {league_id} 分组映射: {mapping}")
            return True
        return False

    def update_season_groups(self, league_id: int, season_groups: Dict[str, Dict[str, str]]) -> bool:
        """更新联赛各赛季的子联赛/组名称（同步时写入，供分组映射面板读取）
        season_groups格式: {"赛季标签": {"组ID": "组名"}}
        例如: {"2025-2026": {"1722": "聯賽", "0": "全部"}, "2024-2025": {"0": "全部"}}
        """
        item = self._league_index.get(league_id)
        if item:
            item['season_groups'] = season_groups
            self._save()
            logger.info(f"更新联赛 {league_id} 赛季分组: {season_groups}")
            return True
        return False


# 全局实例
_follow_manager: FollowListManager = None


def get_follow_manager() -> FollowListManager:
    """获取关注名单管理器单例"""
    global _follow_manager
    if _follow_manager is None:
        _follow_manager = FollowListManager()
    return _follow_manager
