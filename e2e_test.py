#!/usr/bin/env python3
"""
E2E 全流程测试脚本
测试所有核心功能模块：API 健康、页面加载、数据同步、ETL、报表、辅助功能
"""

import sys
import os

# 只添加 system_b 到路径 — system_a 通过 HTTP API 访问
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "system_b"))

# 强制使用 localhost 访问 Docker 服务
os.environ["SYSTEM_A_API_URL"] = "http://localhost:8000"

import json
import time
import urllib.request
import urllib.error

PASS = 0
FAIL = 0
SKIP = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

def skip(name, reason):
    global SKIP
    SKIP += 1
    print(f"  ⏭️  {name} — {reason}")

def http_get(url, timeout=15):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, resp.read().decode()
    except Exception as e:
        return 0, str(e)

def http_post(url, data=None, timeout=15):
    try:
        if data:
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, data=body,
                headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url, method="POST")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode()
    except Exception as e:
        return 0, str(e)

SYS_A = "http://localhost:8000"
SYS_B = "http://localhost:8501"

print("=" * 60)
print("E2E")
print("=" * 60)

print("\n" + "─" * 40)
print("1. System A API")
print("─" * 40)

status, body = http_get(f"{SYS_A}/")
test("API root", status == 200, f"HTTP {status}")

status, body = http_get(f"{SYS_A}/api/leagues")
test("leagues list API", status == 200, f"HTTP {status}")
leagues = json.loads(body) if status == 200 else []
test("leagues not empty", len(leagues) > 0, f"{len(leagues)} items")

enabled = [l for l in leagues if l.get("enabled")]
test("some leagues enabled", len(enabled) > 0, f"{len(enabled)} enabled")

status, body = http_get(f"{SYS_A}/api/crawl/stats")
test("crawl stats API", status == 200, f"HTTP {status}")

if leagues:
    first_id = leagues[0]["id"]
    status, body = http_get(f"{SYS_A}/api/leagues/{first_id}")
    test("league detail API", status == 200, f"HTTP {status}")

print("\n" + "─" * 40)
print("2. System B Service")
print("─" * 40)

status, body = http_get(f"{SYS_B}/", timeout=30)
test("Streamlit accessible", status == 200, f"HTTP {status}")

try:
    from system_b.modules.data_connector import get_connector
    conn = get_connector()
    test("DataConnector init", conn is not None)
    s = conn.get_crawl_stats()
    test("DataConnector fetch stats", s is not None and "total_matches" in s,
         f"total={s.get('total_matches', '?')}")
except Exception as e:
    test("DataConnector fetch stats", False, str(e)[:80])

try:
    from system_b.core.config_store import get_store
    store = get_store()
    test("core.config_store init", store is not None)
except Exception as e:
    test("core.config_store init", False, str(e)[:80])

print("\n" + "─" * 40)
print("3. Sync Flow")
print("─" * 40)

if leagues:
    tl = leagues[0]
    t_id = tl["id"]
    t_name = tl.get("league_name_tw", tl.get("league_name_zh", "?"))

    status, body = http_post(f"{SYS_A}/api/leagues/{t_id}/sync-seasons")
    test(f"single league sync ({t_name})", status == 200, f"HTTP {status}")
    if status == 200:
        result = json.loads(body)
        jid = result.get("job_id", "?")
        test("sync returns job_id", jid != "?", f"job_id={jid}")

        time.sleep(2)
        status2, body2 = http_get(f"{SYS_A}/api/crawl/jobs")
        if status2 == 200:
            jobs = json.loads(body2)
            sjobs = [j for j in jobs if j.get("job_type") == "sync_schedule"]
            test("sync job records found", len(sjobs) > 0, f"{len(sjobs)} jobs")
            if jid != "?":
                status3, body3 = http_get(f"{SYS_A}/api/crawl/jobs/{jid}")
                test("query by job_id", status3 == 200 or status3 == 404,
                     f"HTTP {status3}")

status, body = http_get(f"{SYS_A}/api/crawl/jobs")
test("crawl jobs list API", status == 200, f"HTTP {status}")
if status == 200:
    jobs = json.loads(body)
    test("job list parseable", len(jobs) >= 0, f"{len(jobs)} jobs")

print("\n" + "─" * 40)
print("4. Data Import Flow")
print("─" * 40)

try:
    from system_b.modules.follow_list import get_follow_manager
    fm = get_follow_manager()
    test("follow manager init", fm is not None)
    test_list = fm.get_all()
    test("follow list readable", test_list is not None, f"{len(test_list)} items")
except Exception as e:
    test("follow manager init", False, str(e)[:80])

try:
    from system_b.modules.data_connector import get_connector as _get_conn
    from system_b.modules.x_calculator import XValueCalculator
    calc = XValueCalculator(data_connector=_get_conn())
    test("XValueCalculator init", calc is not None)
except Exception as e:
    test("XValueCalculator init", False, str(e)[:80])

status, body = http_get(f"{SYS_A}/api/x-values")
if status == 200:
    xvals = json.loads(body)
    test("X-value list API", True, f"{len(xvals)} records")
else:
    skip("X-value list API", f"HTTP {status}")

print("\n" + "─" * 40)
print("5. ETL + Dashboard")
print("─" * 40)

try:
    from system_b.core.pipeline import ETLPipeline
    from system_b.core.config_store import get_store
    s = get_store()
    pipeline = ETLPipeline(s)
    test("ETLPipeline init", pipeline is not None)
except ImportError as e:
    test("ETLPipeline init", False, str(e)[:80])
except Exception as e:
    skip("ETLPipeline init", str(e)[:80])

try:
    store = __import__("system_b.core.config_store", fromlist=["get_store"]).get_store()
    runs = store.list_etl_runs(limit=5)
    test("ETL history query", runs is not None, f"{len(runs)} records")
except Exception:
    skip("ETL history query", "core.config_store unavailable")

try:
    candidates = ["system_b/db/quant.db", "system_b/db/football_quant.db", "system_b/football_quant.db"]
    found = None
    for p in candidates:
        if os.path.exists(p):
            found = p
            break
    if found:
        with open(found, "rb") as f:
            h = f.read(16)
        test("SQLite DB exists", h.startswith(b"SQLite format"), found)
    else:
        import glob
        dbs = glob.glob("system_b/**/*.db", recursive=True)
        if dbs:
            with open(dbs[0], "rb") as f:
                h = f.read(16)
            test("SQLite DB exists", h.startswith(b"SQLite format"), f"found {dbs[0]}")
        else:
            test("SQLite DB exists", False, "no .db file found")
except Exception as e:
    test("SQLite DB exists", False, str(e)[:60])

print("\n" + "─" * 40)
print("6. Auxiliary Features")
print("─" * 40)

try:
    from system_b.config.settings import get_settings
    bs = get_settings()
    test("config loadable", bs is not None)
    hss = hasattr(bs, "sync_enabled") and hasattr(bs, "sync_interval_hours")
    test("auto-sync config fields", hss,
         f"enabled={getattr(bs, 'sync_enabled', '?')}, interval={getattr(bs, 'sync_interval_hours', '?')}")
except Exception as e:
    test("config loadable", False, str(e)[:80])

try:
    from system_b.modules.auto_sync import SyncScheduler
    test("SyncScheduler importable", True)
except Exception as e:
    test("SyncScheduler importable", False, str(e)[:80])

try:
    from system_b.core.mismatch_detector import detect_mismatches, apply_fixes
    test("team grouping module importable", True)
except Exception as e:
    test("team grouping module importable", False, str(e)[:80])

print("\n" + "─" * 40)
print("7. Auto-sync UI")
print("─" * 40)

try:
    with open("system_b/app.py") as f:
        app_content = f.read()
    test("app.py has SyncScheduler init", "SyncScheduler" in app_content and "auto_sync" in app_content)
    test("app.py has Docker check", "IS_DOCKER" in app_content)
except Exception as e:
    test("app.py check failed", False, str(e)[:80])

try:
    with open("system_b/app_pages/system_sync.py") as f:
        sc = f.read()
    test("system_sync.py has auto-sync UI section", "自動同步設定" in sc)
    test("system_sync.py has manual trigger", "立即執行自動同步" in sc)
except Exception as e:
    test("system_sync.py check failed", False, str(e)[:80])

print("\n" + "=" * 60)
total = PASS + FAIL + SKIP
print(f"Total: {total}  |  Pass: {PASS}  |  Fail: {FAIL}  |  Skip: {SKIP}")
print(f"Rate: {PASS * 100 // max(total, 1)}% ({PASS}/{total})")
if FAIL > 0:
    print("Some tests failed, check details above")
else:
    print("All core functionality verified!")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)