"""信号追踪页面"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.title("🔍 信号追踪")

st.info("追踪信号变化，比较不同版本的决策结果")

# 选择联赛
with st.sidebar:
    st.subheader("追踪条件")
    selected_league = st.selectbox(
        "联赛",
        ["英超", "西甲", "意甲", "德甲", "法甲", "日职联"]
    )

    selected_group = st.selectbox(
        "分组",
        ["Top", "Weak", "中游"]
    )

# 版本选择
col1, col2 = st.columns(2)

with col1:
    st.subheader("版本 A")
    version_a_date = st.date_input(
        "版本 A 日期",
        value=datetime.now() - timedelta(days=7)
    )

with col2:
    st.subheader("版本 B")
    version_b_date = st.date_input(
        "版本 B 日期",
        value=datetime.now()
    )

# 模拟数据
st.subheader("📊 信号对比")

sample_a = {
    "联赛": [selected_league] * 5,
    "分组": [selected_group] * 5,
    "队伍": ["队伍A", "队伍B", "队伍C", "队伍D", "队伍E"],
    "玩法": ["HDP", "HDP", "OU", "HDP", "OU"],
    "Home信号": ["A2", "B0.5", "", "A1", "B2"],
    "Away信号": ["B0.5", "A2", "A0.2", "", ""],
}

sample_b = {
    "联赛": [selected_league] * 5,
    "分组": [selected_group] * 5,
    "队伍": ["队伍A", "队伍B", "队伍C", "队伍D", "队伍E"],
    "玩法": ["HDP", "HDP", "OU", "HDP", "OU"],
    "Home信号": ["A2", "B0.5", "", "A1.5", "B2"],
    "Away信号": ["B0.5", "A2", "A0.2", "", ""],
}

df_a = pd.DataFrame(sample_a)
df_b = pd.DataFrame(sample_b)

# 合并对比
comparison = pd.concat([df_a, df_b]).drop_duplicates(keep=False)

col_left, col_right = st.columns(2)

with col_left:
    st.write(f"**版本 A ({version_a_date})**")
    st.dataframe(df_a, use_container_width=True)

with col_right:
    st.write(f"**版本 B ({version_b_date})**")
    st.dataframe(df_b, use_container_width=True)

# 变化检测
st.subheader("🔄 变化检测")

changes = []
for i in range(len(df_a)):
    home_a = df_a.iloc[i]["Home信号"]
    home_b = df_b.iloc[i]["Home信号"]
    away_a = df_a.iloc[i]["Away信号"]
    away_b = df_b.iloc[i]["Away信号"]

    if home_a != home_b or away_a != away_b:
        changes.append({
            "队伍": df_a.iloc[i]["队伍"],
            "玩法": df_a.iloc[i]["玩法"],
            "Home变化": f"{home_a} → {home_b}" if home_a != home_b else "-",
            "Away变化": f"{away_a} → {away_b}" if away_a != away_b else "-",
        })

if changes:
    st.warning(f"检测到 {len(changes)} 处变化")
    st.dataframe(pd.DataFrame(changes), use_container_width=True)
else:
    st.success("版本间无变化")

# 导出功能
st.divider()
st.subheader("📥 导出")

if st.button("导出对比报告"):
    st.success("报告导出功能开发中")