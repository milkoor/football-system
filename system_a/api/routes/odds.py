"""赔率路由"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from config.database import get_db
from config.models import OddsMovement

router = APIRouter()


# ============ Pydantic 模型 ============

class OddsMovementResponse(BaseModel):
    """赔率变动响应"""
    movement_id: int
    match_id: int
    odds_type: str
    is_half_time: bool = False
    elapsed_time: Optional[str] = None
    score_at_time: Optional[str] = None
    update_time: Optional[datetime] = None
    status: Optional[str] = None
    home_rate: Optional[float] = None
    handicap_raw: Optional[str] = None
    handicap_std: Optional[float] = None
    away_rate: Optional[float] = None

    class Config:
        from_attributes = True


class OddsListResponse(BaseModel):
    """赔率列表响应"""
    total: int
    movements: List[OddsMovementResponse]


# ============ 路由 ============

@router.get("/matches/{match_id}/odds", response_model=OddsListResponse)
async def get_match_odds(
    match_id: int,
    odds_type: Optional[str] = Query(None, description="赔率类型: AH, OU, 1x2"),
    status: Optional[str] = Query(None, description="状态: 早, 即, 走"),
    db: Session = Depends(get_db),
):
    """获取比赛的赔率变动历史"""
    query = db.query(OddsMovement).filter(OddsMovement.match_id == match_id)

    if odds_type:
        query = query.filter(OddsMovement.odds_type == odds_type)
    if status:
        query = query.filter(OddsMovement.status == status)

    # 按时间排序
    movements = query.order_by(OddsMovement.update_time.asc()).all()

    return OddsListResponse(total=len(movements), movements=movements)


@router.get("/odds/latest")
async def get_latest_odds(
    odds_type: str = Query(..., description="赔率类型: AH, OU, 1x2"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """获取最新赔率变动"""
    movements = db.query(OddsMovement)\
        .filter(OddsMovement.odds_type == odds_type)\
        .order_by(OddsMovement.update_time.desc())\
        .limit(limit)\
        .all()

    return movements