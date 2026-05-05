"""
测试 system_a_mapper.py 中的函数
使用 pytest 和 mock 进行测试
"""

import pytest
from unittest.mock import Mock
from utils.system_a_mapper import sync_league_to_system_b, sync_season_to_system_b


class TestSyncLeagueToSystemB:
    """测试同步联赛到系统B的函数"""

    def test_sync_league_with_valid_data(self):
        """测试：联赛名称存在且正确映射 continent 和 code"""
        # 创建 mock 对象
        mock_store = Mock()
        mock_connector = Mock()

        # 模拟数据
        league_data = {
            'id': 2064,
            'league_name_tw': '英超',
            'league_name_zh': '英格兰超级联赛',
            'country': '欧洲'
        }

        # 模拟 store.find_league_by_identity 返回 None（表示不存在）
        mock_store.find_league_by_identity.return_value = None

        # 执行测试
        league_id = sync_league_to_system_b(mock_store, mock_connector, league_data)

        # 验证调用
        assert league_id is not None
        mock_store.find_league_by_identity.assert_called_once_with('英超', None)
        mock_store.create_league.assert_called_once()

        # 验证创建联赛时的参数
        call_args = mock_store.create_league.call_args
        assert call_args.kwargs['continent'] == 'EUR'
        assert call_args.kwargs['code'] == 'LEAGUE_2064'
        assert call_args.kwargs['name_zh'] == '英超'

    def test_sync_league_with_empty_name(self):
        """测试：联赛名称为空时的降级处理"""
        # 创建 mock 对象
        mock_store = Mock()
        mock_connector = Mock()

        # 模拟数据 - 联赛名称为空
        league_data = {
            'id': 2064,
            'league_name_tw': '',
            'league_name_zh': '',
            'country': '亚洲'
        }

        # 模拟 store.find_league_by_identity 返回 None（表示不存在）
        mock_store.find_league_by_identity.return_value = None

        # 执行测试
        league_id = sync_league_to_system_b(mock_store, mock_connector, league_data)

        # 验证调用
        assert league_id is not None
        # 应该使用默认名称
        mock_store.find_league_by_identity.assert_called_once()
        call_args = mock_store.create_league.call_args
        assert '未命名联赛' in call_args.kwargs['name_zh']

    def test_sync_league_existing_league(self):
        """测试：find_league_by_identity 返回已有联赛时只更新不创建"""
        # 创建 mock 对象
        mock_store = Mock()
        mock_connector = Mock()

        # 模拟数据
        league_data = {
            'id': 2064,
            'league_name_tw': '英超',
            'league_name_zh': '英格兰超级联赛',
            'country': '欧洲'
        }

        # 模拟已存在的联赛
        existing_league = Mock()
        existing_league.id = 1
        existing_league.name_zh = '英超'
        mock_store.find_league_by_identity.return_value = existing_league

        # 执行测试
        league_id = sync_league_to_system_b(mock_store, mock_connector, league_data)

        # 验证调用
        assert league_id == 1
        mock_store.create_league.assert_not_called()

    def test_sync_league_existing_league_with_empty_name(self):
        """测试：已有联赛名字为空时会更新为正确名称"""
        # 创建 mock 对象
        mock_store = Mock()
        mock_connector = Mock()

        # 模拟数据
        league_data = {
            'id': 2064,
            'league_name_tw': '英超',
            'league_name_zh': '英格兰超级联赛',
            'country': '欧洲'
        }

        # 模拟已存在的联赛，但名称为空
        existing_league = Mock()
        existing_league.id = 1
        existing_league.name_zh = ''
        mock_store.find_league_by_identity.return_value = existing_league

        # 执行测试
        league_id = sync_league_to_system_b(mock_store, mock_connector, league_data)

        # 验证调用
        assert league_id == 1
        mock_store.update_league.assert_called_once_with(1, name_zh='英超')


class TestSyncSeasonToSystemB:
    """测试同步赛季到系统B的函数"""

    def test_sync_season_existing(self):
        """测试：赛季已存在时返回已有ID"""
        # 创建 mock 对象
        mock_store = Mock()

        # 模拟已存在的赛季
        existing_season = Mock()
        existing_season.id = 100
        existing_season.label = '2024-2025'
        mock_store.list_season_instances.return_value = [existing_season]

        # 执行测试
        season_id = sync_season_to_system_b(mock_store, 1, '2024-2025')

        # 验证调用
        assert season_id == 100
        mock_store.create_season_instance.assert_not_called()

    def test_sync_season_new_should_create_and_set_current(self):
        """测试：赛季不存在时创建新赛季并设置为 current"""
        # 创建 mock 对象
        mock_store = Mock()

        # 模拟 list_season_instances 返回空列表（不存在）
        mock_store.list_season_instances.return_value = []
        mock_store.create_season_instance.return_value = 200

        # 执行测试
        season_id = sync_season_to_system_b(mock_store, 1, '2024-2025')

        # 验证调用
        assert season_id == 200
        mock_store.create_season_instance.assert_called_once_with(
            league_id=1,
            label='2024-2025',
            year_start=2024,
            year_end=2025
        )
        mock_store.set_season_role.assert_called_once_with(200, 'current')

    def test_sync_season_parse_year_format(self):
        """测试：解析赛季年份（支持 '2024-2025' 格式）"""
        # 创建 mock 对象
        mock_store = Mock()

        # 模拟 list_season_instances 返回空列表（不存在）
        mock_store.list_season_instances.return_value = []
        mock_store.create_season_instance.return_value = 200

        # 执行测试
        season_id = sync_season_to_system_b(mock_store, 1, '2024-2025')

        # 验证解析的年份
        mock_store.create_season_instance.assert_called_once_with(
            league_id=1,
            label='2024-2025',
            year_start=2024,
            year_end=2025
        )

    def test_sync_season_parse_invalid_year_format(self):
        """测试：异常格式降级"""
        # 创建 mock 对象
        mock_store = Mock()

        # 模拟 list_season_instances 返回空列表（不存在）
        mock_store.list_season_instances.return_value = []
        mock_store.create_season_instance.return_value = 200

        # 测试异常格式
        season_id = sync_season_to_system_b(mock_store, 1, 'invalid-season')

        # 验证降级处理，应该使用默认年份（2024）
        mock_store.create_season_instance.assert_called_once_with(
            league_id=1,
            label='invalid-season',
            year_start=2024,
            year_end=2025
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
