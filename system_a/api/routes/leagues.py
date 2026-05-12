"""联赛路由"""

from typing import List, Optional
import threading
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date, datetime
import logging

from config.database import get_db
from config.models import LeagueIndex, Season

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

# 全局爬虫并发限流 — 最多 6 个同步任务同时爬 titan007（实测 3 太保守）
_sync_semaphore = threading.Semaphore(6)

# infoHeaderFn.js 缓存 — 一次性加载所有联赛的赛季列表，避免逐个探测
_all_seasons_cache: dict[int, list[str]] | None = None
_all_seasons_cache_lock = threading.Lock()


# ============ Pydantic 模型 ============

class LeagueBase(BaseModel):
    """联赛基础信息"""
    country: str
    league_id: int
    league_name_zh: str
    league_name_tw: str
    display_order: int = 0
    enabled: bool = True


class LeagueCreate(LeagueBase):
    """创建联赛请求"""
    pass


class LeagueResponse(LeagueBase):
    """联赛响应"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SeasonBase(BaseModel):
    """赛季基础信息"""
    league_id: int
    season_label: str
    season_start: Optional[date] = None
    season_end: Optional[date] = None
    status: str = "active"


class SeasonResponse(SeasonBase):
    """赛季响应"""
    id: int

    class Config:
        from_attributes = True


# ============ 路由 ============

@router.get("/leagues", response_model=List[LeagueResponse])
async def get_leagues(
    country: Optional[str] = Query(None, description="国家筛选"),
    enabled: Optional[bool] = Query(None, description="是否启用"),
    limit: int = Query(10000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """获取联赛列表"""
    query = db.query(LeagueIndex)

    if country:
        query = query.filter(LeagueIndex.country == country)
    if enabled is not None:
        query = query.filter(LeagueIndex.enabled == enabled)

    total = query.count()
    leagues = query.order_by(LeagueIndex.display_order)\
        .offset(offset)\
        .limit(limit)\
        .all()

    return leagues


@router.get("/leagues/{league_id}", response_model=LeagueResponse)
async def get_league(
    league_id: int,
    db: Session = Depends(get_db),
):
    """获取单个联赛详情"""
    league = db.query(LeagueIndex).filter(LeagueIndex.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="联赛不存在")

    return league


@router.post("/leagues", response_model=LeagueResponse)
async def create_league(
    league: LeagueCreate,
    db: Session = Depends(get_db),
):
    """创建联赛"""
    db_league = LeagueIndex(**league.model_dump())
    db.add(db_league)
    db.commit()
    db.refresh(db_league)
    return db_league


@router.put("/leagues/{league_id}", response_model=LeagueResponse)
async def update_league(
    league_id: int,
    league: LeagueCreate,
    db: Session = Depends(get_db),
):
    """更新联赛"""
    db_league = db.query(LeagueIndex).filter(LeagueIndex.id == league_id).first()
    if not db_league:
        raise HTTPException(status_code=404, detail="联赛不存在")

    for key, value in league.model_dump().items():
        setattr(db_league, key, value)

    db.commit()
    db.refresh(db_league)
    return db_league


@router.delete("/leagues/{league_id}")
async def delete_league(
    league_id: int,
    db: Session = Depends(get_db),
):
    """删除联赛"""
    db_league = db.query(LeagueIndex).filter(LeagueIndex.id == league_id).first()
    if not db_league:
        raise HTTPException(status_code=404, detail="联赛不存在")

    db.delete(db_league)
    db.commit()
    return {"message": "联赛已删除"}


@router.post("/leagues/sync-from-site")
async def sync_leagues_from_site(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """从网站抓取联赛列表并保存到数据库"""
    import uuid
    from scraper.league_crawler import LeagueCrawler
    from config.models import CrawlJob

    # 创建任务记录
    job_uuid = str(uuid.uuid4())[:8]
    job = CrawlJob(
        job_id=job_uuid,
        job_type="sync_leagues",
        status="pending",
        total_matches=0,
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    def do_sync(job_id: int):
        from config.database import SessionLocal
        db = SessionLocal()

        try:
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if job:
                job.status = "running"
                job.started_at = datetime.utcnow()
                db.commit()

            crawler = LeagueCrawler()
            leagues_from_site = crawler.get_league_list()

            added_count = 0
            updated_count = 0

            for league_data in leagues_from_site:
                league_id = league_data.get("league_id")
                if not league_id:
                    continue

                # 检查是否已存在
                existing = db.query(LeagueIndex).filter(
                    LeagueIndex.league_id == league_id
                ).first()

                if existing:
                    # 更新现有记录
                    existing.league_name_tw = league_data.get("name", "")
                    existing.league_name_zh = league_data.get("name", "")
                    existing.country = league_data.get("country", "")
                    updated_count += 1
                else:
                    # 创建新记录
                    new_league = LeagueIndex(
                        league_id=league_id,
                        league_name_tw=league_data.get("name", ""),
                        league_name_zh=league_data.get("name", ""),
                        country=league_data.get("country", ""),
                        display_order=0,
                        enabled=True
                    )
                    db.add(new_league)
                    added_count += 1

            db.commit()
            logger.info(f"联赛同步完成: 新增 {added_count}, 更新 {updated_count}")

            # 更新任务状态
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.total_matches = added_count + updated_count
                job.completed_matches = added_count + updated_count
                db.commit()

        except Exception as e:
            logger.error(f"联赛同步失败: {e}")
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.error_message = str(e)
                db.commit()
        finally:
            db.close()

    background_tasks.add_task(do_sync, job.id)
    return {"message": "联赛同步任务已启动", "status": "started", "job_id": job.job_id}


@router.post("/leagues/{league_id}/sync-seasons")
async def sync_seasons_for_league(
    league_id: int,
    background_tasks: BackgroundTasks,
    season_label: Optional[str] = Query(None, description="指定赛季标签，为空则同步所有可用赛季"),
    db: Session = Depends(get_db),
):
    """同步指定联赛的赛季赛程

    如果指定 season_label 则只同步该赛季，否则同步所有可用赛季。
    """
    import uuid
    from scraper.league_crawler import LeagueCrawler
    from config.models import Match, Season, CrawlJob

    league = db.query(LeagueIndex).filter(LeagueIndex.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="联赛不存在")

    # 创建任务记录
    job_uuid = str(uuid.uuid4())[:8]
    job = CrawlJob(
        job_id=job_uuid,
        job_type="sync_schedule",
        league_id=league_id,
        status="pending",
        total_matches=0,
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 指定赛季标签，为空则同步所有
    target_season = season_label

    def do_sync_schedule(job_id: int):
        import random as _random
        import time as _time

        # 全局限流：最多 6 个任务同时爬 titan007，超时 10 分钟
        if not _sync_semaphore.acquire(timeout=600):
            logger.warning(f"同步任务 {job_id} 等待信号量超时，跳过")
            return

        try:
            _time.sleep(_random.uniform(0, 3))
            from config.database import SessionLocal
            db = SessionLocal()

            try:
                job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
                if job:
                    job.status = "running"
                    job.started_at = datetime.utcnow()
                    db.commit()

                crawler = LeagueCrawler()

                # 从 infoHeaderFn.js 批量获取赛季列表（一次 HTTP 请求，缓存复用）
                global _all_seasons_cache
                if _all_seasons_cache is None:
                    with _all_seasons_cache_lock:
                        if _all_seasons_cache is None:  # double-check
                            _all_seasons_cache = crawler.fetch_all_seasons()

                season_labels = (_all_seasons_cache or {}).get(league.league_id)
                if not season_labels:
                    logger.info(f"联赛 {league_id} 在 infoHeaderFn.js 中无赛季数据，回退到逐探测")
                    season_labels = crawler.get_available_seasons(league.league_id)

                # 如果指定了目标赛季，只同步该赛季
                if target_season and target_season in season_labels:
                    season_labels = [target_season]
                elif target_season:
                    logger.info(f"目标赛季 {target_season} 不在可用列表 {season_labels[:5]}... 中，回退到全部同步")

                total_matches = 0
                completed_matches = 0
                failed_matches = 0

                for season in season_labels:
                    try:
                        matches = crawler.get_season_schedules(
                            league_id=league.league_id, season=season
                        )

                        existing_season = db.query(Season).filter(
                            Season.league_id == league_id,
                            Season.season_label == season
                        ).first()
                        if not existing_season:
                            db.add(Season(
                                league_id=league_id, season_label=season, status="active"
                            ))
                            db.commit()

                        for md in matches:
                            mid = md.get("match_id")
                            if not mid:
                                continue
                            exist = db.query(Match).filter(Match.match_id == mid).first()
                            if not exist:
                                db.add(Match(
                                    match_id=mid, league_id=league_id,
                                    league_name=md.get("league_name", ""),
                                    season=md.get("season", season),
                                    round_name=md.get("round_name", ""),
                                    match_time=md.get("match_time_str", ""),
                                    home_team=md.get("home_team", ""),
                                    away_team=md.get("away_team", ""),
                                    score_ft=md.get("score_ft", ""),
                                    crawl_status="pending"
                                ))
                            else:
                                is_done = exist.score_ft and exist.score_ft.strip()
                                if is_done:
                                    new_s = md.get("score_ft", "")
                                    if new_s != exist.score_ft:
                                        exist.score_ft = new_s
                                else:
                                    exist.round_name = md.get("round_name", "")
                                    exist.home_team = md.get("home_team", "")
                                    exist.away_team = md.get("away_team", "")
                                    exist.score_ft = md.get("score_ft", "")

                        db.commit()
                        total_matches += len(matches)
                        completed_matches += len(matches)
                    except Exception as e:
                        logger.error(f"赛季 {season} 同步失败: {e}")
                        failed_matches += 1

                j = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
                if j:
                    j.status = "completed"
                    j.completed_at = datetime.utcnow()
                    j.total_matches = total_matches
                    j.completed_matches = completed_matches
                    j.failed_matches = failed_matches
                    db.commit()

            except Exception as e:
                logger.error(f"联赛 {league_id} 同步失败: {e}")
                j = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
                if j:
                    j.status = "failed"
                    j.completed_at = datetime.utcnow()
                    j.error_message = str(e)
                    db.commit()
            finally:
                db.close()
        finally:
            _sync_semaphore.release()

    background_tasks.add_task(do_sync_schedule, job.id)
    return {"message": f"联赛 {league_id} 赛季同步任务已启动", "status": "started", "job_id": job.job_id}


@router.post("/leagues/batch-sync-seasons")
async def batch_sync_seasons(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """批量同步所有联赛的赛季赛程（一个后台任务处理全部）"""
    import uuid
    from scraper.league_crawler import LeagueCrawler
    from config.models import Match, Season, CrawlJob

    job_uuid = str(uuid.uuid4())[:8]
    job = CrawlJob(
        job_id=job_uuid,
        job_type="batch_sync_schedule",
        status="pending",
        total_matches=0,
        completed_matches=0,
        failed_matches=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    def do_batch_sync(job_id: int):
        import logging as _logging
        _log = _logging.getLogger(__name__)

        from config.database import SessionLocal as _SessionLocal
        db = _SessionLocal()

        try:
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if job:
                job.status = "running"
                job.started_at = datetime.utcnow()
                db.commit()

            # 一次 HTTP 请求获取所有联赛的赛季标签
            crawler = LeagueCrawler()
            all_seasons = crawler.fetch_all_seasons()
            if not all_seasons:
                _log.error("batch_sync: fetch_all_seasons 失败")
                return

            leagues = db.query(LeagueIndex).filter(LeagueIndex.enabled == True).all()
            created = 0
            skipped = 0

            for league in leagues:
                labels = all_seasons.get(league.league_id, [])
                if not labels:
                    continue
                for label in labels:
                    exist = db.query(Season).filter(
                        Season.league_id == league.id,
                        Season.season_label == label
                    ).first()
                    if not exist:
                        db.add(Season(
                            league_id=league.id,
                            season_label=label,
                            status="active"
                        ))
                        created += 1
                    else:
                        skipped += 1

            db.commit()

            j = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if j:
                j.status = "completed"
                j.completed_at = datetime.utcnow()
                j.total_matches = created
                j.completed_matches = skipped
                db.commit()

            _log.info(f"batch_sync: 完成！创建 {created} 个赛季记录, 跳过 {skipped} 个已有记录")

        except Exception as e:
            _log.error(f"batch_sync: 失败: {e}")
            j = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if j:
                j.status = "failed"
                j.completed_at = datetime.utcnow()
                j.error_message = str(e)
                db.commit()
        finally:
            db.close()

    background_tasks.add_task(do_batch_sync, job.id)
    return {"message": "全联赛批量同步任务已启动", "status": "started", "job_id": job.job_id}


# ============ 赛季路由 ============

@router.get("/seasons/{league_id}", response_model=List[SeasonResponse])
async def get_seasons(
    league_id: int,
    status: Optional[str] = Query(None, description="状态筛选"),
    db: Session = Depends(get_db),
):
    """获取联赛的赛季列表"""
    query = db.query(Season).filter(Season.league_id == league_id)

    if status:
        query = query.filter(Season.status == status)

    seasons = query.order_by(Season.season_label.desc()).all()
    return seasons


@router.post("/seasons", response_model=SeasonResponse)
async def create_season(
    season: SeasonBase,
    db: Session = Depends(get_db),
):
    """创建赛季"""
    db_season = Season(**season.model_dump())
    db.add(db_season)
    db.commit()
    db.refresh(db_season)
    return db_season


@router.post("/leagues/clear-all")
async def clear_all_sync_data(
    db: Session = Depends(get_db),
):
    """清除所有同步的数据"""
    from config.models import Match, OddsMovement, XValueResult, CrawlJob

    try:
        # 清除所有数据
        db.query(OddsMovement).delete()
        db.query(XValueResult).delete()
        db.query(Match).delete()
        db.query(Season).delete()
        db.query(LeagueIndex).delete()
        db.query(CrawlJob).delete()

        db.commit()
        return {"message": "所有同步数据已清除"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清除失败: {e}")


@router.get("/season-stats")
async def get_season_stats(
    db: Session = Depends(get_db),
):
    """获取赛季维度统计"""
    from config.models import Match, Season
    from sqlalchemy import text
    total_seasons = db.query(Season).count()
    synced_seasons = db.execute(text(
        "SELECT COUNT(*) FROM seasons s WHERE EXISTS "
        "(SELECT 1 FROM matches m WHERE m.league_id = s.league_id AND m.season = s.season_label)"
    )).scalar()
    return {
        "total_seasons": total_seasons,
        "synced_seasons": synced_seasons,
    }