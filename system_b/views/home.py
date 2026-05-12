"""首页"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def render():
    st.title("🏠 欢迎使用足球数据分析系统")

    st.markdown("""
    ### 系统介绍
    这是一个完整的足球数据分析平台，提供以下功能：

    - **数据同步**：从系统 A 同步比赛和赔率数据
    - **X值计算**：基于盘口变动计算X值
    - **量化分析**：实现完整的ETL流程和信号生成
    - **信号追踪**：分析不同版本的决策信号
    - **数据可视化**：提供报表看板和历史记录

    ### 快速开始
    1. 进入「数据准备」分组，完成系统同步
    2. 在「关注管理」中添加需要分析的联赛/赛季
    3. 运行ETL流程进行数据分析
    4. 查看「报表看板」获取决策信号
    """)

    try:
        from modules.data_connector import get_connector
        connector = get_connector()
        leagues = connector.get_leagues(enabled=True)
        st.metric("活跃联赛数量", len(leagues))

        total_matches = 0
        for league in leagues:
            matches = connector.get_matches(league_id=league['id'])
            if 'total' in matches:
                total_matches += matches['total']

        st.metric("总比赛数量", total_matches)
    except Exception as e:
        st.warning(f"无法获取系统状态: {e}")


if __name__ == "__main__":
    render()
