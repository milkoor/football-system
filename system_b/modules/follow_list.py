"""关注名单管理模块

功能：
- 添加联赛赛季到关注名单
- 从关注名单移除
- 获取关注名单
- 检查是否在关注名单中
"""

import json
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FollowListManager:
    """关注名单管理器"""

    def __init__(self, storage_path: str = "data/follow_list.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._follow_list: List[Dict[str, Any]] = self._load()

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
        season_label: str,
        country: str = ""
    ) -> bool:
        """添加联赛赛季到关注名单"""
        # 检查是否已存在
        for item in self._follow_list:
            if (item.get('league_id') == league_id and
                item.get('season_label') == season_label):
                logger.warning(f"已在关注名单中: {league_name} - {season_label}")
                return False

        self._follow_list.append({
            'league_id': league_id,
            'league_name': league_name,
            'season_label': season_label,
            'country': country,
            'added_at': None
        })
        self._save()
        logger.info(f"添加到关注名单: {league_name} - {season_label}")
        return True

    def remove(self, league_id: int, season_label: str) -> bool:
        """从关注名单移除"""
        original_len = len(self._follow_list)
        self._follow_list = [
            item for item in self._follow_list
            if not (item.get('league_id') == league_id and
                    item.get('season_label') == season_label)
        ]

        if len(self._follow_list) < original_len:
            self._save()
            logger.info(f"从关注名单移除: {league_id} - {season_label}")
            return True
        return False

    def is_following(self, league_id: int, season_label: str) -> bool:
        """检查是否在关注名单中"""
        for item in self._follow_list:
            if (item.get('league_id') == league_id and
                item.get('season_label') == season_label):
                return True
        return False

    def get_all(self) -> List[Dict[str, Any]]:
        """获取关注名单"""
        return self._follow_list.copy()

    def clear(self):
        """清空关注名单"""
        self._follow_list = []
        self._save()
        logger.info("清空关注名单")


# 全局实例
_follow_manager: FollowListManager = None


def get_follow_manager() -> FollowListManager:
    """获取关注名单管理器单例"""
    global _follow_manager
    if _follow_manager is None:
        _follow_manager = FollowListManager()
    return _follow_manager
