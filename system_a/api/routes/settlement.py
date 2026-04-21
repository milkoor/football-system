"""结算相关路由"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from config.database import get_db, SessionLocal
from config.models import Match

logger = logging.getLogger(__name__)
router = APIRouter()


class MatchSettlementResponse(BaseModel):
    """比赛结算响应"""
    match_id: int
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    score: Optional[str] = None
    handicap: Optional[str] = None
    settlement: Optional[str] = None
    settlement_value: Optional[float] = None
    settlement_direction: Optional[str] = None
    home_away_direction: Optional[str] = None
    target_team: Optional[str] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class BatchSettlementResponse(BaseModel):
    """批量结算响应"""
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


def calculate_settlement(match_id: int, db: Session) -> Dict[str, Any]:
    """计算单场比赛的结算结果（内部函数）"""
    from modules.settlement_calculator import AutoSettlementCalculator

    calc = AutoSettlementCalculator()
    return calc.auto_settle_match(match_id)


@router.post("/matches/{match_id}/auto-settle", response_model=MatchSettlementResponse)
async def auto_settle_match(
    match_id: int,
    db: Session = Depends(get_db),
):
    """自动结算单场比赛

    根据比赛比分和盘口自动计算结算结果
    """
    result = calculate_settlement(match_id, db)

    if "error" in result and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/matches/auto-settle", response_model=BatchSettlementResponse)
async def batch_auto_settle(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    season: Optional[str] = Query(None, description="赛季"),
    db: Session = Depends(get_db),
):
    """批量自动结算

    对指定联赛/赛季下所有有比分但未结算的比赛进行自动结算
    """
    from modules.settlement_calculator import AutoSettlementCalculator

    calc = AutoSettlementCalculator()
    result = calc.batch_auto_settle(league_id=league_id, season=season)

    return result


@router.get("/matches/{match_id}/settlement", response_model=MatchSettlementResponse)
async def get_match_settlement(
    match_id: int,
    db: Session = Depends(get_db),
):
    """获取比赛结算结果"""
    match = db.query(Match).filter(Match.match_id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    return MatchSettlementResponse(
        match_id=match.match_id,
        home_team=match.home_team,
        away_team=match.away_team,
        score=match.score_ft,
        settlement=match.settlement,
        settlement_value=match.settlement_value,
        settlement_direction=match.settlement_direction,
        home_away_direction=match.home_away_direction,
        target_team=match.target_team,
    )


@router.post("/matches/{match_id}/score")
async def update_match_score(
    match_id: int,
    score_ft: str = ...,  # 必填，如 "2-1"
    score_ht: Optional[str] = None,  # 可选，如 "1-0"
    db: Session = Depends(get_db),
):
    """更新比赛比分并自动结算

    更新比分后会自动计算结算结果
    """
    match = db.query(Match).filter(Match.match_id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    # 更新比分
    match.score_ft = score_ft
    if score_ht:
        match.score_ht = score_ht

    db.commit()

    # 自动结算
    result = calculate_settlement(match_id, db)

    return {
        "message": "比分已更新并自动结算",
        "match_id": match_id,
        "score": score_ft,
        "settlement": result.get("settlement", "结算失败"),
    }