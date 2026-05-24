"""比赛路由"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from config.database import get_db
from config.models import Match

router = APIRouter()


# ============ Pydantic 模型 ============

class MatchResponse(BaseModel):
    """比赛响应"""
    match_id: int
    league_id: Optional[int] = None
    league_name: Optional[str] = None
    group_name: Optional[str] = None
    round_name: Optional[str] = None
    season: Optional[str] = None
    match_time: Optional[datetime] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    score_ft: Optional[str] = None
    score_ht: Optional[str] = None
    settlement: Optional[str] = None
    settlement_value: Optional[float] = None
    settlement_direction: Optional[str] = None
    home_away_direction: Optional[str] = None
    target_team: Optional[str] = None
    crawl_status: str = "pending"
    retry_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class MatchListResponse(BaseModel):
    """比赛列表响应"""
    total: int
    matches: List[MatchResponse]


# ============ 路由 ============

@router.get("/matches", response_model=MatchListResponse)
async def get_matches(
    league_id: Optional[int] = Query(None, description="联赛ID"),
    season: Optional[str] = Query(None, description="赛季"),
    crawl_status: Optional[str] = Query(None, description="爬取状态"),
    home_team: Optional[str] = Query(None, description="主队名称（模糊匹配）"),
    away_team: Optional[str] = Query(None, description="客队名称（模糊匹配）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=10000, description="每页数量"),
    db: Session = Depends(get_db),
):
    """获取比赛列表（支持分页和筛选）"""
    query = db.query(Match)

    # 筛选条件
    if league_id is not None:
        query = query.filter(Match.league_id == league_id)
    if season:
        query = query.filter(Match.season == season)
    if crawl_status:
        query = query.filter(Match.crawl_status == crawl_status)
    if home_team:
        query = query.filter(Match.home_team.ilike(f"%{home_team}%"))
    if away_team:
        query = query.filter(Match.away_team.ilike(f"%{away_team}%"))

    # 总数
    total = query.count()

    # 分页
    offset = (page - 1) * page_size
    matches = query.order_by(Match.match_time.desc())\
        .offset(offset)\
        .limit(page_size)\
        .all()

    return MatchListResponse(total=total, matches=matches)


@router.get("/matches/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: int,
    db: Session = Depends(get_db),
):
    """获取单个比赛详情"""
    match = db.query(Match).filter(Match.match_id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    return match


@router.post("/matches/batch")
async def create_matches(
    matches: List[dict],
    db: Session = Depends(get_db),
):
    """批量创建/更新比赛"""
    created_count = 0

    for match_data in matches:
        match_id = match_data.get("match_id")
        if not match_id:
            continue

        # 查找是否已存在
        existing = db.query(Match).filter(Match.match_id == match_id).first()

        if existing:
            # 更新
            for key, value in match_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            # 创建
            db_match = Match(**match_data)
            db.add(db_match)
            created_count += 1

    db.commit()
    return {"message": f"已处理 {len(matches)} 条记录", "created": created_count}


# ============ 结算相关 ============

class MatchSettlementUpdate(BaseModel):
    """更新比赛结算请求"""
    score_ft: Optional[str] = None  # 全场比分，如 "2-1"
    score_ht: Optional[str] = None  # 半场比分
    settlement: Optional[str] = None  # 结算结果: 主赢, 客赢半, 等
    settlement_value: Optional[float] = None  # 1.0 或 0.5
    settlement_direction: Optional[str] = None  # win 或 lose
    home_away_direction: Optional[str] = None  # home 或 away
    target_team: Optional[str] = None  # 结算目标队伍


@router.patch("/matches/{match_id}/settlement", response_model=MatchResponse)
async def update_match_settlement(
    match_id: int,
    settlement: MatchSettlementUpdate,
    db: Session = Depends(get_db),
):
    """更新比赛结算结果"""
    match = db.query(Match).filter(Match.match_id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")

    # 更新字段
    if settlement.score_ft is not None:
        match.score_ft = settlement.score_ft
    if settlement.score_ht is not None:
        match.score_ht = settlement.score_ht
    if settlement.settlement is not None:
        match.settlement = settlement.settlement
    if settlement.settlement_value is not None:
        match.settlement_value = settlement.settlement_value
    if settlement.settlement_direction is not None:
        match.settlement_direction = settlement.settlement_direction
    if settlement.home_away_direction is not None:
        match.home_away_direction = settlement.home_away_direction
    if settlement.target_team is not None:
        match.target_team = settlement.target_team

    db.commit()
    db.refresh(match)

    return match