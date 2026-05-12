"""数据导入页面

功能：
- 关注管理：添加/删除关注的联赛和赛季
- 数据同步：同步赛程、爬取赔率、计算X值
- 运行ETL：从系统A PostgreSQL读取数据并运行ETL

Validates: Requirements 9.3, 10.2, 16.1, 16.2, 16.4, 16.5, 16.6
"""

import streamlit as st
import logging
import time
from typing import List, Dict, Any
from datetime import datetime

from core.config_store import get_store
from modules.data_connector import get_connector
from modules.x_calculator import XValueCalculator
from modules.follow_list import get_follow_manager
from utils.system_a_mapper import sync_league_to_system_b, sync_season_to_system_b


logger = logging.getLogger(__name__)


@st.cache_data(ttl=300)  # 缓存5分钟
def fetch_leagues(_connector):
    """获取联赛列表，带缓存"""
    try:
        leagues = _connector.get_leagues(enabled=True)
        return leagues
    except Exception as e:
        st.error(f"获取联赛失败: {e}")
        return []


@st.cache_data(ttl=300)  # 缓存5分钟
def fetch_seasons(_connector, league_id):
    """获取指定联赛的赛季列表，带缓存"""
    try:
        seasons = _connector.get_seasons(league_id)
        return seasons
    except Exception as e:
        st.error(f"获取赛季失败: {e}")
        return []


def render():
    st.title("8️⃣ 数据导入")
    st.caption("关注驱动的完整流程：添加关注 → 同步数据 → 运行ETL")

    # 初始化
    store = get_store()
    connector = get_connector()
    x_calculator = XValueCalculator(connector)
    follow_manager = get_follow_manager()

    # ============ 关注管理 ============
    st.divider()
    st.subheader("关注管理")

    # 显示已同步的联赛赛季供选择
    col1, col2 = st.columns([1, 1])

    with col1:
        st.caption("添加到关注名单")

        # 刷新按钮
        if st.button("🔄 刷新联赛/赛季数据", key="refresh_leagues", type="secondary"):
            st.cache_data.clear()  # 清除所有缓存
            st.rerun()

        try:
            # 获取已同步的联赛列表（带缓存）
            all_leagues = fetch_leagues(connector)
            if all_leagues:
                league_options = {
                    f"{l.get('country', '')} - {l.get('league_name_tw', l.get('league_name_zh', ''))}": l
                    for l in all_leagues
                }

                selected_league_name = st.selectbox(
                    "选择联赛",
                    ["請選擇聯賽"] + list(league_options.keys()),
                    index=0
                )

                selected_league = None
                selected_season_name = None
                selected_season = None

                if selected_league_name and selected_league_name != "請選擇聯賽":
                    selected_league = league_options[selected_league_name]

                    # 获取该联赛的赛季列表（从API同步的结果）
                    seasons = connector.get_seasons(selected_league['id'])

                    # 本地生成期望的赛季标签（当前年-1 ~ 当前年-4），作为 API 结果的兜底
                    _cur = datetime.now().year
                    _expected_labels = [
                        f"{_cur - y - 1}-{_cur - y}"
                        for y in range(4)  # 生成最近 4 个赛季
                    ]

                    # 合并 API 赛季 + 本地生成的赛季标签
                    season_options = {}
                    if seasons:
                        for s in seasons:
                            season_options[s['season_label']] = s
                    for lbl in _expected_labels:
                        if lbl not in season_options:
                            season_options[lbl] = {"season_label": lbl}

                    selected_season_name = st.selectbox(
                        "选择赛季",
                        ["請選擇賽季"] + list(season_options.keys()),
                        index=0
                    )

                    if selected_season_name and selected_season_name != "請選擇賽季":
                        selected_season = season_options[selected_season_name]

                if selected_league and selected_season:
                    if st.button("➕ 添加到关注名单", type="primary"):
                        success = follow_manager.add(
                            league_id=selected_league['id'],
                            league_name=selected_league_name,
                            season_label=selected_season_name,
                            country=selected_league.get('country', '')
                        )

                        if success:
                            st.success(f"✅ 已添加到关注名单：{selected_league_name} - {selected_season_name}")
                        else:
                            st.warning(f"⚠️ 已在关注名单中：{selected_league_name} - {selected_season_name}")

                        st.rerun()
            else:
                st.info("請先到系統同步頁面同步聯賽和賽季")

        except Exception as e:
            st.error(f"獲取數據失敗: {e}")

    with col2:
        st.caption("管理关注名单")
        following = follow_manager.get_all()
        if following:
            st.write(f"关注名单（{len(following)}个）：")
            with st.expander("查看关注名单"):
                for item in following:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"{item.get('country', '')} - {item.get('league_name')} ({item.get('season_label')})")
                    with col_b:
                        if st.button("删除", key=f"del_{item['league_id']}_{item['season_label']}"):
                            follow_manager.remove(item['league_id'], item['season_label'])
                            st.success(f"✅ 删除成功")
                            st.rerun()
        else:
            st.info("暂无关注的联赛赛季")

    # ============ 完整同步（赛程 + 赔率 + X值） ============
    st.divider()
    st.subheader("完整同步")

    if "sync_step" not in st.session_state:
        st.session_state.sync_step = None
    if "sync_busy" not in st.session_state:
        st.session_state.sync_busy = False

    following = follow_manager.get_all()
    busy = st.session_state.sync_busy

    if following:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.metric("关注赛季数量", len(following))
        with col2:
            try:
                total_matches = sum(connector.get_matches(league_id=item['league_id'], page=1, page_size=1).get('total', 0) for item in following)
            except:
                total_matches = "?"
            st.metric("比赛总数", total_matches)
        with col3:
            try:
                completed = sum(connector.get_matches(league_id=item['league_id'], crawl_status='completed', page=1, page_size=1).get('total', 0) for item in following)
            except:
                completed = "?"
            st.metric("已爬取", completed, delta=f"{total_matches - completed} 待爬取" if isinstance(total_matches, int) and isinstance(completed, int) else None)

        step = st.session_state.sync_step

        # ---- 状态显示 ----
        status_map = {
            'sync': '⏳ 步骤1/3: 触发赛程同步...',
            'poll_sync': '⏳ 步骤1/3: 等待赛程同步完成...',
            'crawl': '⏳ 步骤2/3: 触发赔率爬取...',
            'poll_crawl': '⏳ 步骤2/3: 正在爬取赔率...',
            'xcalc': '⏳ 步骤3/3: 计算X值并导入系统B...',
        }
        if step in status_map:
            st.info(status_map[step])

        # ---- 步骤执行 ----
        if step is None:
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("🚀 完整同步（赛程→赔率→X值）", type="primary", key="btn_full_sync", disabled=busy):
                    st.session_state.sync_step = 'sync'
                    st.session_state.sync_busy = True
                    st.session_state.sync_results = []
                    st.rerun()
            with col_b:
                if st.button("📥 仅导入到系统B", type="secondary", key="btn_import_only", disabled=busy):
                    st.session_state.sync_step = 'xcalc'
                    st.session_state.sync_busy = True
                    st.rerun()

        elif step == 'sync':
            pending_jobs = []
            for item in following:
                try:
                    result = connector.sync_seasons_for_league(item['league_id'], item['season_label'])
                    jid = result.get('job_id')
                    if jid:
                        pending_jobs.append(jid)
                except Exception as e:
                    st.warning(f"{item['league_name']} 同步触发失败: {e}")
            st.session_state.sync_pending = pending_jobs
            st.session_state.sync_step = 'poll_sync'
            st.rerun()

        elif step == 'poll_sync':
            remaining = []
            for jid in st.session_state.get('sync_pending', []):
                try:
                    job = connector.get_crawl_job(jid)
                    if job and job.get('status') in ('running', 'pending', None):
                        remaining.append(jid)
                except:
                    remaining.append(jid)
            total_sync = len(st.session_state.sync_pending)
            done_sync = total_sync - len(remaining)
            if total_sync > 0:
                st.progress(done_sync / total_sync, text=f"已完成 {done_sync}/{total_sync}")
            if remaining:
                time.sleep(3)
                st.rerun()
            else:
                st.success("✅ 赛程同步完成")
                st.session_state.sync_step = 'crawl'
                st.rerun()

        elif step == 'crawl':
            crawl_jobs = []
            for item in following:
                try:
                    result = connector.trigger_crawl(item['league_id'], item['season_label'])
                    jid = result.get('job_id')
                    if jid:
                        crawl_jobs.append(jid)
                except Exception as e:
                    st.warning(f"{item['league_name']} 爬取触发失败: {e}")
            st.session_state.crawl_pending = crawl_jobs
            st.session_state.sync_step = 'poll_crawl'
            st.rerun()

        elif step == 'poll_crawl':
            total_task = 0
            done_task = 0
            remaining = []
            for jid in st.session_state.get('crawl_pending', []):
                try:
                    job = connector.get_crawl_job(jid)
                    if job:
                        s = job.get('status')
                        if s in ('running', 'pending', None):
                            remaining.append(jid)
                        total_task += job.get('total_matches', 0)
                        done_task += job.get('completed_matches', 0) + job.get('failed_matches', 0)
                except:
                    remaining.append(jid)

            if total_task > 0:
                st.progress(min(done_task / total_task, 1.0),
                           text=f"已处理 {done_task}/{total_task} 场比赛")
            else:
                st.progress(0.5, text="等待爬虫开始...")

            col_skip, _ = st.columns([1, 3])
            with col_skip:
                skip = st.button("⏭️ 先看结果, 稍后继续爬", key="btn_skip_crawl")

            if remaining and not skip:
                time.sleep(5)
                st.rerun()
            else:
                st.success("✅ 赔率爬取完成" if not remaining else "⏭️ 已跳过爬虫等待")
                st.session_state.sync_step = 'xcalc'
                st.rerun()

        elif step == 'xcalc':
            all_completed = []
            for item in following:
                try:
                    mr = connector.get_matches(league_id=item['league_id'], crawl_status='completed', page=1, page_size=10000)
                    for m in (mr.get('matches') or mr.get('data') or []):
                        all_completed.append(m)
                except:
                    pass
            # 也获取 pending 的(可能爬虫还在跑但用户跳过了)
            all_pending = []
            for item in following:
                try:
                    mr = connector.get_matches(league_id=item['league_id'], crawl_status='pending', page=1, page_size=10000)
                    for m in (mr.get('matches') or mr.get('data') or []):
                        all_pending.append(m)
                except:
                    pass

            total_found = len(all_completed) + len(all_pending)
            if all_completed or all_pending:
                st.info(f"找到 {len(all_completed)} 场已爬取 + {len(all_pending)} 场待爬取的比赛，共 {total_found} 场")
            else:
                st.warning("⚠️ 数据库中没有比赛数据。请先点击「完整同步」完成赛程同步。")
                if st.button("← 返回", key="btn_back_from_xcalc"):
                    st.session_state.sync_step = None
                    st.session_state.sync_busy = False
                    st.rerun()

            if all_completed:
                batch_size = 100
                success = 0
                imported = 0
                prog = st.progress(0)
                for i in range(0, len(all_completed), batch_size):
                    batch = all_completed[i:i+batch_size]
                    # 分出已有比分(已完成)的比赛，跳过X值计算
                    active = [m for m in batch if not m.get('score_ft', '').strip()]
                    done_count = len(batch) - len(active)

                    results = []
                    if active:
                        match_ids = [m['match_id'] for m in active]
                        results = x_calculator.batch_calculate(match_ids)
                    else:
                        results = [{"status": "skipped"} for _ in active]

                    for r in results:
                        if r.get('status') == 'success':
                            try:
                                connector.save_x_value(r)
                                success += 1
                            except:
                                pass

                    for idx, (md, r) in enumerate(zip(active, results)):
                        if r.get('status') == 'success':
                            try:
                                lid_b = sync_league_to_system_b(store, connector, md)
                                sid_b = sync_season_to_system_b(store, lid_b, md.get('season', '2024-2025'))
                                from core.models import MatchRecord
                                from core.settlement import SettlementCalculator
                                record = MatchRecord(
                                    round_num=int(md.get('round_name', '1').replace('R_', '')),
                                    home_team=md.get('home_team', ''),
                                    away_team=md.get('away_team', ''),
                                    x_value=r.get('x_value', 0.0),
                                    settlement='', score=md.get('score_ft', ''),
                                    link=r.get('movement_url', ''),
                                    play_type='HDP',
                                    target_team=r.get('target_team', ''),
                                    is_completed=bool(md.get('score_ft', '').strip()),
                                    match_id=str(md.get('match_id', ''))
                                )
                                SettlementCalculator().calculate([record])
                                store.upsert_match_records(sid_b, 'HDP', 'Early', [record])
                                imported += 1
                            except Exception as e:
                                logger.error(f"导入失败: {e}")

                    if done_count:
                        st.caption(f"批次 {i//batch_size+1}: 跳过 {done_count} 场已完成比赛")
                    prog.progress(min((i + batch_size) / len(all_completed), 1.0))

                st.success(f"🎉 完整同步完成！计算 {success} 条X值，导入 {imported} 条记录到系统B")
                st.info("💡 接下来请点击「运行ETL」生成报表，然后前往「报表看板」查看决策信号。")
            elif all_pending:
                st.warning("比赛数据已同步，但赔率尚未爬取完成。请等待爬虫结束后再次点击「仅导入到系统B」。")
            else:
                st.warning("暂无数据可导入。")

            st.session_state.sync_step = 'done'
            st.session_state.sync_busy = False
            st.rerun()

        else:  # done
            st.success("✅ 处理完成，可再次点击按钮执行新的同步。")
            if st.button("🔄 再来一次", key="btn_reset_sync"):
                st.session_state.sync_step = None
                st.rerun()
                st.session_state.sync_step = None
                st.rerun()
    else:
        st.warning("请先添加关注的联赛赛季")

    # ============ 自动同步设定 ============
    st.divider()
    with st.expander("⏰ 自动同步设定", expanded=False):
        sched = st.session_state.get("auto_scheduler")
        is_running = sched is not None and sched.get_scheduler() is not None

        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            enable = st.checkbox("启用自动同步", value=is_running, key="chk_auto_enable")
        with col_b:
            hours = st.number_input("同步间隔（小时）", min_value=1, max_value=168,
                                     value=st.session_state.get("auto_interval", 24),
                                     key="num_auto_interval")
        with col_c:
            if st.button("💾 应用设置", type="primary", key="btn_apply_auto"):
                try:
                    sched.reschedule(interval_hours=int(hours), enabled=enable)
                    st.session_state.auto_interval = int(hours)
                    st.success(f"✅ 已{'启用' if enable else '停用'}自动同步，间隔 {int(hours)} 小时")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 设置失败: {e}")

        if is_running:
            st.caption(f"🟢 运行中 — 每 {sched._interval}h 执行一次（从文件读取配置可覆盖env）")
        else:
            st.caption("🔴 已停用 — 勾选上方复选框并点击应用设置以启用")

        if st.button("🔄 立即执行一次", type="secondary", key="btn_trigger_auto_sync"):
            try:
                from config.settings import get_settings
                sched.run_sync_job()
                st.success("✅ 自动同步任务已执行完成")
            except Exception as e:
                st.error(f"❌ 执行失败: {e}")

    # ============ 运行ETL ============
    st.divider()
    st.subheader("运行ETL")

    if following:
        if st.button("🎯 运行ETL", type="primary"):
            st.divider()
            st.subheader("ETL 执行")
            with st.spinner("正在执行ETL..."):
                try:
                    from core.pipeline import ETLPipeline
                    pipeline = ETLPipeline(store)
                    run_id = pipeline.execute(league_ids=None)  # 所有联赛
                    st.success(f"✅ ETL 执行完成！Run ID: {run_id}")
                    st.info("请前往「报表看板」页面查看结果")

                except Exception as e:
                    st.error(f"❌ ETL 执行失败: {str(e)}")
                    import traceback
                    st.error(traceback.format_exc())

    else:
        st.warning("请先添加关注的联赛赛季")


if __name__ == "__main__":
    render()
