"""系統同步頁面

功能：
- 直接呼叫系統A的API，從網站抓取聯賽列表並儲存到資料庫
- 同步指定聯賽的賽季賽程
- 顯示同步進度和結果
"""

import streamlit as st
import time
import logging

from core.config_store import get_store
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

    col_clear, col_sync_all = st.columns(2)

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

    with col_sync_all:
        if st.button("🔄 一键同步所有联赛数据", type="primary"):
            with st.spinner("正在同步所有联赛数据..."):
                try:
                    # 1. 同步联赛列表
                    st.write("步骤 1/2: 同步联赛列表...")
                    league_result = connector.sync_leagues_from_site()
                    time.sleep(2)
                    st.success("✅ 联赛列表同步完成")

                    # 2. 同步所有联赛的赛季赛程
                    st.write("步骤 2/2: 同步所有联赛的赛季赛程...")
                    leagues = connector.get_leagues(enabled=True)
                    success_count = 0
                    fail_count = 0

                    for league in leagues:
                        try:
                            result = connector.sync_seasons_for_league(league['id'])
                            success_count += 1
                            st.write(f"✅ {league.get('league_name_tw', league.get('league_name_zh', ''))}")
                        except Exception as e:
                            fail_count += 1
                            st.warning(f"⚠️ {league.get('league_name_tw', league.get('league_name_zh', ''))}: {str(e)}")

                    st.success(f"🎉 一键同步完成! 成功: {success_count}, 失败: {fail_count}")
                    st.info("请前往「数据导入」页面继续后续流程")
                    st.rerun()
                except Exception as e:
                    st.error(f"同步流程失敗: {e}")

    st.divider()

    # ============ 联赛信息 ============
    st.subheader("联赛信息")
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

        st.divider()

        st.subheader("下一步操作指引")

        col1, col2 = st.columns(2)

        with col1:
            st.warning("⚠️ 重要提示")
            st.markdown("""
            同步賽季賽程成功，但數據尚未計算X值！

            **接下來需要執行：**
            1. 前往「数据导入」頁面
            2. 完成「關注管理」步驟
            3. 下載賠率數據
            4. 計算X值並導入到系統B

            只有完成這些步驟後，數據才會出現在ETL執行和其他功能中！
            """)

        with col2:
            st.info("🔄 快捷操作")
            st.markdown("""
            **請手動前往「数据导入」頁面**：

            點擊左側導航菜單中的「📥 数据导入」選項，
            然後按照以下步驟執行：
            1. 添加關注聯賽
            2. 下載賠率數據
            3. 計算X值並導入到系統B
            """)

        st.divider()

        if st.button("查看完整流程說明"):
            with st.expander("三步完整流程詳解"):
                st.markdown("""
                ### 1. 系統同步（當前頁面）
                - 同步聯賽列表
                - 同步賽季賽程
                - 獲取比賽基本信息

                ### 2. 数据导入 - 關注管理
                - 將需要分析的聯賽賽季添加到「關注名單」
                - 支持按國家、聯賽名稱篩選

                ### 3. 数据导入 - 下載賠率
                - 下載關注名單中所有比賽的賠率數據
                - 自動分批觸發爬取任務

                ### 4. 数据导入 - 計算X值
                - 計算所有已完成賠率爬取的比賽的X值
                - 自動同步到系統B的數據庫中
                - 支持批次處理，防止超時

                ### 5. ETL執行
                - 執行完整的數據分析流程
                - 進行分類、聚類、信號生成
                - 生成決策報表
                """)


if __name__ == "__main__":
    render()
