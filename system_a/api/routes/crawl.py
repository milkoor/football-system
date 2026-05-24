"""爬虫任务路由"""

import uuid
import re
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from config.database import get_db
from config.models import CrawlJob, LeagueIndex

router = APIRouter()

logger = logging.getLogger(__name__)

# 爬虫任务状态常量
CRAWL_STATUS_PENDING = "pending"
CRAWL_STATUS_RUNNING = "running"
CRAWL_STATUS_COMPLETED = "completed"
CRAWL_STATUS_FAILED = "failed"
CRAWL_STATUS_CANCELLED = "cancelled"

# 比赛爬取状态常量
MATCH_CRAWL_STATUS_PENDING = "pending"
MATCH_CRAWL_STATUS_COMPLETED = "completed"
MATCH_CRAWL_STATUS_NO_DATA = "nodata"
MATCH_CRAWL_STATUS_ERROR = "error"


# ============ Pydantic 模型 ============

class CrawlJobCreate(BaseModel):
    """创建爬虫任务请求"""
    league_id: Optional[int] = None
    season_label: Optional[str] = None
    match_ids: Optional[list] = None  # 指定比赛ID列表


class CrawlJobResponse(BaseModel):
    """爬虫任务响应"""
    id: int
    job_id: str
    job_type: Optional[str] = "crawl_odds"
    league_id: Optional[int] = None
    season_label: Optional[str] = None
    match_ids: Optional[str] = None
    status: str
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============ 内部函数 ============

def run_crawl_task(job_id: int):
    """实际执行爬虫任务的函数"""
    # 注意：后台任务不能使用请求生命周期的db会话，必须自己创建新的会话
    import json
    from config.database import SessionLocal
    from scraper.odds_crawler import OddsCrawler

    db = SessionLocal()
    try:
        # 原子更新，避免TOCTOU竞态条件
        updated = db.query(CrawlJob).filter(CrawlJob.id == job_id).update({
            "status": "running",
            "started_at": datetime.utcnow()
        })
        if not updated:
            return

        # 加载任务对象（update返回行数而非对象）
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if not job:
            return

        # 创建爬虫实例
        crawler = OddsCrawler()

        # 确定要爬取的比赛 ID 列表（仅跳过已经爬取过的）
        match_ids = []
        skipped_completed = 0

        from config.models import Match
        if job.match_ids:
            # 如果任务指定了 match_ids（从 JSON 字符串解析）
            try:
                requested_ids = json.loads(job.match_ids)

                # 批量查询比赛状态，N+1优化为1次查询
                matches = db.query(Match.match_id, Match.crawl_status).filter(
                    Match.match_id.in_(requested_ids)
                ).all()

                completed_ids = {m.match_id for m in matches if m.crawl_status == "completed"}
                match_ids = [mid for mid in requested_ids if mid not in completed_ids]
                skipped_completed = len(completed_ids)

                if skipped_completed:
                    logger.info(f"已跳过 {skipped_completed} 场已爬取的比赛")

            except json.JSONDecodeError:
                logger.error(f"解析 match_ids 失败: {job.match_ids}")
                match_ids = []
        elif job.league_id:
            # 否则从数据库获取该联赛的比赛
            q = db.query(Match).filter(Match.league_id == job.league_id)
            if job.season_label:
                q = q.filter(Match.season == job.season_label)

            # 只爬取未完成的比赛（completed 表示已爬取且完赛）
            from sqlalchemy import or_
            match_ids = [
                m.match_id for m in
                q.filter(
                    or_(
                        Match.crawl_status.is_(None),
                        Match.crawl_status != MATCH_CRAWL_STATUS_COMPLETED
                    )
                ).with_entities(Match.match_id).all()
            ]
            total_matches = q.count()
            skipped_completed = total_matches - len(match_ids)

            if skipped_completed:
                logger.info(f"已跳过 {skipped_completed} 场已爬取的比赛")

        total = len(match_ids)
        # 更新实际需爬取总数（start_crawl中预计算的包含了已完成的）
        job.total_matches = total
        db.commit()

        if total == 0:
            logger.info("无需爬取新比赛，全部已完成")
            job.status = CRAWL_STATUS_COMPLETED
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        logger.info(f"准备爬取 {total} 场比赛的赔率")

        # 爬取每场比赛的赔率数据（并发版本）
        completed = 0
        failed = 0
        skipped = 0
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        # Thread-local storage for crawler instances (each thread gets its own)
        thread_local = threading.local()

        def get_crawler():
            """Get or create a crawler instance for the current thread"""
            if not hasattr(thread_local, "crawler"):
                thread_local.crawler = OddsCrawler()
            return thread_local.crawler

        def crawl_one(match_id: int) -> tuple[bool, int]:
            """Crawl a single match, return (success, match_id)"""
            try:
                crawler = get_crawler()
                result = crawler.crawl_and_save(match_id, odds_types=["AH"])
                success = result.get("AH", 0) > 0
                return success, match_id
            except Exception as e:
                logger.error(f"爬取比赛 {match_id} 失败: {e}")
                return False, match_id

        # Use 3 concurrent workers by default (adjust based on target website tolerance)
        max_workers = 3
        logger.info(f"开始并发爬取，最大并发数: {max_workers}")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all crawl tasks
            futures = {executor.submit(crawl_one, match_id): match_id for match_id in match_ids}

            # Process results as they complete
            for idx, future in enumerate(as_completed(futures), 1):
                success, match_id = future.result()
                if success:
                    completed += 1
                else:
                    failed += 1

                # 每爬取10场更新一次进度，或者最后一场更新
                if idx % 10 == 0 or idx == total:
                    # 更新任务进度
                    current_job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
                    if current_job:
                        current_job.completed_matches = completed
                        current_job.failed_matches = failed
                        db.commit()
                    logger.info(f"爬取进度: {idx}/{total}, 成功 {completed}, 失败 {failed}")

        logger.info(f"任务完成: 成功 {completed}, 失败 {failed}, 已爬取跳过 {skipped_completed}")

        # 最终更新任务状态
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if job:
            job.status = CRAWL_STATUS_COMPLETED
            job.completed_at = datetime.utcnow()
            job.completed_matches = completed
            job.failed_matches = failed
            db.commit()

    except Exception as e:
        if 'job' in locals() and job:
            job.status = CRAWL_STATUS_FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


# ============ 路由 ============

@router.get("/crawl/jobs", response_model=list[CrawlJobResponse])
async def get_crawl_jobs(
    status: Optional[str] = Query(None, description="任务状态"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取爬虫任务列表"""
    query = db.query(CrawlJob)

    if status:
        query = query.filter(CrawlJob.status == status)

    jobs = query.order_by(CrawlJob.created_at.desc())\
        .limit(limit)\
        .all()

    return jobs


@router.get("/crawl/jobs/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """获取单个爬虫任务详情（支持通过数据库ID或job_uuid查询）"""
    # 先尝试通过数据库ID查询
    job = None
    try:
        job_id_int = int(job_id)
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id_int).first()
    except ValueError:
        pass

    # 如果没找到，尝试通过job_uuid查询
    if not job:
        job = db.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    return job


@router.post("/crawl/start", response_model=CrawlJobResponse)
async def start_crawl(
    request: CrawlJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """触发爬虫任务"""
    import json

    # 生成任务 ID
    job_uuid = str(uuid.uuid4())[:8]

    # 确定要爬取的联赛
    league_id = request.league_id
    season_label = request.season_label or "2024-2025"

    # 序列化 match_ids 为 JSON 字符串
    match_ids_json = None
    if request.match_ids:
        match_ids_json = json.dumps(request.match_ids)

    # 创建任务记录
    job = CrawlJob(
        job_id=job_uuid,
        job_type="crawl_odds",
        league_id=league_id,
        season_label=season_label,
        match_ids=match_ids_json,
        status=CRAWL_STATUS_PENDING,
        total_matches=0,
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 实际需爬取数量由背景任务 run_crawl_task 在过滤已完成比赛后计算
    job.total_matches = 0

    db.commit()

    # 启动后台任务 - 不要传递当前请求的db会话，后台任务会自己创建新的会话
    background_tasks.add_task(run_crawl_task, job.id)

    return job


@router.post("/crawl/stop/{job_id}")
async def stop_crawl(
    job_id: int,
    db: Session = Depends(get_db),
):
    """停止爬虫任务"""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="任务无法停止")

    job.status = CRAWL_STATUS_CANCELLED
    job.completed_at = datetime.utcnow()
    db.commit()

    return {"message": "任务已停止"}


@router.get("/crawl/stats")
async def get_crawl_stats(db: Session = Depends(get_db)):
    """获取爬虫统计信息"""
    from config.models import Match

    total_matches = db.query(Match).count()
    pending = db.query(Match).filter(Match.crawl_status == "pending").count()
    completed = db.query(Match).filter(Match.crawl_status == "completed").count()
    error = db.query(Match).filter(Match.crawl_status == "error").count()

    # 活跃任务
    active_jobs = db.query(CrawlJob).filter(
        CrawlJob.status.in_(["pending", "running"])
    ).count()

    return {
        "total_matches": total_matches,
        "pending": pending,
        "completed": completed,
        "error": error,
        "active_jobs": active_jobs,
    }