"""自动同步模块"""
import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional

logger = logging.getLogger(__name__)


class SyncScheduler:
    """自动同步调度器"""

    def __init__(self, connector, follow_manager, settings):
        self.connector = connector
        self.follow_manager = follow_manager
        self.settings = settings
        self.scheduler: Optional[BackgroundScheduler] = None

        # 创建并启动调度器
        self.scheduler = self._create_scheduler()

        if self.scheduler:
            logger.info("自动同步调度器初始化成功")
            # 注册关闭钩子
            atexit.register(self._shutdown_scheduler)
        else:
            logger.info("自动同步功能已禁用")

    def _create_scheduler(self) -> Optional[BackgroundScheduler]:
        """创建调度器"""
        if not self.settings.sync_enabled:
            return None

        scheduler = BackgroundScheduler()
        trigger = IntervalTrigger(hours=self.settings.sync_interval_hours)
        scheduler.add_job(
            self.run_sync_job,
            trigger=trigger,
            id="auto_sync_job",
            name="自动同步任务"
        )
        scheduler.start()
        return scheduler

    def _shutdown_scheduler(self):
        """关闭调度器"""
        if self.scheduler:
            logger.info("正在关闭自动同步调度器")
            self.scheduler.shutdown(wait=True)
            logger.info("自动同步调度器已关闭")

    def run_sync_job(self):
        """运行同步任务"""
        logger.info("开始自动同步任务")

        try:
            # 获取关注名单
            follow_list = self.follow_manager.get_all()
            logger.info(f"关注名单包含 {len(follow_list)} 个联赛赛季")

            if not follow_list:
                logger.info("关注名单为空，跳过同步")
                return

            # 逐个同步联赛赛季
            for item in follow_list:
                league_id = item.get("league_id")
                season_label = item.get("season_label")
                league_name = item.get("league_name", f"联赛{league_id}")

                logger.info(f"开始同步: {league_name} - {season_label}")

                try:
                    # 同步赛季赛程
                    logger.debug(f"同步赛季赛程: league_id={league_id}, season={season_label}")
                    self.connector.sync_seasons_for_league(league_id, season_label)

                    # 触发爬取
                    logger.debug(f"触发爬取: league_id={league_id}, season={season_label}")
                    self.connector.trigger_crawl(league_id, season_label)

                    # 计算X值
                    logger.debug(f"计算X值: league_id={league_id}, season={season_label}")
                    self.connector.calculate_x_values(league_id, season_label)

                    logger.info(f"同步完成: {league_name} - {season_label}")
                except Exception as e:
                    logger.error(f"同步失败 {league_name} - {season_label}: {str(e)}")
                    continue

            logger.info("所有同步任务完成")
        except Exception as e:
            logger.error(f"自动同步任务失败: {str(e)}")

    def get_scheduler(self) -> Optional[BackgroundScheduler]:
        """获取调度器实例"""
        return self.scheduler
