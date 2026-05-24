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
import re
from typing import List, Dict, Any
from datetime import datetime

from core.config_store import get_store
from modules.data_connector import get_connector
from modules.follow_list import get_follow_manager
from utils.system_a_mapper import get_league_display_name


logger = logging.getLogger(__name__)


def _resolve_follow_list(follow_manager, connector):
    """解析关注列表，将过期的数据库ID替换为当前ID"""
    items = follow_manager.get_all()

    for item in items:
        lid = item.get("league_id")
        # 验证 ID 是否存在（查联赛详情，非查比赛）
        try:
            leagues_all = connector.get_leagues(enabled=True)
            valid = any(lg.get('id') == lid for lg in leagues_all)
            if valid:
                continue  # ID 有效
        except:
            pass

        # ID 失效，按名称重新查找
        name = item.get("league_name", "")
        parts = name.split(" - ", 1)
        search_name = parts[-1] if len(parts) > 1 else name

        from utils.system_a_mapper import find_league_by_name_fuzzy
        found = find_league_by_name_fuzzy(leagues_all, search_name)

        if found:
            old_id = item["league_id"]
            item["league_id"] = found["id"]
            follow_manager.remove(old_id)
            follow_manager.add(
                league_id=found["id"],
                league_name=name,
                country=item.get("country", ""),
            )
            logger.warning(f"已修复过期的关注联赛ID: {old_id} -> {found['id']} ({found.get('league_name_tw', '')})")
        else:
            # 找不到对应的联赛，删除失效的关注
            follow_manager.remove(lid)
            logger.warning(f"已删除失效的关注联赛: {name} (ID: {lid})，请重新添加")

    return follow_manager.get_all()


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
    follow_manager = get_follow_manager()

    # 解析关注列表，修复过期的数据库ID（数据库重建后自增ID会变）
    _resolve_follow_list(follow_manager, connector)

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
                    f"{l.get('country', '')} - {get_league_display_name(l)}": l
                    for l in all_leagues
                }

                selected_league_name = st.selectbox(
                    "选择联赛",
                    ["請選擇聯賽"] + list(league_options.keys()),
                    index=0
                )

                selected_league = None

                if selected_league_name and selected_league_name != "請選擇聯賽":
                    selected_league = league_options[selected_league_name]

                if selected_league:
                    if st.button("➕ 添加到关注名单", type="primary"):
                        success = follow_manager.add(
                            league_id=selected_league['id'],
                            league_name=selected_league_name,
                            country=selected_league.get('country', '')
                        )

                        if success:
                            st.success(f"✅ 已添加到关注名单：{selected_league_name}")
                        else:
                            st.warning(f"⚠️ 已在关注名单中：{selected_league_name}")

                        st.rerun()
            else:
                st.info("請先到系統同步頁面同步聯賽和賽季")

        except Exception as e:
            st.error(f"獲取數據失敗: {e}")

    with col2:
        st.caption("管理关注名单")
        following = follow_manager.get_all()
        if following:
            st.write(f"关注名单（{len(following)}个联赛）：")
            with st.expander("查看和管理关注名单"):
                for item in following:
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.write(f"{item.get('country', '')} - {item.get('league_name')}")
                        # 显示已同步的赛季
                        seasons = item.get('seasons', [])
                        if seasons:
                            st.caption(f"已同步赛季: {', '.join(seasons)}")
                    with col_b:
                        if st.button("分组映射", key=f"map_{item['league_id']}"):
                            st.session_state[f"show_mapping_{item['league_id']}"] = not st.session_state.get(f"show_mapping_{item['league_id']}", False)
                    with col_c:
                        if st.button("删除", key=f"del_{item['league_id']}"):
                            follow_manager.remove(item['league_id'])
                            st.success(f"✅ 删除成功")
                            st.rerun()

                    # 分组映射配置面板
                    if st.session_state.get(f"show_mapping_{item['league_id']}", False):
                        st.info("⚙️ 赛季分组映射配置（将当前赛季组别对应到上赛季组别）")
                        league_id = item['league_id']
                        mapping = item.get('group_mapping', {})

                        # 组别信息（从同步时写入的 season_groups 读取，避免实时调用 titan007）
                        season_groups = item.get('season_groups', {})
                        current_groups = {}
                        previous_groups = {}

                        # 获取该联赛的赛季列表
                        seasons = fetch_seasons(connector, league_id)
                        if len(seasons) < 2:
                            st.warning("⚠️ 该联赛不足2个赛季，无法进行分组匹配")
                        else:
                            # 取最近2个赛季
                            current_season = seasons[0]['season_label']
                            previous_season = seasons[1]['season_label']

                            st.write(f"当前赛季: {current_season}")
                            st.write(f"上一赛季: {previous_season}")

                            # 从存储读取组别信息，如有缺失则实时获取
                            from utils.system_a_mapper import get_season_groups, auto_match_groups

                            current_groups = season_groups.get(current_season, {})
                            previous_groups = season_groups.get(previous_season, {})

                            if not current_groups or not previous_groups:
                                with st.spinner("加载组别信息..."):
                                    if not current_groups:
                                        current_groups = get_season_groups(connector, league_id, current_season)
                                    if not previous_groups:
                                        previous_groups = get_season_groups(connector, league_id, previous_season)
                                # 回写到存储
                                if current_groups or previous_groups:
                                    season_groups.update({current_season: current_groups, previous_season: previous_groups})
                                    follow_manager.update_season_groups(league_id, season_groups)

                            # 刷新按钮（手动重新获取）
                            if st.button("🔄 刷新分组", key=f"refresh_groups_{league_id}"):
                                with st.spinner("刷新组别信息..."):
                                    current_groups = get_season_groups(connector, league_id, current_season)
                                    previous_groups = get_season_groups(connector, league_id, previous_season)
                                    season_groups = {current_season: current_groups, previous_season: previous_groups}
                                    follow_manager.update_season_groups(league_id, season_groups)
                                st.rerun()

                            # 自动匹配按钮
                            if st.button("🤖 自动匹配", key=f"auto_match_{league_id}"):
                                auto_mapping = auto_match_groups(current_groups, previous_groups)
                                # 合并到现有映射，不覆盖已有
                                for cur, prev in auto_mapping.items():
                                    if cur not in mapping:
                                        mapping[cur] = prev
                                follow_manager.update_group_mapping(league_id, mapping)
                                st.success("✅ 自动匹配完成")
                                st.rerun()

                            # 添加新映射
                            st.subheader("添加映射")
                            col_group1, col_group2 = st.columns([1,1])
                            with col_group1:
                                # 当前赛季组别下拉
                                current_options = [f"{k} ({v})" for k, v in current_groups.items()]
                                current_selected = st.selectbox("当前赛季组别", ["请选择"] + current_options, key=f"cur_group_{league_id}")
                            with col_group2:
                                # 上赛季组别下拉
                                previous_options = [f"{k} ({v})" for k, v in previous_groups.items()]
                                previous_selected = st.selectbox("对应上赛季组别", ["请选择"] + previous_options, key=f"tar_group_{league_id}")

                            if st.button("➕ 添加映射", key=f"add_map_{league_id}"):
                                if current_selected != "请选择" and previous_selected != "请选择":
                                    # 提取group_id
                                    current_group_id = current_selected.split(" ")[0]
                                    previous_group_id = previous_selected.split(" ")[0]
                                    mapping[current_group_id] = previous_group_id
                                    follow_manager.update_group_mapping(league_id, mapping)
                                    st.success(f"✅ 已添加映射: {current_selected} → {previous_selected}")
                                    st.rerun()

                        # 显示已有映射
                        if mapping:
                            st.subheader("已配置的映射")
                            for cur, tar in mapping.items():
                                col_map1, col_map2, col_map3 = st.columns([2,2,1])
                                # 显示名称，如果有的话
                                cur_display = f"{cur} ({current_groups.get(cur, '')})" if cur in current_groups else cur
                                tar_display = f"{tar} ({previous_groups.get(tar, '')})" if tar in previous_groups else tar
                                col_map1.write(cur_display)
                                col_map2.write(f"→ {tar_display}")
                                if col_map3.button("删除", key=f"del_map_{league_id}_{cur}"):
                                    del mapping[cur]
                                    follow_manager.update_group_mapping(league_id, mapping)
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
    if "sync_errors" not in st.session_state:
        st.session_state.sync_errors = []

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

        # ---- 错误信息显示 ----
        if st.session_state.sync_errors:
            st.error("❌ 同步过程中出现以下错误:")
            for err in st.session_state.sync_errors:
                st.write(f"- {err}")

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
                    st.session_state.sync_errors = []
                    st.rerun()
            with col_b:
                if st.button("📥 仅导入到系统B", type="secondary", key="btn_import_only", disabled=busy):
                    st.session_state.sync_step = 'xcalc'
                    st.session_state.sync_busy = True
                    st.session_state.sync_errors = []
                    st.rerun()

        elif step == 'sync':
            pending_jobs = []
            st.session_state.sync_errors = []
            st.session_state.sync_league_seasons = {}  # 存储每个联赛同步的赛季

            for item in following:
                try:
                    league_id = item['league_id']
                    league_name = item['league_name']

                    # 获取该联赛的所有赛季，取最近2个
                    seasons = connector.get_seasons(league_id)
                    if not seasons:
                        st.warning(f"⚠️ {league_name} 没有找到可用赛季，跳过")
                        continue

                    # 赛季通常按时间倒序排列，取前2个（本赛季+上赛季）
                    recent_seasons = [s['season_label'] for s in seasons[:2]]
                    st.info(f"ℹ️ {league_name} 同步最近2个赛季: {', '.join(recent_seasons)}")

                    # 存储赛季信息，后续同步完成后更新到关注列表
                    st.session_state.sync_league_seasons[league_id] = recent_seasons

                    # 逐个触发赛季同步
                    for season in recent_seasons:
                        try:
                            result = connector.sync_seasons_for_league(league_id, season)
                            jid = result.get('job_id')
                            if jid:
                                pending_jobs.append(jid)
                                st.success(f"{league_name} {season} 同步触发成功: job_id={jid}")
                        except Exception as e:
                            error_msg = f"{league_name} {season} 同步触发失败: {str(e)}"
                            st.session_state.sync_errors.append(error_msg)
                            st.error(error_msg)

                except Exception as e:
                    error_msg = f"{item['league_name']} 获取赛季列表失败: {str(e)}"
                    st.session_state.sync_errors.append(error_msg)
                    st.error(error_msg)

            if pending_jobs:
                st.session_state.sync_pending = pending_jobs
                st.session_state.sync_step = 'poll_sync'
                time.sleep(2)  # 给用户看信息的时间
                st.rerun()
            else:
                st.error("❌ 所有赛季同步触发都失败了，请检查错误信息")
                st.session_state.sync_step = None
                st.session_state.sync_busy = False
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

                # 将同步成功的赛季更新到关注列表，并获取赛季分组信息
                if 'sync_league_seasons' in st.session_state:
                    from utils.system_a_mapper import get_season_groups
                    for league_id, seasons in st.session_state.sync_league_seasons.items():
                        follow_manager.update_seasons(league_id, seasons)
                        # 同步各赛季分组信息（写入 follow_list 供分组映射面板读取）
                        season_groups = {}
                        for s in seasons:
                            try:
                                groups = get_season_groups(connector, league_id, s)
                                if groups:
                                    season_groups[s] = groups
                            except Exception:
                                pass
                        if season_groups:
                            follow_manager.update_season_groups(league_id, season_groups)
                    del st.session_state.sync_league_seasons

                st.session_state.sync_step = 'crawl'
                st.rerun()

        elif step == 'crawl':
            crawl_jobs = []
            st.session_state.sync_errors = []
            for item in following:
                try:
                    league_id = item['league_id']
                    league_name = item['league_name']
                    seasons = item.get('seasons', [])

                    if not seasons:
                        st.warning(f"⚠️ {league_name} 没有可爬取的赛季，请先同步赛程")
                        continue

                    # 对每个赛季触发爬取
                    for season in seasons:
                        try:
                            result = connector.trigger_crawl(league_id, season)
                            jid = result.get('job_id')
                            if jid:
                                crawl_jobs.append(jid)
                                st.success(f"{league_name} {season} 爬取触发成功: job_id={jid}")
                        except Exception as e:
                            error_msg = f"{league_name} {season} 爬取触发失败: {str(e)}"
                            st.session_state.sync_errors.append(error_msg)
                            st.error(error_msg)

                except Exception as e:
                    error_msg = f"{item['league_name']} 爬取触发失败: {str(e)}"
                    st.session_state.sync_errors.append(error_msg)
                    st.error(error_msg)
            if crawl_jobs:
                st.session_state.crawl_pending = crawl_jobs
                st.session_state.sync_step = 'poll_crawl'
                time.sleep(2)  # 给用户看错误信息的时间
                st.rerun()
            else:
                st.error("❌ 所有赛季爬取触发都失败了，请检查错误信息")
                st.session_state.sync_step = None
                st.session_state.sync_busy = False
                st.rerun()

        elif step == 'poll_crawl':
            total_task = 0
            done_task = 0
            remaining = []
            failed_jobs = []

            for jid in st.session_state.get('crawl_pending', []):
                try:
                    job = connector.get_crawl_job(jid)
                    if job:
                        s = job.get('status')
                        if s == 'failed':
                            failed_jobs.append(jid)
                            error_msg = job.get('error_message', '未知错误')
                            st.error(f"❌ 爬取任务 {jid} 失败: {error_msg}")
                        elif s in ('running', 'pending', None):
                            remaining.append(jid)
                        # 统计进度
                        total_task += job.get('total_matches', 0)
                        done_task += job.get('completed_matches', 0) + job.get('failed_matches', 0)
                except Exception as e:
                    logger.error(f"获取任务 {jid} 状态失败: {e}")
                    remaining.append(jid)

            # 移除失败的任务
            for jid in failed_jobs:
                st.session_state.crawl_pending.remove(jid)

            if total_task > 0:
                progress = min(done_task / total_task, 1.0)
                st.progress(progress, text=f"已处理 {done_task}/{total_task} 场比赛")
                # 显示进度百分比
                st.caption(f"进度: {progress:.1%}")
            else:
                st.progress(0.5, text="等待爬虫开始...")

            col_skip, _ = st.columns([1, 3])
            with col_skip:
                skip = st.button("⏭️ 先看结果, 稍后继续爬", key="btn_skip_crawl")

            # 如果还有剩余任务，并且没有点击跳过，继续等待
            if remaining and not skip:
                time.sleep(3)  # 缩短轮询间隔，更及时更新进度
                st.rerun()
            else:
                if not remaining:
                    st.success(f"✅ 赔率爬取完成! 共成功 {done_task} 场, 失败 {total_task - done_task} 场")
                else:
                    st.info("⏭️ 已跳过爬虫等待，可稍后重新执行爬取")
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

            if all_completed or all_pending:
                from utils.system_a_mapper import import_matches_to_system_b

                # 合并已完成+待爬取比赛，让导入函数统一处理
                # 待爬取比赛没有赔率数据，X值会默认为0
                all_matches = all_completed + all_pending

                prog = st.progress(0)

                def _update_prog(done, total):
                    prog.progress(min(done / total, 1.0))

                result = import_matches_to_system_b(
                    store, connector, all_matches,
                    progress_callback=_update_prog,
                )
                success = result['x_success']
                imported = result['imported']

                st.success(f"🎉 完整同步完成！计算 {success} 条X值，导入 {imported} 条记录到系统B")
                st.info("💡 接下来请点击「运行ETL」生成报表，然后前往「报表看板」查看决策信号。")
            else:
                st.warning("暂无数据可导入。")

            st.session_state.sync_step = 'done'
            st.session_state.sync_busy = False
            st.rerun()

        else:  # done
            st.success("✅ 处理完成，可再次点击按钮执行新的同步。")
            if st.button("🔄 再来一次", key="btn_reset_sync"):
                st.session_state.sync_step = None
                st.session_state.sync_busy = False
                st.session_state.sync_errors = []
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


if __name__ == "__main__":
    render()
