"""自动同步模块"""
import logging
import atexit
import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional

from utils.system_a_mapper import import_matches_to_system_b

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "auto_sync_config.json")


def _load_config() -> dict:
    """从文件加载运行时配置"""
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(config: dict):
    """保存运行时配置到文件"""
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(config, f)


class SyncScheduler:
    """自动同步调度器"""

    def __init__(self, connector, follow_manager, settings, store=None):
        self.connector = connector
        self.follow_manager = follow_manager
        self.settings = settings
        self.store = store
        self.scheduler: Optional[BackgroundScheduler] = None

        # 从运行时配置覆盖 env 设置
        runtime = _load_config()
        self._interval = runtime.get("interval_hours", settings.sync_interval_hours)
        self._enabled = runtime.get("enabled", settings.sync_enabled)

        self.scheduler = self._create_scheduler()
        if self.scheduler:
            logger.info(f"自动同步调度器已启动 (间隔={self._interval}h)")
            atexit.register(self._shutdown_scheduler)
        else:
            logger.info("自动同步功能已禁用")

    def _create_scheduler(self) -> Optional[BackgroundScheduler]:
        if not self._enabled:
            return None
        scheduler = BackgroundScheduler()
        trigger = IntervalTrigger(hours=self._interval)
        scheduler.add_job(self.run_sync_job, trigger=trigger, id="auto_sync_job", name="自动同步任务")
        scheduler.start()
        return scheduler

    def reschedule(self, interval_hours: int, enabled: bool):
        """运行时修改同步间隔和启停状态"""
        self._interval = interval_hours
        self._enabled = enabled

        # 持久化到文件
        _save_config({"interval_hours": interval_hours, "enabled": enabled})

        # 重启调度器
        self._shutdown_scheduler()
        self.scheduler = self._create_scheduler()
        status = "已启动" if self.scheduler else "已停用"
        logger.info(f"自动同步调度器已重新配置: {status}, 间隔={interval_hours}h")

    def _shutdown_scheduler(self):
        if self.scheduler:
            logger.info("正在关闭自动同步调度器")
            self.scheduler.shutdown(wait=True)
            self.scheduler = None
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

                    # 计算并导入X值。如果挂了 store，统一通过 _import_to_system_b 完成
                    # （内部会调 batch_calculate + save_x_value），避免重复计算
                    if self.store:
                        self._import_to_system_b(league_id, season_label, league_name)
                    else:
                        logger.debug(f"计算X值: league_id={league_id}, season={season_label}")
                        self.connector.calculate_x_values(league_id, season_label)

                    logger.info(f"同步完成: {league_name} - {season_label}")
                except Exception as e:
                    logger.error(f"同步失败 {league_name} - {season_label}: {str(e)}")
                    continue

            logger.info("所有同步任务完成")
        except Exception as e:
            logger.error(f"自动同步任务失败: {str(e)}")

    def _import_to_system_b(self, league_id, season_label, league_name):
        """将System A的比赛和X值导入System B本地SQLite"""

        try:
            # 分页获取所有比赛，避免单次请求过大
            matches = []
            page = 1
            page_size = 1000  # 使用较小的分页大小，平衡请求次数和性能

            while True:
                mr = self.connector.get_matches(
                    league_id=league_id, season=season_label,
                    crawl_status='completed', page=page, page_size=page_size,
                )
                page_matches = mr.get('matches') or mr.get('data') or []
                if not page_matches:
                    break
                matches.extend(page_matches)
                if len(page_matches) < page_size:
                    break
                page += 1

            if not matches:
                logger.info(f"没有需要导入的比赛: {league_name}")
                return

            result = import_matches_to_system_b(
                self.store, self.connector, matches,
            )
            logger.info(
                f"System B导入完成: {league_name}, "
                f"导入 {result['imported']} 条记录"
            )
        except Exception as e:
            logger.error(f"System B导入失败 {league_name}: {e}")

    def get_scheduler(self) -> Optional[BackgroundScheduler]:
        """获取调度器实例"""
        return self.scheduler
