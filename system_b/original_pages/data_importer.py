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
        st.session_state.sync_step = None  # None / 'sync' / 'crawl' / 'xcalc' / 'done'

    following = follow_manager.get_all()
    if following:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("关注赛季数量", len(following))
        with col2:
            total = sum(connector.get_matches(league_id=item['league_id'], page=1, page_size=1).get('total', 0) for item in following)
            st.metric("总比赛数", total)
        with col3:
            pending = sum(connector.get_matches(league_id=item['league_id'], crawl_status='pending', page=1, page_size=1).get('total', 0) for item in following)
            st.metric("待爬取赔率", pending)

        step = st.session_state.sync_step
        if step is None:
            if st.button("🚀 完整同步（赛程→赔率→X值）", type="primary", key="btn_full_sync"):
                st.session_state.sync_step = 'sync'
                st.session_state.sync_results = []
                st.rerun()

        elif step == 'sync':
            st.caption("步骤 1/3: 同步赛程...")
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
            st.caption("步骤 1/3: 等待赛程同步完成...")
            remaining = []
            for jid in st.session_state.get('sync_pending', []):
                try:
                    job = connector.get_crawl_job(jid)
                    if job and job.get('status') in ('running', 'pending', None):
                        remaining.append(jid)
                except:
                    remaining.append(jid)
            st.progress((len(st.session_state.sync_pending) - len(remaining)) / max(len(st.session_state.sync_pending), 1))
            if remaining:
                st.info(f"等待 {len(remaining)} 个同步任务完成...")
                time.sleep(3)
                st.rerun()
            else:
                st.success("✅ 赛程同步完成")
                st.session_state.sync_step = 'crawl'
                st.rerun()

        elif step == 'crawl':
            st.caption("步骤 2/3: 触发赔率爬取...")
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
            st.caption("步骤 2/3: 等待赔率爬取完成...")
            remaining = []
            for jid in st.session_state.get('crawl_pending', []):
                try:
                    job = connector.get_crawl_job(jid)
                    if job and job.get('status') in ('running', 'pending', None):
                        remaining.append(jid)
                except:
                    remaining.append(jid)
            st.progress((len(st.session_state.crawl_pending) - len(remaining)) / max(len(st.session_state.crawl_pending), 1))
            if remaining:
                st.info(f"等待 {len(remaining)} 个爬取任务完成...")
                time.sleep(3)
                st.rerun()
            else:
                st.success("✅ 赔率爬取完成")
                st.session_state.sync_step = 'xcalc'
                st.rerun()

        elif step == 'xcalc':
            st.caption("步骤 3/3: 计算X值并导入系统B...")
            all_completed = []
            for item in following:
                try:
                    mr = connector.get_matches(league_id=item['league_id'], crawl_status='completed', page=1, page_size=10000)
                    for m in (mr.get('matches') or mr.get('data') or []):
                        all_completed.append(m)
                except:
                    pass

            if all_completed:
                batch_size = 100
                success = 0
                imported = 0
                prog = st.progress(0)
                for i in range(0, len(all_completed), batch_size):
                    batch = all_completed[i:i+batch_size]
                    match_ids = [m['match_id'] for m in batch]
                    results = x_calculator.batch_calculate(match_ids)

                    for r in results:
                        if r.get('status') == 'success':
                            try:
                                connector.save_x_value(r)
                                success += 1
                            except:
                                pass

                    for idx, r in enumerate(results):
                        if r.get('status') == 'success':
                            try:
                                md = batch[idx]
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
                    prog.progress(min((i + batch_size) / len(all_completed), 1.0))

                st.success(f"🎉 完整同步完成！计算 {success} 条X值，导入 {imported} 条记录")
            else:
                st.warning("没有已同步的比赛数据")

            st.session_state.sync_step = 'done'
            st.rerun()

        else:  # done
            st.success("✅ 完整同步已完成，可再次点击按钮重新同步")
            if st.button("🔄 重新同步", key="btn_reset_sync"):
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
            st.metric("状态", "🟢 运行中" if is_running else "🔴 已停用")
        with col_b:
            from config.settings import get_settings
            interval = get_settings().sync_interval_hours
            st.metric("同步间隔", f"{interval} 小时")
        with col_c:
            if st.button("🔄 立即执行", type="secondary", key="btn_trigger_auto_sync"):
                try:
                    from modules.auto_sync import SyncScheduler
                    from config.settings import get_settings
                    SyncScheduler(
                        connector=connector,
                        follow_manager=get_follow_manager(),
                        settings=get_settings()
                    ).run_sync_job()
                    st.success("✅ 自动同步任务已执行完成")
                except Exception as e:
                    st.error(f"❌ 执行自动同步失败: {e}")

        if not is_running:
            st.caption("自动同步未启用。设置 SYNC_ENABLED=true 环境变量并重启容器以启用。")

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
                    run_id = pipeline.run_etl(data_source='postgresql')
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
