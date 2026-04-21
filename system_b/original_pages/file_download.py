"""檔案下載頁面

功能：
- 第一步：同步选中的比赛或者一键同步所有比赛
- 第二步：下载选中的比赛档案或者一键下载同步过的比赛档案（剔除已下载且没有更新的）
- 第三步：ETL执行，先计算X值，后续流程不变
"""

import streamlit as st
import logging
from typing import List, Dict, Any
from datetime import datetime

from app import get_store
from modules.data_connector import get_connector
from modules.x_calculator import XValueCalculator
from modules.follow_list import get_follow_manager


logger = logging.getLogger(__name__)


def _sync_league_to_system_b(store, connector, league_data: Dict) -> int:
    """将系统A的联赛同步到系统B"""
    # 映射大陆到系统B的格式
    continent_map = {
        "国际": "",
        "欧洲": "EUR",
        "美洲": "AME",
        "亚洲": "ASI",
        "大洋洲": "",
        "非洲": "AFR"
    }

    continent = continent_map.get(league_data.get('country', ''), '')

    # 获取联赛名称，确保不为空
    league_name = league_data.get('league_name_tw', '')
    if not league_name or league_name.strip() == '':
        league_name = league_data.get('league_name_zh', '')

    if not league_name or league_name.strip() == '':
        # 如果都为空，生成一个默认名称
        league_name = f"未命名联赛_{league_data.get('id', 'unknown')}"
        logger.warning(f"联赛ID {league_data.get('id')} 名称为空，使用默认名称: {league_name}")
    else:
        league_name = league_name.strip()

    # 创建或更新联赛
    existing_league = store.find_league_by_identity(
        league_name,
        None
    )

    if existing_league:
        league_id = existing_league.id
        # 如果现有联赛名字为空，更新为正确的名称
        if not existing_league.name_zh or existing_league.name_zh.strip() == "":
            store.update_league(league_id, name_zh=league_name)
    else:
        league_id = store.create_league(
            continent=continent,
            code=f"LEAGUE_{league_data['id']}",
            name_zh=league_name,
            league_url_id=str(league_data.get('league_id', '')),
        )

    return league_id


def _sync_season_to_system_b(store, league_id: int, season_label: str) -> int:
    """将系统A的赛季同步到系统B"""
    seasons = store.list_season_instances(league_id)

    # 查找是否已存在
    existing_season = None
    for s in seasons:
        if s.label == season_label:
            existing_season = s
            break

    if existing_season:
        return existing_season.id

    # 解析赛季年份
    year_start = 2024
    if "-" in season_label:
        try:
            year_start = int(season_label.split("-")[0])
        except:
            pass

    season_id = store.create_season_instance(
        league_id=league_id,
        label=season_label,
        year_start=year_start,
        year_end=year_start + 1
    )

    # 设置为current赛季
    store.set_season_role(season_id, "current")

    return season_id


def render():
    st.title("📥 檔案下載")
    st.caption("三步流程：同步比赛 → 关注管理 → 下载赔率 → 计算X值")

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
        try:
            # 获取已同步的联赛列表
            all_leagues = connector.get_leagues(enabled=True)
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
                    if st.button("➕ 添加到关注名单"):
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

    st.divider()

    # ============ 下载赔率 ============
    st.subheader("下载赔率")

    # 显示关注名单统计
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
        if st.button("🚀 一键下载所有关注赔率", type="primary"):
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

    else:
        st.warning("請先添加聯賽賽季到關注名單")

    # ============ 计算X值 ============
    st.divider()
    st.subheader("计算X值")

    if following:
        if st.button("📊 一键计算所有X值并导入", type="primary"):
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
                                        league_id_b = _sync_league_to_system_b(store, connector, {
                                            'id': match_data['league_id'],
                                            'league_name_tw': match_data.get('league_name', ''),
                                            'country': '',
                                            'league_id': match_data['league_id']
                                        })

                                        # 同步赛季到系统B
                                        season_id_b = _sync_season_to_system_b(store, league_id_b, match_data.get('season', '2024-2025'))

                                        # 创建MatchRecord
                                        from etl.models import MatchRecord
                                        from etl.settlement import SettlementCalculator

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
                                        traceback.print_exc()

                            progress_bar.progress(min((i+batch_size)/len(all_completed), 1.0))

                        st.success(f"✅ 成功计算 {success_count} 场比赛的X值，导入 {imported_count} 条记录到系统B")
                    else:
                        st.info("没有找到已完成赔率爬取的比赛，请先完成第二步")

                except Exception as e:
                    st.error(f"计算X值失败: {e}")
                    import traceback
                    traceback.print_exc()
    else:
        st.warning("請先添加聯賽賽季到關注名單")

    # ============ 状态显示 ============
    st.divider()
    st.subheader("📋 进度查看")

    st.info("提示：")
    st.markdown("- 如需查看详细任务进度，请访问「任务列表」页面")
    st.markdown("- 如需查看数据质量，请访问「数据验证」页面")
    st.markdown("- 完成前三步后，可前往「ETL执行」页面运行完整流程")


if __name__ == "__main__":
    render()