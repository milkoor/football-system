"""系統同步頁面

功能：
- 直接呼叫系統A的API，從網站抓取聯賽列表並儲存到資料庫
- 同步指定聯賽的賽季賽程
- 顯示同步進度和結果
"""

import streamlit as st
import time
import logging

from app import get_store
from modules.data_connector import get_connector
from modules.data_connector import DataConnector

# 配置日志
logger = logging.getLogger(__name__)


def render():
    st.title("🔄 系統同步")
    st.caption("呼叫系統A從網站抓取聯賽和賽季賽程")

    # 初始化
    store = get_store()
    connector = get_connector()

    # ============ 同步狀態 ============
    st.subheader("同步狀態")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("系統A連接", "✅ 正常" if connector else "❌ 失敗")

    with col2:
        try:
            stats = connector.get_crawl_stats()
            st.metric("總比賽數", stats.get('total_matches', 0))
        except Exception as e:
            st.metric("總比賽數", "❌")
            logger.warning(f"獲取總比賽數失敗: {e}")

    with col3:
        try:
            stats = connector.get_crawl_stats()
            st.metric("待爬取", stats.get('pending', 0))
        except Exception as e:
            st.metric("待爬取", "❌")
            logger.warning(f"獲取待爬取數量失敗: {e}")

    st.divider()

    # ============ 快速操作 ============
    st.subheader("快速操作")

    col_clear, col_sync = st.columns(2)

    with col_clear:
        if st.button("🧹 清除所有同步資料", type="secondary"):
            if st.warning("這會清除本地同步的所有資料，確定繼續嗎?", icon="⚠️"):
                with st.spinner("正在清除所有同步資料..."):
                    try:
                        connector.clear_sync_data()
                        st.success("✅ 所有同步資料已清除")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 清除失敗: {e}")

    with col_sync:
        if st.button("🔄 完整同步流程", type="primary"):
            with st.spinner("執行完整同步流程..."):
                try:
                    # 1. 同步聯賽
                    st.write("1. 同步聯賽列表...")
                    league_result = connector.sync_leagues_from_site()

                    # 2. 等待一會兒讓聯賽同步完成
                    time.sleep(2)

                    # 3. 同步所有聯賽的賽季
                    try:
                        leagues = connector.get_leagues(enabled=True)
                    except Exception as e:
                        st.error(f"獲取聯賽列表失敗: {e}")
                        leagues = []

                    if leagues:
                        st.write(f"2. 同步 {len(leagues)} 個聯賽的賽季...")

                        # 添加进度显示
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        success_count = 0
                        for i, league in enumerate(leagues):
                            try:
                                status_text.text(f"   同步 {i+1}/{len(leagues)}: {league['league_name_tw']}")
                                connector.sync_seasons_for_league(league['id'])
                                success_count += 1
                                progress_bar.progress((i+1)/len(leagues))
                                time.sleep(0.5)
                            except Exception as e:
                                st.warning(f"同步 {league['league_name_tw']} 失败: {e}")
                                continue

                        st.write(f"成功同步 {success_count} 个联赛的赛季")
                    else:
                        st.info("未找到可用聯賽")

                    st.success("完整同步流程完成!")
                except Exception as e:
                    st.error(f"同步流程失敗: {e}")

    st.divider()

    # ============ 同步聯賽列表 ============
    st.subheader("同步聯賽列表")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 同步所有聯賽", type="primary"):
            try:
                with st.spinner("正在同步聯賽列表..."):
                    result = connector.sync_leagues_from_site()
                    st.success(f"聯賽同步成功: {result.get('message')}")
                    st.rerun()
            except Exception as e:
                st.error(f"聯賽同步失敗: {e}")

    with col2:
        st.info("此功能會呼叫系統A的LeagueCrawler直接從網站抓取聯賽列表，並儲存到資料庫中。")

    # ============ 顯示當前聯賽列表 ============
    try:
        leagues = connector.get_leagues(enabled=True)
        if leagues:
            st.write(f"目前有 {len(leagues)} 個啟用的聯賽:")
            with st.expander("查看聯賽列表"):
                for league in leagues:
                    st.write(f"- {league.get('country', '')} - {league.get('league_name_tw', league.get('league_name_zh', ''))}")
        else:
            st.warning("資料庫中沒有聯賽資料，請先同步聯賽列表。")
    except Exception as e:
        st.error(f"取得聯賽列表失敗: {e}")

    st.divider()

    # ============ 同步賽季賽程 ============
    st.subheader("同步賽季賽程")

    selected_league = None
    try:
        leagues = connector.get_leagues(enabled=True)
        if leagues:
            league_options = {
                f"{l.get('country', '')} - {l.get('league_name_tw', l.get('league_name_zh', ''))}": l for l in leagues
            }
            selected_league_name = st.selectbox(
                "選擇聯賽",
                list(league_options.keys())
            )
            selected_league = league_options[selected_league_name]
        else:
            st.warning("請先同步聯賽列表")
    except Exception as e:
        st.error(f"取得聯賽列表失敗: {e}")

    if selected_league:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 同步賽季賽程", type="primary"):
                try:
                    with st.spinner(f"正在同步 {selected_league_name} 的賽季賽程..."):
                        result = connector.sync_seasons_for_league(selected_league['id'])
                        st.success(f"賽程同步成功: {result.get('message')}")
                except Exception as e:
                    st.error(f"賽程同步失敗: {e}")

        with col2:
            st.info("此功能會呼叫系統A的LeagueCrawler抓取指定聯賽的賽季賽程，並儲存到資料庫中。")

        st.divider()

        # 顯示比賽數量
        try:
            matches_result = connector.get_matches(
                league_id=selected_league['id'],
                page=1,
                page_size=1
            )
            total = matches_result.get('total', 0)
            st.metric("比賽數量", total)
        except Exception as e:
            st.error(f"取得比賽數量失敗: {e}")


if __name__ == "__main__":
    render()
