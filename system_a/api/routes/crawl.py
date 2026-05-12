"""爬虫任务路由"""

import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from config.database import get_db
from config.models import CrawlJob, LeagueIndex

router = APIRouter()

logger = logging.getLogger(__name__)


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

    class Config:
        from_attributes = True


# ============ 内部函数 ============

def run_crawl_task(job_id: int, db: Session):
    """实际执行爬虫任务的函数"""
    # 注意：这里需要实际调用爬虫逻辑
    # 由于在后台任务中，需要重新获取数据库会话
    import json
    from config.database import SessionLocal
    from scraper.odds_crawler import OddsCrawler

    db = SessionLocal()
    try:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # 创建爬虫实例
        crawler = OddsCrawler()

        # 确定要爬取的比赛 ID 列表（智能过滤：跳过已完成的比赛）
        match_ids = []
        skipped_completed = 0

        if job.match_ids:
            # 如果任务指定了 match_ids（从 JSON 字符串解析）
            try:
                from config.models import Match
                requested_ids = json.loads(job.match_ids)

                # 过滤已完成的比赛
                for match_id in requested_ids:
                    match = db.query(Match).filter(Match.match_id == match_id).first()
                    if match and match.score_ft and match.score_ft.strip():
                        logger.info(f"跳过已完成的比赛: {match_id}")
                        skipped_completed += 1
                    else:
                        match_ids.append(match_id)

            except json.JSONDecodeError:
                logger.error(f"解析 match_ids 失败: {job.match_ids}")
                match_ids = []
        elif job.league_id:
            # 否则从数据库获取该联赛的比赛，过滤已完成的
            from config.models import Match
            matches = db.query(Match).filter(
                Match.league_id == job.league_id,
            ).all()

            # 智能过滤：只爬取未完成的比赛
            for match in matches:
                is_completed = match.score_ft and match.score_ft.strip()
                if is_completed:
                    logger.info(f"跳过已完成的比赛: {match.match_id}")
                    skipped_completed += 1
                else:
                    match_ids.append(match.match_id)

        logger.info(f"准备爬取 {len(match_ids)} 场比赛，已跳过 {skipped_completed} 场已完成比赛")

        # 爬取每场比赛的赔率数据
        completed = 0
        failed = 0
        skipped = 0
        for match_id in match_ids:
            try:
                result = crawler.crawl_and_save(match_id, odds_types=["AH"])
                if result.get("AH", 0) > 0:
                    completed += 1
                else:
                    # 如果返回 0 可能是比赛已完成被跳过
                    # 检查是否真的是已完成
                    from scraper.odds_crawler import OddsCrawler
                    temp_crawler = OddsCrawler()
                    if temp_crawler.is_match_completed(match_id):
                        skipped += 1
                    else:
                        failed += 1
            except Exception as e:
                logger.error(f"爬取比赛 {match_id} 失败: {e}")
                failed += 1

        logger.info(f"任务完成: 成功 {completed}, 失败 {failed}, 已完成比赛跳过 {skipped}")

        # 更新任务状态
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.completed_matches = completed
        job.failed_matches = failed
        db.commit()

    except Exception as e:
        job.status = "failed"
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
        status="pending",
        total_matches=0,
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 计算总比赛数
    if request.match_ids:
        # 如果指定了比赛 ID 列表
        job.total_matches = len(request.match_ids)
    elif league_id:
        # 否则获取该联赛的比赛数量
        from config.models import Match
        match_count = db.query(Match).filter(
            Match.league_id == league_id,
        ).count()
        job.total_matches = match_count

    db.commit()

    # 启动后台任务
    background_tasks.add_task(run_crawl_task, job.id, db)

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

    job.status = "cancelled"
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