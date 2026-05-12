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
import concurrent.futures

from core.config_store import get_store
from modules.data_connector import get_connector, DataConnector

logger = logging.getLogger(__name__)


def render():
    st.title("🔄 系統同步")
    st.caption("呼叫系統A從網站抓取聯賽和賽季賽程")

    store = get_store()
    connector = get_connector()

    if "sync_jobs" not in st.session_state:
        st.session_state.sync_jobs = []
    if "sync_in_progress" not in st.session_state:
        st.session_state.sync_in_progress = False

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

    # ============ 自動同步設定 ============
    with st.expander("⏰ 自動同步設定", expanded=False):
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            auto_enabled = st.checkbox(
                "啟用自動同步",
                value=st.session_state.get("auto_sync_enabled", True),
                help="啟用後將定時自動同步關注聯賽的賽程和賠率"
            )
            st.session_state.auto_sync_enabled = auto_enabled

        with col2:
            interval_hours = st.number_input(
                "同步間隔（小時）",
                min_value=1,
                max_value=168,
                value=st.session_state.get("auto_sync_interval", 24),
                help="每隔多少小時自動執行一次同步"
            )
            st.session_state.auto_sync_interval = interval_hours

        with col3:
            st.caption("當前狀態")
            status_text = "🟢 運行中" if st.session_state.get("auto_sync_enabled", True) else "🔴 已停用"
            st.metric("自動同步", status_text)
            st.caption(f"間隔: {st.session_state.get('auto_sync_interval', 24)} 小時")
            if st.button("🔄 立即執行自動同步", type="secondary"):
                try:
                    from modules.auto_sync import SyncScheduler
                    from modules.follow_list import get_follow_manager
                    from config.settings import get_settings
                    sched = SyncScheduler(
                        connector=connector,
                        follow_manager=get_follow_manager(),
                        settings=get_settings()
                    )
                    sched.run_sync_job()
                    st.success("✅ 自動同步任務已執行完成")
                except Exception as e:
                    st.error(f"❌ 執行自動同步失敗: {e}")

    st.divider()

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
        sync_disabled = st.session_state.sync_in_progress
        help_text = "同步正在進行中，請等待完成" if sync_disabled else None
        if st.button(
            "🔄 一键同步所有联赛数据",
            type="primary",
            disabled=sync_disabled,
            help=help_text
        ):
            try:
                with st.spinner("步驟 1/3: 同步聯賽列表..."):
                    connector.sync_leagues_from_site()
                    time.sleep(1)
                st.success("✅ 联赛列表同步完成")

                leagues = connector.get_leagues(enabled=True)
                total = len(leagues)

                st.write(f"步驟 2/3: 觸發 {total} 個聯賽的賽季同步...")
                job_records = []
                progress_ui = st.progress(0, text="正在觸發聯賽同步...")

                def _trigger_one(league):
                    """单联赛触发函数（在子线程中运行）"""
                    name = league.get('league_name_tw', league.get('league_name_zh', ''))
                    try:
                        conn = DataConnector()
                        result = conn.sync_seasons_for_league(league['id'])
                        jid = result.get('job_id', 'unknown')
                        return {'league_name': name, 'job_id': jid, 'status': 'triggered'}
                    except Exception as e:
                        return {'league_name': name, 'job_id': None, 'status': 'failed', 'error': str(e)}
                    finally:
                        conn.close()

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                    fut_map = {pool.submit(_trigger_one, league): league for league in leagues}
                    for i, fut in enumerate(concurrent.futures.as_completed(fut_map), 1):
                        rec = fut.result()
                        job_records.append(rec)
                        progress_ui.progress(i / total, text=f"({i}/{total}) {rec['league_name']}")
                        if rec['status'] == 'triggered':
                            st.write(f"  ✅ ({i}/{total}) {rec['league_name']} — 任務 {rec['job_id']}")
                        else:
                            st.write(f"  ⚠️ ({i}/{total}) {rec['league_name']}: {rec.get('error', '?')}")

                st.session_state.sync_jobs = job_records
                st.session_state.sync_in_progress = True

                st.success(f"🎉 已觸發 {len(job_records)} 個聯賽的同步任務")
                st.info("💡 同步任務在後台非同步執行，可以切換到其他頁面，返回此頁面可查看進度")
                st.rerun()
            except Exception as e:
                st.error(f"同步流程失敗: {e}")

    # ============ 同步進度（跨頁面持久化） ============
    if st.session_state.sync_in_progress and st.session_state.sync_jobs:
        st.divider()
        st.subheader("📊 同步進度")

        updated = []
        running = 0
        completed = 0
        failed = 0
        total = 0

        for job in st.session_state.sync_jobs:
            status = job.get('status', 'unknown')
            if job.get('job_id') and status in ('triggered', 'running'):
                try:
                    detail = connector.get_crawl_job(job['job_id'])
                    if detail:
                        status = detail.get('status', status)
                        job['status'] = status
                except Exception:
                    pass

            if status == 'completed':
                completed += 1
            elif status in ('running', 'triggered', 'pending'):
                running += 1
            elif status == 'failed':
                failed += 1
            else:
                total += 1
            updated.append(job)

        st.session_state.sync_jobs = updated

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("總計", len(updated))
        with c2:
            st.metric("✅ 完成", completed)
        with c3:
            st.metric("⏳ 執行中", running)
        with c4:
            st.metric("❌ 失敗", failed)

        with st.expander("查看各聯賽狀態", expanded=True):
            for job in st.session_state.sync_jobs:
                s = job.get('status', 'unknown')
                icons = {'completed': '✅', 'running': '⏳', 'triggered': '⏳',
                         'failed': '❌', 'pending': '⏳'}
                icon = icons.get(s, '❓')
                st.write(f"{icon} {job['league_name']} — {s}")

        all_done = (running == 0)
        if all_done:
            st.success(f"🎉 所有聯賽同步完成！成功 {completed}，失敗 {failed}")
            st.session_state.sync_in_progress = False
            st.info("请前往「数据导入」页面继续后续流程")
            if st.button("🔄 刷新頁面"):
                st.rerun()
        else:
            st.info("⏳ 部分聯賽仍在同步中，每 5 秒自動刷新...")
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