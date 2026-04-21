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