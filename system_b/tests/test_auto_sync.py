"""自动同步模块测试"""
import pytest
from unittest.mock import Mock, patch
from modules.auto_sync import SyncScheduler


class TestSyncScheduler:
    """测试同步调度器"""

    @pytest.fixture
    def mock_connector(self):
        """创建mock数据连接器"""
        connector = Mock()
        connector.sync_seasons_for_league = Mock(return_value={"success": True})
        connector.trigger_crawl = Mock(return_value={"success": True})
        connector.calculate_x_values = Mock(return_value={"success": True})
        return connector

    @pytest.fixture
    def mock_follow_manager(self):
        """创建mock关注管理器"""
        follow_manager = Mock()
        follow_manager.get_all = Mock(return_value=[])
        return follow_manager

    @pytest.fixture
    def mock_settings_enabled(self):
        """创建启用同步的mock设置"""
        settings = Mock()
        settings.sync_enabled = True
        settings.sync_interval_hours = 24
        return settings

    @pytest.fixture
    def mock_settings_disabled(self):
        """创建禁用同步的mock设置"""
        settings = Mock()
        settings.sync_enabled = False
        settings.sync_interval_hours = 24
        return settings

    def test_scheduler_created_when_sync_enabled(self, mock_connector, mock_follow_manager, mock_settings_enabled):
        """测试当同步启用时创建调度器"""
        scheduler = SyncScheduler(mock_connector, mock_follow_manager, mock_settings_enabled)
        assert scheduler.scheduler is not None
        assert len(scheduler.scheduler.get_jobs()) == 1

    def test_scheduler_not_created_when_sync_disabled(self, mock_connector, mock_follow_manager, mock_settings_disabled):
        """测试当同步禁用时不创建调度器"""
        scheduler = SyncScheduler(mock_connector, mock_follow_manager, mock_settings_disabled)
        assert scheduler.scheduler is None

    def test_sync_job_executes_full_chain(self, mock_connector, mock_follow_manager, mock_settings_enabled):
        """测试同步任务执行完整方法链"""
        # 模拟关注名单
        mock_follow_manager.get_all.return_value = [
            {"league_id": 1, "season_label": "2025-2026", "league_name": "英超"},
            {"league_id": 2, "season_label": "2025-2026", "league_name": "西甲"}
        ]

        scheduler = SyncScheduler(mock_connector, mock_follow_manager, mock_settings_enabled)

        # 直接调用同步任务
        scheduler.run_sync_job()

        # 验证所有方法都被调用
        assert mock_follow_manager.get_all.called
        assert mock_connector.sync_seasons_for_league.called
        assert mock_connector.trigger_crawl.called
        assert mock_connector.calculate_x_values.called

        # 验证每个关注的联赛都被处理
        assert mock_connector.sync_seasons_for_league.call_count == 2
        assert mock_connector.trigger_crawl.call_count == 2
        assert mock_connector.calculate_x_values.call_count == 2

    def test_sync_job_handles_empty_follow_list(self, mock_connector, mock_follow_manager, mock_settings_enabled):
        """测试同步任务处理空关注名单的情况"""
        mock_follow_manager.get_all.return_value = []

        scheduler = SyncScheduler(mock_connector, mock_follow_manager, mock_settings_enabled)
        scheduler.run_sync_job()

        # 验证没有调用后续方法
        mock_connector.sync_seasons_for_league.assert_not_called()
        mock_connector.trigger_crawl.assert_not_called()
        mock_connector.calculate_x_values.assert_not_called()

    def test_sync_job_handles_error_gracefully(self, mock_connector, mock_follow_manager, mock_settings_enabled):
        """测试同步任务优雅处理错误"""
        mock_follow_manager.get_all.return_value = [
            {"league_id": 1, "season_label": "2025-2026", "league_name": "英超"},
            {"league_id": 2, "season_label": "2025-2026", "league_name": "西甲"}
        ]

        # 第一个联赛同步时抛出异常
        mock_connector.sync_seasons_for_league.side_effect = Exception("同步失败")

        scheduler = SyncScheduler(mock_connector, mock_follow_manager, mock_settings_enabled)

        # 应该不会抛出异常
        scheduler.run_sync_job()

        # 验证第二个联赛仍被处理
        assert mock_connector.sync_seasons_for_league.call_count == 2
