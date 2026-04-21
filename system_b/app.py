"""系统 B：Streamlit 应用入口"""
import streamlit as st
import sys
import os

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from pathlib import Path

from etl.config_store import get_store
from etl.pipeline import ETLPipeline

# 配置页面设置
st.set_page_config(
    page_title="足球数据分析系统",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局状态管理
if 'initialized' not in st.session_state:
    st.session_state.initialized = False


def init_app():
    """初始化应用程序"""
    st.session_state.initialized = True
    logger.info("应用程序初始化完成")


def main():
    """主应用程序入口"""
    if not st.session_state.initialized:
        init_app()

    # 侧边栏导航
    st.sidebar.title("🏆 足球数据分析系统")
    st.sidebar.markdown("---")

    pages = [
        ("🏠 首页", "home"),
        ("📥 档案下载", "file_download"),
        ("🚀 ETL 执行", "etl_exec"),
        ("⚙️ 系统设置", "settings"),
        ("📊 数据验证", "data_validation"),
        ("🔍 历史记录", "history"),
        ("👥 关注管理", "follow_list"),
        ("🎯 数据筛选", "data_filtering"),
        ("📈 信号追踪", "signal_tracking"),
        ("🏅 队伍分组", "team_grouping"),
        ("📝 数据库管理", "database_management")
    ]

    selection = st.sidebar.radio("导航菜单", [p[0] for p in pages])

    # 加载对应的页面
    selected_page = [p[1] for p in pages if p[0] == selection][0]

    if selected_page == "home":
        show_home_page()
    else:
        show_page(selected_page)


def show_home_page():
    """显示首页"""
    st.title("⚽ 足球数据分析系统")
    st.caption("智能量化分析平台")

    st.markdown("---")

    st.subheader("系统介绍")
    st.markdown("""
    本系统提供完整的足球数据处理和分析功能，包括：

    - **数据同步**：从多个数据源同步比赛和赔率数据
    - **智能计算**：自动计算X值和结算结果
    - **量化分析**：实现五大区间、轮次块、强度等分析
    - **信号生成**：基于历史数据生成投资信号
    - **数据可视化**：提供丰富的图表和报表
    """)

    st.markdown("---")

    st.subheader("系统状态")
    store = get_store()

    try:
        leagues = store.list_leagues(active_only=True)
        seasons = []
        for lg in leagues:
            seasons.extend(store.list_season_instances(lg.id))

        st.metric("活跃联赛", len(leagues))
        st.metric("活跃赛季", len(seasons))

        match_count = 0
        for season in seasons:
            match_count += len(store.get_match_records(season.id))
        st.metric("比赛记录", match_count)

    except Exception as e:
        st.error(f"获取系统状态失败: {e}")


def show_page(page_name: str):
    """显示指定页面"""
    try:
        page_module = __import__(f"app_pages.{page_name}", fromlist=["render"])
        page_module.render()
    except ImportError:
        try:
            # 尝试从original_pages中加载
            page_module = __import__(f"original_pages.{page_name}", fromlist=["render"])
            page_module.render()
        except ImportError as e:
            st.error(f"页面 {page_name} 未找到: {e}")
    except Exception as e:
        logger.error(f"页面加载失败: {e}", exc_info=True)
        st.error(f"页面加载失败: {e}")


if __name__ == "__main__":
    main()
