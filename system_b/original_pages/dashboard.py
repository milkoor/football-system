"""报表看板页面"""

import streamlit as st

st.title("📊 报表看板")

st.info("此页面需要先完成数据同步和 X 值计算")

# 侧边栏筛选
with st.sidebar:
    st.subheader("筛选条件")

    # 全局分组
    group_filter = st.selectbox(
        "分组",
        ["全部", "Top", "Weak", "中游"]
    )

    # 玩法类型
    play_type = st.selectbox(
        "玩法",
        ["全部", "HDP（让球）", "OU（大小）"]
    )

    # 时段
    timing = st.selectbox(
        "时段",
        ["全部", "Early（早盘）", "RT（即时）"]
    )

    # 联赛多选
    league_filter = st.multiselect(
        "联赛",
        ["英超", "西甲", "意甲", "德甲", "法甲", "日职联", "中超"]
    )

# 示例数据展示（实际需要从 ETL 结果获取）
st.subheader("📈 信号汇总")

# 模拟数据表格
import pandas as pd

sample_data = {
    "联赛": ["英超", "英超", "西甲", "意甲", "德甲"],
    "分组": ["Top", "Weak", "Top", "中游", "Top"],
    "玩法": ["HDP", "HDP", "OU", "HDP", "OU"],
    "时段": ["Early", "Early", "RT", "Early", "Early"],
    "Home信号": ["A2", "B0.5", "", "A1", "B2"],
    "Away信号": ["B0.5", "A2", "A0.2", "", ""],
    "更新时间": ["2026-04-12", "2026-04-12", "2026-04-11", "2026-04-11", "2026-04-10"]
}

df = pd.DataFrame(sample_data)

# 筛选
if group_filter != "全部":
    df = df[df["分组"] == group_filter]

if play_type != "全部":
    pt = "HDP" if "HDP" in play_type else "OU"
    df = df[df["玩法"] == pt]

if timing != "全部":
    tm = "Early" if "Early" in timing else "RT"
    df = df[df["时段"] == tm]

if league_filter:
    df = df[df["联赛"].isin(league_filter)]

st.dataframe(df, use_container_width=True)

# 分组展示
st.subheader("📋 按分组查看")

tab1, tab2, tab3 = st.tabs(["Top 队伍", "Weak 队伍", "中游队伍"])

with tab1:
    st.write("**Top 队伍信号**")
    st.dataframe(df[df["分组"] == "Top"], use_container_width=True)

with tab2:
    st.write("**Weak 队伍信号**")
    st.dataframe(df[df["分组"] == "Weak"], use_container_width=True)

with tab3:
    st.write("**中游队伍信号**")
    st.dataframe(df[df["分组"] == "中游"], use_container_width=True)

# 信号说明
st.divider()
st.caption("""
**信号说明**:
- 字母（A/B）表示方向：A=上季优势方向，B=上季劣势方向
- 数值表示强度：2=强，1=中等，0.5=弱，0.2=很弱
- 空值表示无信号
""")