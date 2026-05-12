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

    # ============ 同步操作 ============
    st.divider()
    st.subheader("同步操作")

    following = follow_manager.get_all()
    if following:
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            sync_schedule_btn = st.button("🔄 同步赛程", type="primary")

        with col2:
            crawl_odds_btn = st.button("📥 爬取赔率", type="primary")

        with col3:
            calculate_x_btn = st.button("🧮 计算X值", type="primary")

        # 同步赛程操作
        if sync_schedule_btn:
            st.divider()
            st.subheader("同步赛程")
            for item in following:
                with st.spinner(f"正在同步 {item['league_name']} ({item['season_label']}) 赛季赛程..."):
                    try:
                        result = connector.sync_seasons_for_league(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}: {result.get('message', '同步成功')}")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

        # 爬取赔率操作
        if crawl_odds_btn:
            st.divider()
            st.subheader("爬取赔率")
            for item in following:
                with st.spinner(f"正在爬取 {item['league_name']} ({item['season_label']}) 赔率数据..."):
                    try:
                        result = connector.trigger_crawl(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}: 任务 {result.get('job_id', 'unknown')} 已启动")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

        # 计算X值操作
        if calculate_x_btn:
            st.divider()
            st.subheader("计算X值")
            for item in following:
                with st.spinner(f"正在计算 {item['league_name']} ({item['season_label']}) X值..."):
                    try:
                        result = connector.calculate_x_values(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}: 任务 {result.get('job_id', 'unknown')} 已启动")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

        # 一键同步所有操作
        st.divider()
        if st.button("🚀 一键同步所有", type="secondary"):
            st.divider()
            # 同步赛程
            st.subheader("1. 同步赛程")
            for item in following:
                with st.spinner(f"正在同步 {item['league_name']} ({item['season_label']})..."):
                    try:
                        result = connector.sync_seasons_for_league(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

            # 爬取赔率
            st.subheader("2. 爬取赔率")
            for item in following:
                with st.spinner(f"正在爬取 {item['league_name']} ({item['season_label']})..."):
                    try:
                        result = connector.trigger_crawl(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}: 任务 {result.get('job_id', 'unknown')}")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

            # 计算X值
            st.subheader("3. 计算X值")
            for item in following:
                with st.spinner(f"正在计算 {item['league_name']} ({item['season_label']})..."):
                    try:
                        result = connector.calculate_x_values(item['league_id'], item['season_label'])
                        st.success(f"✅ {item['league_name']} - {item['season_label']}: 任务 {result.get('job_id', 'unknown')}")
                    except Exception as e:
                        st.error(f"❌ {item['league_name']} - {item['season_label']}: {str(e)}")

            st.success("🎉 一键同步完成！")

    else:
        st.warning("请先添加关注的联赛赛季")

    # ============ 自动同步设定 ============
    st.divider()
    with st.expander("⏰ 自动同步设定", expanded=False):
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            auto_enabled = st.checkbox(
                "启用自动同步", value=True,
                key="auto_sync_enabled",
                help="启用后按设定时间间隔自动同步关注联赛的比赛、赔率并计算X值"
            )
        with col_b:
            st.number_input(
                "同步间隔（小时）", min_value=1, max_value=168, value=24,
                key="auto_sync_interval"
            )
        with col_c:
            st.caption("当前状态")
            st.metric("自动同步", "🟢 运行中" if st.session_state.get("auto_sync_enabled", True) else "🔴 已停用")
            if st.button("🔄 立即执行", type="secondary", key="btn_trigger_auto_sync"):
                try:
                    from modules.auto_sync import SyncScheduler
                    from modules.follow_list import get_follow_manager
                    from config.settings import get_settings
                    SyncScheduler(
                        connector=connector,
                        follow_manager=get_follow_manager(),
                        settings=get_settings()
                    ).run_sync_job()
                    st.success("✅ 自动同步任务已执行完成")
                except Exception as e:
                    st.error(f"❌ 执行自动同步失败: {e}")

    # ============ 下载赔率 ============
    st.divider()
    st.subheader("下载赔率")

    following = follow_manager.get_all()
    if following:
        # 显示统计信息
        try:
            total_matches = 0
            pending_matches = 0

            for item in following:
                matches_result = connector.get_matches(
                    league_id=item['league_id'],
                    season=item['season_label'],
                    page=1,
                    page_size=10000
                )
                total = matches_result.get('total', 0)
                total_matches += total

                # 获取待爬取的比赛数量
                pending_result = connector.get_matches(
                    league_id=item['league_id'],
                    season=item['season_label'],
                    crawl_status='pending',
                    page=1,
                    page_size=10000
                )
                pending = pending_result.get('total', 0)
                pending_matches += pending

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("关注赛季数量", len(following))
            with col2:
                st.metric("总比赛数", total_matches)
            with col3:
                st.metric("待爬取赔率", pending_matches)

        except Exception as e:
            st.error(f"統計數據獲取失敗: {e}")

        # 一键下载所有关注联赛的赔率
        if st.button("🚀 一键下载所有关注赔率", type="primary", key="download_all_odds"):
            with st.spinner("正在下载关注联赛的赔率..."):
                try:
                    all_pending = []

                    for item in following:
                        matches_result = connector.get_matches(
                            league_id=item['league_id'],
                            season=item['season_label'],
                            crawl_status='pending',
                            page=1,
                            page_size=10000
                        )
                        pending = matches_result.get('matches', [])
                        all_pending.extend(pending)

                    if all_pending:
                        st.write(f"找到 {len(all_pending)} 场待爬取的比赛")

                        # 分批触发爬取任务（每批500场）
                        batch_size = 500
                        for i in range(0, len(all_pending), batch_size):
                            batch = all_pending[i:i+batch_size]
                            match_ids = [m['match_id'] for m in batch]
                            result = connector.trigger_crawl(match_ids=match_ids)
                            st.write(f"批次 {i//batch_size + 1}: 任务 {result.get('job_id')} 已启动")

                        st.success(f"✅ 已启动 {len(all_pending)} 场比赛的赔率爬取任务")
                    else:
                        st.info("🎉 所有关注比赛的赔率数据已同步完成")

                except Exception as e:
                    st.error(f"下载赔率失败: {e}")
                    import traceback
                    st.error(traceback.format_exc())

    else:
        st.warning("請先添加聯賽賽季到關注名單")

    # ============ 计算X值 ============
    st.divider()
    st.subheader("计算X值")

    if following:
        if st.button("📊 一键计算所有X值并导入", type="primary", key="calculate_all_xvalues"):
            with st.spinner("正在计算所有比赛的X值并导入..."):
                try:
                    # 获取所有待计算的比赛
                    all_completed = []

                    for item in following:
                        matches_result = connector.get_matches(
                            league_id=item['league_id'],
                            season=item['season_label'],
                            crawl_status='completed',
                            page=1,
                            page_size=10000
                        )
                        completed = matches_result.get('matches', [])
                        all_completed.extend(completed)

                    if all_completed:
                        st.write(f"找到 {len(all_completed)} 场已完成赔率爬取的比赛")

                        # 分批计算X值
                        batch_size = 100
                        success_count = 0
                        imported_count = 0
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for i in range(0, len(all_completed), batch_size):
                            batch = all_completed[i:i+batch_size]
                            status_text.text(f"处理批次 {i//batch_size + 1}/{(len(all_completed) + batch_size - 1)//batch_size}")

                            # 计算X值
                            match_ids = [m['match_id'] for m in batch]
                            results = x_calculator.batch_calculate(match_ids)

                            # 保存X值结果到系统A
                            for result in results:
                                if result.get('status') == 'success':
                                    try:
                                        connector.save_x_value(result)
                                        success_count += 1
                                    except Exception as e:
                                        logger.warning(f"保存X值失败: {e}")

                            # 导入到系统B的match_records
                            for idx, result in enumerate(results):
                                if result.get('status') == 'success':
                                    try:
                                        match_data = batch[idx]

                                        # 同步联赛到系统B
                                        league_id_b = sync_league_to_system_b(store, connector, {
                                            'id': match_data['league_id'],
                                            'league_name_tw': match_data.get('league_name', ''),
                                            'country': '',
                                            'league_id': match_data['league_id']
                                        })

                                        # 同步赛季到系统B
                                        season_id_b = sync_season_to_system_b(store, league_id_b, match_data.get('season', '2024-2025'))

                                        # 创建MatchRecord
                                        from core.models import MatchRecord
                                        from core.settlement import SettlementCalculator

                                        # 解析轮次
                                        round_num = 1
                                        round_name = match_data.get('round_name', '')
                                        if round_name.startswith('R_'):
                                            try:
                                                round_num = int(round_name.replace('R_', ''))
                                            except:
                                                pass

                                        # 判断比赛是否已完成
                                        score_ft = match_data.get('score_ft', '')
                                        is_completed = False
                                        if score_ft and score_ft.strip():
                                            # 如果比分存在，认为比赛已完成
                                            is_completed = True

                                        record = MatchRecord(
                                            round_num=round_num,
                                            home_team=match_data.get('home_team', ''),
                                            away_team=match_data.get('away_team', ''),
                                            x_value=result.get('x_value', 0.0),
                                            settlement='',
                                            score=score_ft,
                                            link=result.get('movement_url', ''),
                                            play_type='HDP',
                                            target_team=result.get('target_team', ''),
                                            is_completed=is_completed,
                                            match_id=str(match_data.get('match_id', ''))
                                        )

                                        # 计算结算
                                        SettlementCalculator().calculate([record])

                                        # 保存到match_records
                                        store.upsert_match_records(
                                            season_id_b,
                                            'HDP',
                                            'Early',
                                            [record]
                                        )
                                        imported_count += 1

                                    except Exception as e:
                                        logger.error(f"导入match_records失败: {e}")
                                        import traceback
                                        st.error(traceback.format_exc())

                            progress_bar.progress(min((i+batch_size)/len(all_completed), 1.0))

                        st.success(f"✅ 成功计算 {success_count} 场比赛的X值，导入 {imported_count} 条记录到系统B")
                    else:
                        st.info("没有找到已完成赔率爬取的比赛，请先完成下载赔率步骤")

                except Exception as e:
                    st.error(f"计算X值失败: {e}")
                    import traceback
                    st.error(traceback.format_exc())
    else:
        st.warning("請先添加聯賽賽季到關注名單")

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

    # ============ 任务状态查看 ============
    st.divider()
    st.subheader("任务状态")

    if st.button("📋 查看爬取任务"):
        try:
            jobs = connector.get_crawl_jobs()
            if jobs:
                for job in jobs:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"任务 {job['job_id']}: {job['status']}")
                    with col2:
                        st.write(f"完成: {job['completed_matches']}/{job['total_matches']}")
                    with col3:
                        if job['status'] in ['pending', 'running']:
                            if st.button("停止", key=f"stop_{job['job_id']}"):
                                connector.stop_crawl_job(job['id'])
                                st.rerun()
            else:
                st.info("暂无爬虫任务")

        except Exception as e:
            st.error(f"获取任务列表失败: {e}")

    # ============ 系统状态 ============
    st.divider()
    st.subheader("系统状态")

    try:
        stats = connector.get_crawl_stats()
        if stats:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.metric("总比赛数", stats.get('total_matches', 0))
            with col2:
                st.metric("已爬取赔率", stats.get('completed', 0))
            with col3:
                st.metric("待爬取", stats.get('pending', 0))
    except Exception as e:
        st.error(f"获取统计信息失败: {e}")


if __name__ == "__main__":
    render()
