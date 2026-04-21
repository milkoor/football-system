"""管理后台路由"""

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.database import get_db
from config.models import LeagueIndex, Season, CrawlJob, Match

router = APIRouter()

# 初始化模板引擎
templates = Jinja2Templates(directory="admin/templates")


# ============ 页面路由 ============

@router.get("/admin/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """仪表盘"""
    # 统计
    total_matches = db.query(Match).count()
    pending = db.query(Match).filter(Match.crawl_status == "pending").count()
    completed = db.query(Match).filter(Match.crawl_status == "completed").count()
    error = db.query(Match).filter(Match.crawl_status == "error").count()
    active_jobs = db.query(CrawlJob).filter(
        CrawlJob.status.in_(["pending", "running"])
    ).count()
    leagues_count = db.query(LeagueIndex).count()
    seasons_count = db.query(Season).count()

    stats = {
        "total_matches": total_matches,
        "pending": pending,
        "completed": completed,
        "error": error,
        "active_jobs": active_jobs,
        "leagues_count": leagues_count,
        "seasons_count": seasons_count,
    }

    # 最近任务
    recent_jobs = db.query(CrawlJob).order_by(
        CrawlJob.created_at.desc()
    ).limit(10).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats, "recent_jobs": recent_jobs, "active_page": "dashboard"}
    )


@router.get("/admin/leagues", response_class=HTMLResponse)
async def leagues_page(
    request: Request,
    country: str = Query(None),
    enabled: str = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db)
):
    """联赛管理页面"""
    # 查询
    query = db.query(LeagueIndex)

    if country:
        query = query.filter(LeagueIndex.country == country)
    if enabled is not None:
        query = query.filter(LeagueIndex.enabled == (enabled == "true"))

    total = query.count()
    page_size = 20
    total_pages = (total + page_size - 1) // page_size

    leagues_list = query.order_by(LeagueIndex.display_order)\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    # 获取每个联赛的赛季数
    leagues_data = []
    for league in leagues_list:
        seasons_count = db.query(Season).filter(Season.league_id == league.id).count()
        leagues_data.append({
            "id": league.id,
            "country": league.country,
            "league_id": league.league_id,
            "league_name_tw": league.league_name_tw,
            "display_order": league.display_order,
            "enabled": league.enabled,
            "created_at": league.created_at.strftime("%Y-%m-%d %H:%M") if league.created_at else "-",
            "seasons_count": seasons_count,
        })

    return templates.TemplateResponse(
        "leagues.html",
        {
            "request": request,
            "leagues": leagues_data,
            "filters": {"country": country, "enabled": enabled},
            "page": page,
            "total_pages": total_pages,
            "active_page": "leagues"
        }
    )


@router.get("/admin/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db)
):
    """任务管理页面"""
    # 统计
    job_stats = {
        "pending": db.query(CrawlJob).filter(CrawlJob.status == "pending").count(),
        "running": db.query(CrawlJob).filter(CrawlJob.status == "running").count(),
        "completed": db.query(CrawlJob).filter(CrawlJob.status == "completed").count(),
        "failed": db.query(CrawlJob).filter(CrawlJob.status == "failed").count(),
    }

    # 任务列表
    query = db.query(CrawlJob)
    if status:
        query = query.filter(CrawlJob.status == status)

    total = query.count()
    page_size = 20
    total_pages = (total + page_size - 1) // page_size

    jobs_list = query.order_by(CrawlJob.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()

    # 联赛列表（用于新建任务）
    leagues = db.query(LeagueIndex).filter(LeagueIndex.enabled == True).all()

    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "jobs": jobs_list,
            "job_stats": job_stats,
            "leagues": leagues,
            "filters": {"status": status},
            "page": page,
            "total_pages": total_pages,
            "active_page": "tasks"
        }
    )


@router.get("/admin/quality", response_class=HTMLResponse)
async def quality_page(request: Request, db: Session = Depends(get_db)):
    """数据质量页面"""
    # 概览统计
    total = db.query(Match).count()
    with_odds = db.query(Match).filter(Match.crawl_status == "completed").count()
    completeness_rate = round(with_odds / total * 100, 1) if total > 0 else 0

    # 缺失数据
    pending = db.query(Match).filter(
        Match.crawl_status == "pending"
    ).order_by(Match.match_time.desc()).limit(20).all()

    # 错误数据
    errors = db.query(Match).filter(
        Match.crawl_status == "error"
    ).order_by(Match.last_synced.desc()).limit(20).all()

    return templates.TemplateResponse(
        "quality.html",
        {
            "request": request,
            "stats": {
                "total_matches": total,
                "with_odds": with_odds,
                "completeness_rate": completeness_rate,
                "anomalies": len(errors),
            },
            "pending_matches": pending,
            "error_matches": errors,
            "league_stats": [],
            "active_page": "quality"
        }
    )


@router.get("/admin/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """系统配置页面"""
    # TODO: 从配置文件读取
    config = {
        "crawl_concurrency": 3,
        "request_delay_min": 1.0,
        "request_delay_max": 3.0,
        "batch_size": 10,
        "proxy_enabled": False,
        "proxy_type": "socks5",
        "proxy_host": "",
        "proxy_port": 3010,
        "proxy_username": "",
        "proxy_password": "",
        "titan_base_url": "https://vip.titan007.com",
        "titan_schedule_url": "https://zq.titan007.com",
        "log_level": "INFO",
    }

    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "config": config, "active_page": "settings"}
    )