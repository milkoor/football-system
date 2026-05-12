"""系統同步頁面

功能：
- 直接呼叫系統A的API，從網站抓取聯賽列表並儲存到資料庫
- 同步指定聯賽的賽季賽程
- 顯示同步進度和結果
- 自動同步設定與狀態展示
"""

import streamlit as st
import time
import logging

from modules.data_connector import get_connector

logger = logging.getLogger(__name__)


def render():
    st.title("🔄 系統同步")
    st.caption("呼叫系統A從網站抓取聯賽和賽季賽程")

    connector = get_connector()

    if "batch_in_progress" not in st.session_state:
        st.session_state.batch_in_progress = False
    if "batch_job_id" not in st.session_state:
        st.session_state.batch_job_id = None
    if "batch_start_time" not in st.session_state:
        st.session_state.batch_start_time = None

    st.subheader("同步狀態")

    # 赛季维度统计
    total_seasons = 0
    synced_seasons = 0
    try:
        stats = connector.get_season_stats()
        total_seasons = stats.get('total_seasons', 0)
        synced_seasons = stats.get('synced_seasons', 0)
    except:
        pass

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("系統A連接", "✅ 正常" if connector else "❌ 失敗")
    with col2:
        try:
            leagues = connector.get_leagues(enabled=True)
            st.metric("聯賽數", len(leagues))
        except:
            st.metric("聯賽數", "?")
    with col3:
        st.metric("賽季總數", total_seasons)
    with col4:
        st.metric("已同步賽季", synced_seasons, delta=total_seasons - synced_seasons, delta_color="inverse")

    st.divider()

    st.subheader("快速操作")

    col_clear, col_sync_all = st.columns(2)

    with col_clear:
        if st.button("🧹 清除所有同步資料", type="secondary", key="btn_clear_sync"):
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
        sync_disabled = st.session_state.batch_in_progress
        help_text = "同步正在進行中，請等待完成" if sync_disabled else None
        if st.button(
            "🔄 一键同步所有联赛数据",
            type="primary",
            key="btn_sync_all",
            disabled=sync_disabled,
            help=help_text
        ):
            try:
                with st.spinner("步驟 1/3: 同步聯賽列表..."):
                    connector.sync_leagues_from_site()
                    time.sleep(1)
                st.success("✅ 联赛列表同步完成")

                st.write("步驟 2/3: 啟動批量同步...")
                result = connector.sync_all_seasons()
                job_id = result.get('job_id', 'unknown')
                st.success(f"✅ 批量同步任務已啟動 — job_id={job_id}")

                st.session_state.batch_job_id = job_id
                st.session_state.batch_in_progress = True
                st.session_state.batch_start_time = time.time()
                st.rerun()
            except Exception as e:
                st.error(f"同步流程失敗: {e}")

    # ============ 批量同步進度 ============
    if st.session_state.batch_in_progress and st.session_state.batch_job_id:
        st.divider()
        st.subheader("📊 批量同步進度")

        try:
            job = connector.get_crawl_job(st.session_state.batch_job_id)
            if not job:
                st.warning("無法查詢同步任務狀態")
                if st.button("🔄 重新檢查", key="btn_retry_check"):
                    st.rerun()
            else:
                status = job.get('status', 'unknown')
                created = job.get('total_matches', 0)
                skipped = job.get('completed_matches', 0)
                failed = job.get('failed_matches', 0)

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("狀態", status)
                with col_b:
                    st.metric("新增賽季記錄", created)
                with col_c:
                    st.metric("已存在(跳過)", skipped)

                if status == "completed":
                    st.success(f"🎉 批量同步完成！新增 {created} 個賽季記錄，跳過 {skipped}")
                    st.session_state.batch_in_progress = False
                    st.session_state.batch_job_id = None
                elif status == "failed":
                    st.error(f"❌ 批量同步失敗: {job.get('error_message', '未知錯誤')}")
                    st.session_state.batch_in_progress = False
                    st.session_state.batch_job_id = None
                else:
                    elapsed = time.time() - (st.session_state.batch_start_time or time.time())
                    st.info(f"⏳ 同步進行中… 已用 {elapsed:.0f}s")
                    time.sleep(3)
                    st.rerun()
        except Exception as e:
            st.warning(f"獲取進度失敗: {e}，5 秒後重試")
            time.sleep(5)
            st.rerun()

    st.divider()

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
    st.subheader("下一步")
    st.markdown("""
    **前往「📥 数据导入」頁面** 完成後續操作：
    1. 添加關注聯賽/賽季
    2. 同步賽程（下載比賽數據）
    3. 爬取賠率
    4. 計算X值
    """)


if __name__ == "__main__":
    render()