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

from etl.config_store import get_store
from modules.data_connector import get_connector
from modules.x_calculator import XValueCalculator
from modules.follow_list import get_follow_manager


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

                    # 获取该联赛的赛季列表
                    seasons = connector.get_seasons(selected_league['id'])
                    if seasons:
                        season_options = {
                            s['season_label']: s for s in seasons
                        }

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

    # ============ 运行ETL ============
    st.divider()
    st.subheader("运行ETL")

    if following:
        if st.button("🎯 运行ETL", type="primary"):
            st.divider()
            st.subheader("ETL 执行")
            with st.spinner("正在执行ETL..."):
                try:
                    from etl.pipeline import ETLPipeline
                    pipeline = ETLPipeline(store)
                    run_id = pipeline.run_etl(data_source='postgresql')
                    st.success(f"✅ ETL 执行完成！Run ID: {run_id}")
                    st.info("请前往「信号看板」页面查看结果")

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
