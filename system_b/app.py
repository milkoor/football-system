"""系统 B：Streamlit 应用入口"""
import streamlit as st
# 必须在任何其他Streamlit命令之前调用
st.set_page_config(
    page_title="足球数据分析系统",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

import sys
import os

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局状态管理
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    logger.info("应用程序初始化完成")

# 定义所有页面（使用包装文件）
page_home = st.Page("views/home.py", title="首页", icon="🏠")

# 数据准备分组
page_system_sync = st.Page("views/system_sync.py", title="系统同步", icon="🔄")
page_data_import = st.Page("views/data_importer.py", title="数据导入", icon="📥")
page_league_mgmt = st.Page("views/league_management.py", title="联赛管理", icon="🏆")
page_team_groups = st.Page("views/team_grouping.py", title="队伍分组", icon="👥")
page_file_upload = st.Page("views/file_upload.py", title="檔案上傳", icon="📄")
page_file_download = st.Page("views/file_download.py", title="檔案下載", icon="📥")

# 数据分析分组
page_params = st.Page("views/settings.py", title="参数设定", icon="⚙️")
page_etl = st.Page("views/etl_exec.py", title="ETL执行", icon="▶️")

# 结果输出分组
page_report = st.Page("views/dashboard.py", title="报表看板", icon="📊")
page_history = st.Page("views/history.py", title="历史纪录", icon="📜")

# 运维分组
page_tasks = st.Page("views/task_list.py", title="任务列表", icon="📋")
page_validation = st.Page("views/data_validation.py", title="数据验证", icon="✅")
page_db_mgmt = st.Page("views/database_management.py", title="数据库管理", icon="🗄️")

# 定义分组导航 - 移除信号追踪页面，因为功能已整合到其他页面
pg = st.navigation({
    "🏠 首页": [page_home],
    "📊 数据准备": [page_system_sync, page_data_import, page_league_mgmt, page_team_groups, page_file_upload],
    "📥 文件管理": [page_file_download],
    "🔧 数据分析": [page_params, page_etl],
    "📈 结果输出": [page_report, page_history],
    "🖥️ 运维": [page_tasks, page_validation, page_db_mgmt]
})

# 运行导航
pg.run()
