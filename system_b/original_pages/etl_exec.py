"""ETL 執行頁面。

功能：
- 顯示有 match_records 資料的聯賽清單，允許勾選
- 點擊「執行 ETL」觸發 pipeline，顯示處理進度
- 完成後顯示結果摘要

Validates: Requirements 9.3, 10.2, 16.1, 16.2, 16.4, 16.5, 16.6
"""

import streamlit as st

from core.config_store import get_store
from core.pipeline import ETLPipeline
from modules.data_connector import get_connector
from utils.system_a_mapper import get_league_display_name, find_league_by_name_fuzzy

def render():
    store = get_store()

    st.title("🚀 ETL 執行")
    st.caption("手動執行計算流程")

    # ---------------------------------------------------------------------------
    # 聯賽清單（只顯示有 match_records 的）
    # ---------------------------------------------------------------------------

    leagues = store.list_leagues(active_only=True)

    ready_leagues = []
    for lg in leagues:
        seasons = store.list_season_instances(lg.id)
        current = next((s for s in seasons if s.role == "current"), None)
        previous = next((s for s in seasons if s.role == "previous"), None)
        if not current:
            continue

        curr_counts = store.get_match_record_counts(current.id)
        prev_counts = store.get_match_record_counts(previous.id) if previous else {}

        # Show league if either current or previous has records
        if curr_counts or prev_counts:
            ready_leagues.append((lg, current, curr_counts, previous, prev_counts))

    if not ready_leagues:
        st.warning("沒有已同步比賽紀錄的聯賽。請先至「📥 数据导入」頁面點擊「僅導入到系統B」按鈕，將比賽數據寫入本地資料庫後再來執行 ETL。")
        st.stop()

    st.subheader("可執行的聯賽")

    # Group by continent for filtering - 使用标准化的洲别值
    _continents = set()
    for lg, _, _, _, _ in ready_leagues:
        lg_continent = lg.continent
        if not lg_continent or lg_continent.strip() == "":
            lg_continent = "OTHER"
        _continents.add(lg_continent)
    _continents = sorted(list(_continents))
    etl_continent_filter = st.selectbox("篩選洲別", ["全部"] + _continents, key="etl_continent")

    # Select all / none
    sel_col1, sel_col2 = st.columns([1, 1])
    with sel_col1:
        if st.button("✅ 全選"):
            st.session_state["etl_select_all"] = True
            st.rerun()
    with sel_col2:
        if st.button("❎ 全不選"):
            st.session_state["etl_select_all"] = False
            st.rerun()

    _select_default = st.session_state.get("etl_select_all", True)

    # 根据洲别筛选
    filtered_leagues = []
    for lg, season, curr_counts, previous, prev_counts in ready_leagues:
        lg_continent = lg.continent
        if not lg_continent or lg_continent.strip() == "":
            lg_continent = "OTHER"
        if etl_continent_filter == "全部" or lg_continent == etl_continent_filter:
            filtered_leagues.append((lg, season, curr_counts, previous, prev_counts))

    if not filtered_leagues:
        st.info(f"洲别「{etl_continent_filter}」下没有可执行的联赛")
    else:
        selected_ids: list[int] = []
        for lg, season, curr_counts, previous, prev_counts in filtered_leagues:
            curr_total = sum(curr_counts.values())
            prev_total = sum(prev_counts.values())
            parts = []
            if curr_counts:
                parts.append(f"本季 {curr_total} 筆")
            if prev_counts:
                parts.append(f"上季 {prev_total} 筆")
            detail = "、".join(parts) if parts else "無紀錄"
            label = f"{lg.code} - {lg.name_zh}（{season.label}，{detail}）"
            if not curr_counts:
                label += " ⚠️ 本季無紀錄（僅用上季資料產生訊號）"
            checked = st.checkbox(
                label,
                value=_select_default,
                key=f"chk_{lg.id}",
            )
            if checked:
                selected_ids.append(lg.id)

    # ---------------------------------------------------------------------------
    # 彈性賽季選擇（設計決策 6）
    # ---------------------------------------------------------------------------

    with st.expander("🔧 進階：自訂賽季配對"):
        st.caption("預設使用 role=current/previous。如需指定其他賽季配對，請在此設定。")
        custom_pairs: dict[int, tuple[int, int | None]] = {}

        # 检查是否有选中的联赛
        if selected_ids and 'filtered_leagues' in locals():
            for lg, season, curr_counts, previous_s, prev_counts in filtered_leagues:
                if lg.id not in selected_ids:
                    continue
                all_seasons = store.list_season_instances(lg.id)
                if len(all_seasons) <= 1:
                    continue

                # 找出預設的 current/previous
                default_current = next((s for s in all_seasons if s.role == "current"), all_seasons[0])
                default_previous = next((s for s in all_seasons if s.role == "previous"), None)

                st.markdown(f"**{lg.code}**")
                c1, c2 = st.columns(2)
                s_opts = {f"{s.label} (id={s.id})": s.id for s in all_seasons}
                s_keys = list(s_opts.keys())

                # 本季預設選中 role=current 的賽季
                curr_default_key = f"{default_current.label} (id={default_current.id})"
                curr_default_idx = s_keys.index(curr_default_key) if curr_default_key in s_keys else 0

                with c1:
                    curr_key = st.selectbox(
                        "本季", s_keys,
                        index=curr_default_idx,
                        key=f"cp_curr_{lg.id}",
                    )

                # 上季預設選中 role=previous 的賽季（若有）
                prev_options = ["（無上季）"] + s_keys
                if default_previous:
                    prev_default_key = f"{default_previous.label} (id={default_previous.id})"
                    prev_default_idx = prev_options.index(prev_default_key) if prev_default_key in prev_options else 0
                else:
                    prev_default_idx = 0

                with c2:
                    prev_key = st.selectbox(
                        "上季", prev_options,
                        index=prev_default_idx,
                        key=f"cp_prev_{lg.id}",
                    )
                curr_id = s_opts[curr_key]
                prev_id = s_opts[prev_key] if prev_key != "（無上季）" else None
                custom_pairs[lg.id] = (curr_id, prev_id)
        else:
            st.info("请先选择要执行的联赛")

    # ---------------------------------------------------------------------------
    # 就緒檢查：全域分組與隊伍配置
    # ---------------------------------------------------------------------------

    global_groups = store.list_global_groups()
    has_groups = len(global_groups) > 0

    # 逐個聯賽檢查隊伍配置
    configured_leagues: set[int] = set()
    missing_config_leagues: list = []
    for lg, _, _, _, _ in ready_leagues:
        if any(
            store.get_league_group_teams(lg.id, gg.id, "current")
            for gg in global_groups
        ):
            configured_leagues.add(lg.id)
        else:
            missing_config_leagues.append(lg)

    if not has_groups:
        st.warning("尚未建立任何全域分組。請先至「隊伍分組」頁面新增分組（如 Top、Weak）。")
    if has_groups and missing_config_leagues:
        names = "、".join(lg.name_zh or lg.code for lg in missing_config_leagues)
        st.warning(f"以下聯賽尚未配置分組隊伍：{names}。請使用下方按鈕自動配置，或至「隊伍分組」頁面手動設定。")

    # 快速配置按鈕：有分組 + 仍有聯賽缺配置時顯示
    show_quick_config = has_groups and len(missing_config_leagues) > 0

    # ETL 可執行條件：有分組 + 至少有一個聯賽已配置隊伍
    etl_ready = has_groups and len(configured_leagues) > 0

    if show_quick_config:
        if st.button("⚡ 快速配置（自動建立分組並分配全部隊伍）", type="secondary", key="btn_auto_setup"):
            with st.spinner("正在自動配置..."):
                if not has_groups:
                    for gn in ("Top", "Mid", "Weak"):
                        store.create_global_group(name=gn, display_name=None)
                    global_groups = store.list_global_groups()
                    has_groups = True

                from modules.data_connector import get_connector
                conn = get_connector()
                sa_leagues = {al['id']: al for al in conn.get_leagues(enabled=True)}

                for lg in missing_config_leagues:
                    # 从 league.code 提取 System A ID，如果失效则按名称查找
                    sa_id = int(lg.code.replace("LEAGUE_", ""))
                    if sa_id not in sa_leagues:
                        # ID 已过期，按 league.name_zh 在 System A 中查找
                        found = find_league_by_name_fuzzy(list(sa_leagues.values()), lg.name_zh)
                        if found:
                            sa_id = found['id']
                    sa_league = sa_leagues.get(sa_id)
                    if not sa_league:
                        continue
                    # 获取该联赛全部队伍，按分组数均分
                    try:
                        mr = conn.get_matches(league_id=sa_id, page=1, page_size=200)
                        all_matches = mr.get('matches') or mr.get('data') or []
                        all_teams = sorted(set(
                            t for m in all_matches
                            for t in (m.get('home_team'), m.get('away_team'))
                            if t
                        ))
                    except Exception:
                        all_teams = []

                    if all_teams:
                        chunk_size = max(1, len(all_teams) // len(global_groups))
                        for idx, gg in enumerate(global_groups):
                            start = idx * chunk_size
                            end = None if idx == len(global_groups) - 1 else (idx + 1) * chunk_size
                            chunk = all_teams[start:end]
                            store.set_league_group_teams(lg.id, gg.id, "current", chunk)
                            store.set_league_group_teams(lg.id, gg.id, "previous", chunk)

                configured_leagues = {
                    lg.id for lg, _, _, _, _ in ready_leagues
                    if any(
                        store.get_league_group_teams(lg.id, gg.id, "current")
                        for gg in global_groups
                    )
                }
                etl_ready = has_groups and len(configured_leagues) > 0
                st.success("✅ 自動配置完成，現在可以執行 ETL！")
                st.rerun()

    # ---------------------------------------------------------------------------
    # 執行 ETL
    # ---------------------------------------------------------------------------

    st.markdown("---")

    if st.button("▶️ 執行 ETL", type="primary", disabled=len(selected_ids) == 0 or not etl_ready):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def _progress(current: int, total: int, message: str):
            progress_bar.progress(current / total if total > 0 else 1.0)
            status_text.text(message)

        pipeline = ETLPipeline(store)
        season_pairs = custom_pairs if custom_pairs else None

        with st.spinner("ETL 執行中..."):
            run_id = pipeline.execute(
                league_ids=selected_ids,
                season_pairs=season_pairs,
                progress_callback=_progress,
            )

        progress_bar.progress(1.0)
        status_text.text("完成")

        # 顯示結果摘要
        st.success(f"ETL 執行完成（Run ID: {run_id}）")
        store.log_action("execute", "etl_run", run_id, f"leagues={selected_ids}")

        runs = store.list_etl_runs(limit=1)
        if runs:
            run = runs[0]
            st.json(run.get("summary", {}))

        # 品質問題
        issues = store.get_quality_issues(run_id)
        if issues:
            st.subheader("⚠️ 品質問題")
            for iss in issues:
                icon = "❌" if iss["severity"] == "error" else "⚠️"
                st.markdown(f"{icon} **{iss['issue_type']}**：{iss['description']}")

    # ---------------------------------------------------------------------------
    # 最近執行紀錄
    # ---------------------------------------------------------------------------

    st.markdown("---")
    st.subheader("📋 最近執行紀錄")

    recent_runs = store.list_etl_runs(limit=5)
    if recent_runs:
        for run in recent_runs:
            status_icon = {"completed": "✅", "failed": "❌", "running": "⏳"}.get(
                run["status"], "❓"
            )
            st.markdown(
                f"{status_icon} **Run #{run['id']}** — {run['started_at']} → "
                f"{run.get('completed_at', '進行中')} — {run['status']}"
            )
    else:
        st.info("尚無執行紀錄。")


if __name__ == "__main__":
    render()
