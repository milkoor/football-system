"""系统 B：Streamlit 应用入口"""
import streamlit as st
st.set_page_config(
    page_title="足球数据分析系统",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if 'initialized' not in st.session_state:
    st.session_state.initialized = True

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 初始化自动同步调度器（在 Docker 和非 Docker 环境下都运行）
try:
    from modules.auto_sync import SyncScheduler
    from modules.data_connector import get_connector
    from modules.follow_list import get_follow_manager
    from config.settings import get_settings

    if "auto_scheduler" not in st.session_state:
        from core.config_store import get_store
        sched = SyncScheduler(
            connector=get_connector(),
            follow_manager=get_follow_manager(),
            settings=get_settings(),
            store=get_store(),
        )
        st.session_state.auto_scheduler = sched
        logger = logging.getLogger(__name__)
        logger.info("自动同步调度器已启动" if sched.get_scheduler() else "自动同步功能已禁用")
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.error(f"初始化自动同步调度器失败: {str(e)}")

# ---------------------------------------------------------------------------
# 页面定义（使用可调用函数，避免 Streamlit 文件路径→URL 推断问题）
# ---------------------------------------------------------------------------

def _page(name, module):
    """生成页面渲染函数"""
    def _render():
        from importlib import import_module
        mod = import_module(module)
        mod.render()
    _render.__name__ = name
    return _render

page_home = st.Page(_page("home", "views.home"), title="首页", icon="🏠", url_path="home")
page_system_sync = st.Page(_page("system_sync", "views.system_sync"), title="系统同步", icon="🔄", url_path="system_sync")
page_data_import = st.Page(_page("data_import", "views.data_importer"), title="数据导入", icon="📥", url_path="data_importer")
page_league_mgmt = st.Page(_page("league_mgmt", "views.league_management"), title="联赛管理", icon="🏆", url_path="league_management")
page_team_groups = st.Page(_page("team_groups", "views.team_grouping"), title="队伍分组", icon="👥", url_path="team_grouping")
page_file_upload = st.Page(_page("file_upload", "views.file_upload"), title="檔案上傳", icon="📄", url_path="file_upload")
page_params = st.Page(_page("settings", "views.settings"), title="参数设定", icon="⚙️", url_path="settings")
page_etl = st.Page(_page("etl_exec", "views.etl_exec"), title="ETL执行", icon="▶️", url_path="etl_exec")
page_report = st.Page(_page("dashboard", "views.dashboard"), title="报表看板", icon="📊", url_path="dashboard")
page_history = st.Page(_page("history", "views.history"), title="历史纪录", icon="📜", url_path="history")
page_tasks = st.Page(_page("task_list", "views.task_list"), title="任务列表", icon="📋", url_path="task_list")
page_validation = st.Page(_page("data_validation", "views.data_validation"), title="数据验证", icon="✅", url_path="data_validation")
page_db_mgmt = st.Page(_page("database_mgmt", "views.database_management"), title="数据库管理", icon="🗄️", url_path="database_management")

pg = st.navigation({
    "🏠 首页": [page_home],
    "📊 数据准备": [page_system_sync, page_data_import, page_league_mgmt, page_team_groups, page_file_upload],
    "🔧 数据分析": [page_params, page_etl],
    "📈 结果输出": [page_report, page_history],
    "🖥️ 运维": [page_tasks, page_validation, page_db_mgmt]
})

pg.run()
