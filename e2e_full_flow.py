#!/usr/bin/env python3
"""
E2E 全流程冒烟测试
覆盖: 同步→导入→ETL→报表 完整链路
"""

import sys, os, json, time, urllib.request, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "system_b"))
os.environ["SYSTEM_A_API_URL"] = "http://localhost:8000"

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

def find_main_league(leagues, name):
    """找到主联赛（排除盃赛等衍生赛事）"""
    for l in leagues:
        n = l.get('league_name_tw', '') or l.get('league_name_zh', '')
        if name in n and '盃' not in n and '杯' not in n and '預' not in n:
            return l
    return None

def http_get(url, timeout=15):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, resp.read().decode()
    except Exception as e:
        return 0, str(e)

def http_post(url, data=None, timeout=15):
    try:
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode()
    except Exception as e:
        return 0, str(e)

SYS_A = "http://localhost:8000"
SYS_B_DB = os.path.join(os.path.dirname(__file__), "system_b", "db", "quant.db")

print("=" * 60)
print("E2E Full Flow Test")
print("=" * 60)

# ===== 1. System A API =====
print("\n" + "─" * 40)
print("1. System A API")
print("─" * 40)

status, body = http_get(f"{SYS_A}/api/leagues?enabled=true")
test("联赛API", status == 200)
leagues = json.loads(body) if status == 200 else []
test("联赛列表非空", len(leagues) > 0, f"{len(leagues)} 个")

status, body = http_get(f"{SYS_A}/api/crawl/stats")
test("统计API", status == 200)

status, body = http_get(f"{SYS_A}/api/season-stats")
test("赛季统计API", status == 200, f"{body[:80]}")

# ===== 2. 批量同步赛季标签 =====
print("\n" + "─" * 40)
print("2. Batch Sync Seasons")
print("─" * 40)

status, body = http_post(f"{SYS_A}/api/leagues/batch-sync-seasons")
test("批量同步触发", status == 200)
jid = json.loads(body).get("job_id", "") if status == 200 else ""
test("返回job_id", bool(jid), jid)

if jid:
    for _ in range(30):
        time.sleep(2)
        status, body = http_get(f"{SYS_A}/api/crawl/jobs/{jid}")
        job = json.loads(body) if status == 200 else {}
        if job.get("status") in ("completed", "failed"):
            break
    test("批量同步完成", job.get("status") == "completed",
         f"created={job.get('total_matches',0)} skipped={job.get('completed_matches',0)}")

    if job.get("status") == "completed":
        test("赛季记录已存在", job.get("completed_matches", 0) > 10000,
             f"已有{job.get('completed_matches',0)}个赛季(新创建{job.get('total_matches',0)})")

# ===== 3. 赛季统计验证 =====
print("\n" + "─" * 40)
print("3. Season Stats")
print("─" * 40)

status, body = http_get(f"{SYS_A}/api/season-stats")
stats = json.loads(body) if status == 200 else {}
test("赛季总数>10000", stats.get("total_seasons", 0) > 10000,
     f"{stats.get('total_seasons')}")

# ===== 4. 关注管理 =====
print("\n" + "─" * 40)
print("4. Follow Management")
print("─" * 40)

from modules.follow_list import get_follow_manager
fm = get_follow_manager()
test("关注管理器", fm is not None)

# 添加中超到关注
if leagues:
    cs = find_main_league(leagues, '中超')
    if cs:
        fm.add(league_id=cs['id'], league_name=f"{cs.get('country','')} - {cs.get('league_name_tw','')}",
               season_label="2026", country=cs.get('country',''))
        fl = fm.get_all()
        test("关注列表有中超", any(i['league_id'] == cs['id'] for i in fl))

# ===== 5. 同步赛程(关注赛季) =====
print("\n" + "─" * 40)
print("5. Sync Schedule")
print("─" * 40)

if leagues:
    test_league = find_main_league(leagues, '中超') or leagues[0]
    lid = test_league['id']
    status, body = http_post(f"{SYS_A}/api/leagues/{lid}/sync-seasons?season_label=2026")
    test("单联赛同步触发", status == 200)
    jid2 = json.loads(body).get("job_id", "") if status == 200 else ""

    if jid2:
        for _ in range(30):
            time.sleep(2)
            status, body = http_get(f"{SYS_A}/api/crawl/jobs/{jid2}")
            job = json.loads(body) if status == 200 else {}
            if job.get("status") in ("completed", "failed"):
                break
        test("赛程同步完成", job.get("status") == "completed",
             f"matches={job.get('total_matches',0)}")

# ===== 6. 爬取赔率 =====
print("\n" + "─" * 40)
print("6. Crawl Odds")
print("─" * 40)

if leagues:
    test_lid = (find_main_league(leagues, '中超') or leagues[0])['id']
    status, body = http_post(f"{SYS_A}/api/crawl/start", {"league_id": test_lid})
    test("爬取触发", status == 200)
    jid3 = json.loads(body).get("job_id", "") if status == 200 else ""
    if jid3:
        for _ in range(15):
            time.sleep(2)
            status, body = http_get(f"{SYS_A}/api/crawl/jobs/{jid3}")
            job = json.loads(body) if status == 200 else {}
            if job.get("status") in ("completed", "failed"):
                break
        test("爬取完成", job.get("status") == "completed",
             f"total={job.get('total_matches',0)}")
        # 直接用 league_id 查，不限制 season_label
        status, body = http_get(f"{SYS_A}/api/matches?league_id={test_lid}&page=1&page_size=1")
        test("联赛有比赛数据", status == 200)

# ===== 7. X值计算+导入System B =====
print("\n" + "─" * 40)
print("7. X-Value Calc + Import to System B")
print("─" * 40)

try:
    from modules.data_connector import get_connector
    from modules.x_calculator import XValueCalculator
    from core.config_store import get_store
    from utils.system_a_mapper import sync_league_to_system_b, sync_season_to_system_b
    from core.models import MatchRecord
    from core.settlement import SettlementCalculator
    from collections import defaultdict
    import re

    store = get_store()
    conn = get_connector()
    calc = XValueCalculator(conn)

    league_name_map = {lg['id']: lg.get('league_name_tw') or lg.get('league_name_zh', '')
                       for lg in conn.get_leagues(enabled=True)}

    if leagues:
        test_lid = (find_main_league(leagues, '中超') or leagues[0])['id']
        mr_resp = conn.get_matches(league_id=test_lid, page=1, page_size=50)
        mlist = mr_resp.get('matches') or mr_resp.get('data') or []
        test("联赛有比赛数据可导入", len(mlist) > 0, f"{len(mlist)} 场")

        if mlist:
            match_ids = [m['match_id'] for m in mlist]
            results = calc.batch_calculate(match_ids)

            batch_records = defaultdict(list)
            imported = 0
            for md, r in zip(mlist, results):
                try:
                    lid = md.get('league_id')
                    league_info = {
                        'id': lid, 'league_name_tw': league_name_map.get(lid, ''),
                        'country': '', 'league_id': lid
                    }
                    lid_b = sync_league_to_system_b(store, conn, league_info)
                    sid_b = sync_season_to_system_b(store, lid_b, md.get('season', '2024-2025'))
                    record = MatchRecord(
                        round_num=int(md.get('round_name', '1').replace('R_', '')),
                        home_team=md.get('home_team', ''), away_team=md.get('away_team', ''),
                        x_value=r.get('x_value', 0.0) if r.get('status') == 'success' else 0.0,
                        settlement='', score=md.get('score_ft', ''),
                        link=r.get('movement_url', ''), play_type='HDP',
                        target_team=r.get('target_team', ''),
                    )
                    SettlementCalculator().calculate([record])
                    batch_records[(sid_b, 'HDP', 'Early')].append(record)
                    imported += 1
                except Exception as e:
                    print(f"    导入单条失败: {e}")
            for (sid, pt, tm), recs in batch_records.items():
                store.upsert_match_records(sid, pt, tm, recs)

            test("导入完成", imported > 0, f"{imported} 条")
            test("X值计算", any(r.get('status') == 'success' for r in results),
                 f"成功{sum(1 for r in results if r.get('status')=='success')}/{len(results)}")

            # 验证SQLite
            if os.path.exists(SYS_B_DB):
                db = sqlite3.connect(SYS_B_DB)
                mr_cnt = db.execute('SELECT COUNT(*) FROM match_records').fetchone()[0]
                test("SQLite match_records>0", mr_cnt > 0, f"{mr_cnt} 条")
                lg_cnt = db.execute('SELECT COUNT(*) FROM leagues').fetchone()[0]
                test("SQLite leagues>0", lg_cnt > 0, f"{lg_cnt} 个")
                si_cnt = db.execute('SELECT COUNT(*) FROM season_instances').fetchone()[0]
                test("SQLite season_instances>0", si_cnt > 0, f"{si_cnt} 个")
                db.close()
except Exception as e:
    test("导入流程", False, str(e)[:120])

# ===== 8. 队伍分组 + ETL =====
print("\n" + "─" * 40)
print("8. Team Groups + ETL")
print("─" * 40)

try:
    if os.path.exists(SYS_B_DB):
        db = sqlite3.connect(SYS_B_DB)
        # 创建全局分组
        existing = db.execute('SELECT COUNT(*) FROM global_groups').fetchone()[0]
        if existing == 0:
            for gn in ("Top", "Mid", "Weak"):
                db.execute("INSERT INTO global_groups (name) VALUES (?)", (gn,))
            db.commit()
        gg = db.execute('SELECT id, name FROM global_groups').fetchall()
        test("全局分组已创建", len(gg) > 0, f"{len(gg)} 个")

        # 分配队伍
        for gid, gname in gg:
            teams = db.execute(
                "SELECT DISTINCT home_team FROM match_records LIMIT 20"
            ).fetchall()
            team_list = [r[0] for r in teams if r[0]]
            if team_list:
                lid = db.execute("SELECT si.league_id FROM match_records mr "
                                 "JOIN season_instances si ON si.id = mr.season_instance_id "
                                 "LIMIT 1").fetchone()
                if lid:
                    db.execute(
                        "INSERT OR REPLACE INTO league_group_teams "
                        "(league_id, global_group_id, role, teams_json) VALUES (?,?,?,?)",
                        (lid[0], gid, 'current', json.dumps(team_list))
                    )
        db.commit()
        test("队伍已分配", db.execute('SELECT COUNT(*) FROM league_group_teams').fetchone()[0] > 0)

        # 运行ETL
        from core.config_store import get_store
        from core.pipeline import ETLPipeline
        etl_store = get_store()
        pipeline = ETLPipeline(etl_store)
        run_id = pipeline.execute(league_ids=None)
        test("ETL执行完成", run_id > 0, f"Run #{run_id}")

        # 验证决策结果
        decisions = etl_store.get_decision_results(run_id)
        test("有决策结果", len(decisions) > 0, f"{len(decisions)} 条")
        db.close()
except Exception as e:
    test("ETL流程", False, str(e)[:120])

# ===== 报告 =====
print("\n" + "=" * 60)
total = PASS + FAIL + SKIP
print(f"Total: {total}  |  Pass: {PASS}  |  Fail: {FAIL}  |  Skip: {SKIP}")
print(f"Rate: {PASS * 100 // max(total, 1)}% ({PASS}/{total})")
sys.exit(0 if FAIL == 0 else 1)
