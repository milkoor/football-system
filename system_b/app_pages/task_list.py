"""任务列表页面

功能：
- 显示爬虫任务列表
- 查看任务详情和状态
- 停止正在运行的任务
- 任务状态实时更新
"""

import streamlit as st
import time
import logging

from etl.config_store import get_store
from modules.data_connector import get_connector


logger = logging.getLogger(__name__)


def render():
    st.title("📋 任务列表")
    st.caption("查看和管理爬虫任务状态")

    # 初始化
    store = get_store()
    connector = get_connector()

    # ============ 任务筛选 ============
    st.subheader("任务筛选")
    col1, col2 = st.columns(2)

    with col1:
        status_filter = st.selectbox(
            "状态筛选",
            ["全部", "待运行", "运行中", "已完成", "失败", "已取消"],
            index=0
        )
        # 映射中文状态到英文状态
        status_map = {
            "待运行": "pending",
            "运行中": "running",
            "已完成": "completed",
            "失败": "failed",
            "已取消": "cancelled"
        }
        status = status_map.get(status_filter) if status_filter != "全部" else None

    with col2:
        limit = st.slider("显示数量", min_value=10, max_value=100, value=20)

    # ============ 任务列表 ============
    st.subheader("任务列表")

    try:
        jobs = connector.get_crawl_jobs(status=status, limit=limit)

        if not jobs:
            st.info("暂无爬虫任务")
        else:
            # 创建表格显示任务列表
            job_data = []
            for job in jobs:
                job_data.append({
                    "任务ID": job.get("job_id"),
                    "类型": "联赛同步" if job.get("league_id") else "单场同步" if job.get("match_ids") else "未知",
                    "联赛ID": job.get("league_id"),
                    "赛季": job.get("season_label"),
                    "状态": job.get("status"),
                    "开始时间": job.get("started_at"),
                    "结束时间": job.get("completed_at"),
                    "总比赛数": job.get("total_matches"),
                    "完成数": job.get("completed_matches"),
                    "失败数": job.get("failed_matches"),
                    "错误信息": job.get("error_message")
                })

            # 显示任务列表
            st.dataframe(job_data)

            # ============ 任务详情 ============
            st.subheader("任务详情")
            selected_job_id = st.selectbox(
                "选择任务查看详情",
                [job.get("job_id") for job in jobs]
            )

            selected_job = None
            for job in jobs:
                if job.get("job_id") == selected_job_id:
                    selected_job = job
                    break

            if selected_job:
                # 任务基本信息
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("任务状态", selected_job.get("status"))
                with col2:
                    st.metric("总比赛数", selected_job.get("total_matches"))
                with col3:
                    st.metric("完成数", selected_job.get("completed_matches"))
                with col4:
                    st.metric("失败数", selected_job.get("failed_matches"))

                # 任务详细信息
                st.write("**任务详细信息**")
                st.json(selected_job, expanded=True)

                # 停止任务按钮
                if selected_job.get("status") in ["pending", "running"]:
                    if st.button("停止任务", type="secondary"):
                        try:
                            connector.stop_crawl_job(selected_job.get("id"))
                            st.success("任务已停止")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"停止任务失败: {e}")

    except Exception as e:
        st.error(f"获取任务列表失败: {e}")
        logger.error(f"获取任务列表失败: {e}")