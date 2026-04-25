"""X值结果路由"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from config.database import get_db
from config.models import XValueResult, Match

router = APIRouter()


# ============ Pydantic 模型 ============

class XValueResultCreate(BaseModel):
    """创建X值结果请求"""
    match_id: int
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    score: Optional[str] = None
    target_team: Optional[str] = None
    has_star_mark: Optional[bool] = None
    x_value: Optional[float] = None
    status: str
    calculation_note: Optional[str] = None
    movement_url: Optional[str] = None


class XValueResultResponse(BaseModel):
    """X值结果响应"""
    id: int
    match_id: int
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    score: Optional[str] = None
    target_team: Optional[str] = None
    has_star_mark: Optional[bool] = None
    x_value: Optional[float] = None
    status: str
    calculation_note: Optional[str] = None
    movement_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 路由 ============

@router.get("/x-values", response_model=List[XValueResultResponse])
async def get_x_values(
    match_id: Optional[int] = Query(None, description="比赛ID"),
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """获取X值计算结果列表"""
    query = db.query(XValueResult)

    if match_id is not None:
        query = query.filter(XValueResult.match_id == match_id)
    if status:
        query = query.filter(XValueResult.status == status)

    results = query.order_by(XValueResult.created_at.desc()).limit(limit).all()
    return results


@router.get("/x-values/{match_id}", response_model=XValueResultResponse)
async def get_x_value(
    match_id: int,
    db: Session = Depends(get_db),
):
    """获取单个比赛的X值计算结果"""
    result = db.query(XValueResult).filter(
        XValueResult.match_id == match_id
    ).order_by(XValueResult.created_at.desc()).first()

    if not result:
        raise HTTPException(status_code=404, detail="X值结果不存在")

    return result


@router.post("/x-values", response_model=XValueResultResponse)
async def create_x_value(
    x_value: XValueResultCreate,
    db: Session = Depends(get_db),
):
    """创建X值计算结果"""
    # 检查比赛是否存在
    match = db.query(Match).filter(Match.match_id == x_value.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    # 创建X值结果
    db_x_value = XValueResult(**x_value.model_dump())
    db.add(db_x_value)
    db.commit()
    db.refresh(db_x_value)

    return db_x_value


@router.put("/x-values/{match_id}", response_model=XValueResultResponse)
async def update_x_value(
    match_id: int,
    x_value: XValueResultCreate,
    db: Session = Depends(get_db),
):
    """更新X值计算结果"""
    # 查找该比赛的最新X值结果
    db_x_value = db.query(XValueResult).filter(
        XValueResult.match_id == match_id
    ).order_by(XValueResult.created_at.desc()).first()

    if not db_x_value:
        # 如果不存在，则创建新的
        db_x_value = XValueResult(**x_value.model_dump())
        db.add(db_x_value)
    else:
        # 更新现有记录
        for key, value in x_value.model_dump().items():
            setattr(db_x_value, key, value)

    db.commit()
    db.refresh(db_x_value)

    return db_x_value


@router.post("/x-values/calculate")
async def calculate_x_values(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    season_label: Optional[str] = Query(None, description="赛季标签"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """批量计算X值（支持按联赛/赛季或比赛ID列表）"""
    import uuid
    import json

    # 生成任务ID
    job_uuid = str(uuid.uuid4())[:8]

    # 确定要计算的比赛ID列表（智能过滤：跳过已完成的比赛）
    match_ids = []
    skipped_completed = 0

    if league_id and season_label:
        # 按联赛/赛季查询
        from config.models import Match
        matches = db.query(Match).filter(
            Match.league_id == league_id,
            Match.season == season_label
        ).all()

        # 智能过滤：只对未完成的比赛计算X值，或已完成但还没有X值的比赛
        for match in matches:
            is_completed = match.score_ft and match.score_ft.strip()

            # 检查是否已有X值结果
            existing_x = db.query(XValueResult).filter(
                XValueResult.match_id == match.match_id
            ).first()

            if is_completed and existing_x:
                # 已完成且已有X值：跳过
                logger.info(f"跳过已完成且已有X值的比赛: {match.match_id}")
                skipped_completed += 1
            else:
                # 未完成，或已完成但需要重新计算：加入列表
                match_ids.append(match.match_id)

        logger.info(f"准备计算 {len(match_ids)} 场比赛的X值，已跳过 {skipped_completed} 场已完成比赛")
    else:
        raise HTTPException(status_code=400, detail="需要提供 league_id 和 season_label 参数")

    if not match_ids:
        raise HTTPException(status_code=404, detail="未找到符合条件的比赛")

    # 创建爬虫任务记录（复用 CrawlJob 表）
    from config.models import CrawlJob
    job = CrawlJob(
        job_id=job_uuid,
        league_id=league_id,
        season_label=season_label,
        match_ids=json.dumps(match_ids),
        status="pending",
        total_matches=len(match_ids),
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 后台任务函数
    def run_calculate_task(job_id: int):
        import json
        from config.database import SessionLocal
        from modules.x_calculator import XValueCalculator

        db = SessionLocal()
        try:
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if not job:
                return

            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()

            # 解析match_ids
            match_ids = []
            if job.match_ids:
                try:
                    match_ids = json.loads(job.match_ids)
                except json.JSONDecodeError:
                    logger.error(f"解析 match_ids 失败: {job.match_ids}")

            if not match_ids:
                job.status = "failed"
                job.error_message = "没有找到需要计算X值的比赛"
                job.completed_at = datetime.utcnow()
                db.commit()
                return

            # 计算X值
            calculator = XValueCalculator()
            completed = 0
            failed = 0

            for match_id in match_ids:
                try:
                    # 计算X值
                    result = calculator.calculate(match_id)
                    if result.get('status') == 'success':
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"计算比赛 {match_id} 的X值失败: {e}")
                    failed += 1

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

    # 启动后台任务
    background_tasks.add_task(run_calculate_task, job.id)

    return {
        "message": f"X值计算任务已启动，将计算 {len(match_ids)} 场比赛",
        "job_id": job.job_id,
        "status": "started"
    }