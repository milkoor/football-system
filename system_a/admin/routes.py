"""管理后台路由"""

import os

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.database import get_db
from config.models import LeagueIndex, Season, CrawlJob, Match

router = APIRouter()

# 初始化模板引擎（与其他页面保持一致）
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
    from config.settings import get_settings
    settings = get_settings()

    # 使用简单的HTML，避免Jinja2兼容性问题
    # 所有功能正常工作：读取真实配置，保存到.env文件
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>系统配置 - 足球数据系统 A</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h2 { margin: 0; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h3 { margin-top: 0; }
        .btn { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn-success { background-color: #4CAF50; color: white; }
        .btn-success:hover { background-color: #45a049; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 500; }
        .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .alert { padding: 15px; background-color: #4CAF50; color: white; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>⚙️ 系统配置</h2>
            <button class="btn btn-success" onclick="saveSettings()">💾 保存配置</button>
        </div>
"""

    # 添加 message 部分
    if hasattr(request.state, 'message'):
        html += f'<div class="alert">{request.state.message}</div>'

    html += f"""
        <!-- 爬虫配置 -->
        <div class="card">
            <h3>🕷️ 爬虫配置</h3>
            <form id="crawlSettingsForm">
                <div class="stats-grid">
                    <div class="form-group">
                        <label>并发数</label>
                        <input type="number" name="crawl_concurrency" value="{settings.crawl_concurrency}" min="1" max="10">
                    </div>
                    <div class="form-group">
                        <label>请求延迟下限（秒）</label>
                        <input type="number" name="request_delay_min" value="{settings.request_delay_min}" min="0.1" step="0.1">
                    </div>
                    <div class="form-group">
                        <label>请求延迟上限（秒）</label>
                        <input type="number" name="request_delay_max" value="{settings.request_delay_max}" min="0.1" step="0.1">
                    </div>
                    <div class="form-group">
                        <label>批次大小</label>
                        <input type="number" name="batch_size" value="{settings.batch_size}" min="1" max="100">
                    </div>
                </div>
            </form>
        </div>

        <!-- 代理配置 -->
        <div class="card">
            <h3>🌐 代理配置</h3>
            <form id="proxySettingsForm">
                <div style="margin-bottom: 15px;">
                    <label style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" name="proxy_enabled" {'checked' if settings.proxy_enabled else ''}>
                        启用代理
                    </label>
                </div>
                <div class="stats-grid">
                    <div class="form-group">
                        <label>代理类型</label>
                        <select name="proxy_type">
                            <option value="socks5" {'selected' if settings.proxy_type == 'socks5' else ''}>SOCKS5</option>
                            <option value="http" {'selected' if settings.proxy_type == 'http' else ''}>HTTP</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>主机</label>
                        <input type="text" name="proxy_host" value="{settings.proxy_host}" placeholder="如：sg.nexip.cc">
                    </div>
                    <div class="form-group">
                        <label>端口</label>
                        <input type="number" name="proxy_port" value="{settings.proxy_port}">
                    </div>
                    <div class="form-group">
                        <label>用户名</label>
                        <input type="text" name="proxy_username" value="{settings.proxy_username}">
                    </div>
                    <div class="form-group">
                        <label>密码</label>
                        <input type="password" name="proxy_password" value="{settings.proxy_password}">
                    </div>
                </div>
            </form>
        </div>

        <!-- 目标网站配置 -->
        <div class="card">
            <h3>🎯 目标网站配置</h3>
            <form id="targetSettingsForm">
                <div class="form-group">
                    <label>Titan 基础 URL</label>
                    <input type="text" name="titan_base_url" value="{settings.titan_base_url}">
                </div>
                <div class="form-group">
                    <label>赛程 URL</label>
                    <input type="text" name="titan_schedule_url" value="{settings.titan_schedule_url}">
                </div>
            </form>
        </div>

        <!-- 日志配置 -->
        <div class="card">
            <h3>📝 日志配置</h3>
            <form id="logSettingsForm">
                <div class="form-group">
                    <label>日志级别</label>
                    <select name="log_level">
                        <option value="DEBUG" {'selected' if settings.log_level == 'DEBUG' else ''}>DEBUG</option>
                        <option value="INFO" {'selected' if settings.log_level == 'INFO' else ''}>INFO</option>
                        <option value="WARNING" {'selected' if settings.log_level == 'WARNING' else ''}>WARNING</option>
                        <option value="ERROR" {'selected' if settings.log_level == 'ERROR' else ''}>ERROR</option>
                    </select>
                </div>
            </form>
        </div>

        <script>
        async function saveSettings() {{
            const forms = ['crawlSettingsForm', 'proxySettingsForm', 'targetSettingsForm', 'logSettingsForm'];
            const formData = new FormData();

            forms.forEach(formId => {{
                const form = document.getElementById(formId);
                const fd = new FormData(form);
                fd.forEach((value, key) => {{
                    const input = form.querySelector(`[name="${{key}}"]`);
                    if (input?.type === 'checkbox') {{
                        formData.append(key, input.checked ? 'true' : 'false');
                    }} else if (value !== '') {{
                        formData.append(key, value);
                    }}
                }});
            }});

            try {{
                const response = await fetch('/admin/settings', {{
                    method: 'POST',
                    body: formData
                }});

                if (response.ok) {{
                    // 重新加载页面以显示更新后的配置
                    window.location.reload();
                }} else {{
                    alert('保存失败');
                }}
            }} catch (error) {{
                console.error('错误:', error);
                alert('保存配置时出错');
            }}
        }}
        </script>
    </div>
</body>
</html>
"""
    return HTMLResponse(html)


@router.post("/admin/settings", response_class=HTMLResponse)
async def save_settings(request: Request):
    """保存系统配置"""
    from config.settings import get_settings, Settings

    # 解析表单数据
    form = await request.form()

    # 更新 .env 文件
    env_path = "/mnt/d/project/football_system/system_a/.env"
    if not os.path.exists(env_path):
        open(env_path, "w").close()

    # 读取现有配置行（保留注释和空行）
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 要更新的字段映射
    field_map = {
        "crawl_concurrency": "CRAWL_CONCURRENCY",
        "request_delay_min": "REQUEST_DELAY_MIN",
        "request_delay_max": "REQUEST_DELAY_MAX",
        "batch_size": "BATCH_SIZE",
        "proxy_enabled": "PROXY_ENABLED",
        "proxy_type": "PROXY_TYPE",
        "proxy_host": "PROXY_HOST",
        "proxy_port": "PROXY_PORT",
        "proxy_username": "PROXY_USERNAME",
        "proxy_password": "PROXY_PASSWORD",
        "titan_base_url": "TITAN_BASE_URL",
        "titan_schedule_url": "TITAN_SCHEDULE_URL",
        "log_level": "LOG_LEVEL"
    }

    # 收集需要更新的键值对
    updates = {}
    for field, env_key in field_map.items():
        if field in form:
            value = form[field]
            # 处理布尔值
            if field == "proxy_enabled":
                updates[env_key] = "true" if value.lower() in ["true", "on", "yes", "1"] else "false"
            else:
                updates[env_key] = value

    # 更新现有行
    new_lines = []
    updated_keys = set()

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                # 更新这个键
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                # 保持原样
                new_lines.append(line)
        else:
            # 保持注释和空行
            new_lines.append(line)

    # 添加未在现有文件中的新键
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    # 写回 .env 文件
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # 清除设置缓存并重新读取
    from config.settings import get_settings as _get_settings
    _get_settings.cache_clear()
    settings = _get_settings()

    # 直接返回简单的成功响应，使用与 GET 方法相同的 HTML
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>配置已保存 - 足球数据系统 A</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .success { color: #4CAF50; font-size: 24px; margin-bottom: 20px; }
        .btn { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn-primary { background-color: #008CBA; color: white; }
        .btn-primary:hover { background-color: #007BA7; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="success">✓ 配置已保存</div>
            <h3>您的配置已成功更新！</h3>
            <p>系统将使用新的配置参数。</p>
            <hr>
            <p><a href="/admin/settings" class="btn btn-primary">返回设置页面</a></p>
        </div>
    </div>
</body>
</html>
    """
    return HTMLResponse(html)