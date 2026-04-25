"""参数设置页面"""

import streamlit as st
import json

st.title("⚙️ 参数设置")

st.info("调整算法参数，影响信号计算结果")

# 加载当前参数
try:
    with open("config/default_params.json", "r", encoding="utf-8") as f:
        params = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    params = {
        "x_value_boundaries": [-0.24, -0.22, -0.15, -0.08, -0.03, 0.07, 0.15, 0.23],
        "five_zone_mapping": [[1], [2, 3, 4], [5, 6], [7, 8], [9]],
        "round_block_size": 10,
        "guard_ratio_threshold": 1.4,
        "strength_upgrade_multiplier": 2.0,
    }

# X值边界
st.subheader("🎯 X值分界点")

st.write("将 X 值划分为 9 个区间的边界值：")

col1, col2 = st.columns(2)

with col1:
    x1 = st.number_input("Zone 1 边界", value=params.get("x_value_boundaries", [-0.24])[0], step=0.01)
    x2 = st.number_input("Zone 2 边界", value=params.get("x_value_boundaries", [-0.22])[1], step=0.01)
    x3 = st.number_input("Zone 3 边界", value=params.get("x_value_boundaries", [-0.15])[2], step=0.01)
    x4 = st.number_input("Zone 4 边界", value=params.get("x_value_boundaries", [-0.08])[3], step=0.01)

with col2:
    x5 = st.number_input("Zone 5 边界", value=params.get("x_value_boundaries", [-0.03])[4], step=0.01)
    x6 = st.number_input("Zone 6 边界", value=params.get("x_value_boundaries", [0.07])[5], step=0.01)
    x7 = st.number_input("Zone 7 边界", value=params.get("x_value_boundaries", [0.15])[6], step=0.01)
    x8 = st.number_input("Zone 8 边界", value=params.get("x_value_boundaries", [0.23])[7], step=0.01)

x_boundaries = [x1, x2, x3, x4, x5, x6, x7, x8]

# 可视化区间
st.write("**当前区间划分：**")
st.code(f"""
Zone 1: X ≤ {x1}
Zone 2: {x1} < X ≤ {x2}
Zone 3: {x2} < X ≤ {x3}
Zone 4: {x3} < X ≤ {x4}
Zone 5: {x4} < X ≤ {x5}
Zone 6: {x5} < X ≤ {x6}
Zone 7: {x6} < X ≤ {x7}
Zone 8: {x7} < X ≤ {x8}
Zone 9: X > {x8}
""")

# 轮次块大小
st.divider()
st.subheader("📊 轮次块大小")

round_block_size = st.number_input(
    "每 N 轮为一个块",
    min_value=1,
    max_value=20,
    value=params.get("round_block_size", 10),
    help="数据聚合时每多少轮分为一个块"
)

# 护级参数
st.divider()
st.subheader("🛡️ 护级判定参数")

guard_threshold = st.number_input(
    "护级比率阈值",
    min_value=1.0,
    max_value=3.0,
    value=params.get("guard_ratio_threshold", 1.4),
    step=0.1,
    help="护级 2 升级到 4 的比率门槛"
)

# 强度升级参数
st.divider()
st.subheader("💪 强度升级参数")

strength_multiplier = st.number_input(
    "强度升级倍数",
    min_value=1.0,
    max_value=5.0,
    value=params.get("strength_upgrade_multiplier", 2.0),
    step=0.1,
    help="护级 2 升级到 4 的赢输比倍数"
)

# 五大区间映射
st.divider()
st.subheader("🗂️ 五大区间映射")

st.write("将 9 个小区间合并为 5 个大区间：")

five_zone = params.get("five_zone_mapping", [[1], [2, 3, 4], [5, 6], [7, 8], [9]])

for i, zone in enumerate(five_zone, 1):
    st.write(f"**大区间 {i}**: Zone {', '.join(map(str, zone))}")

# 保存按钮
st.divider()

if st.button("💾 保存参数", type="primary"):
    new_params = {
        "x_value_boundaries": x_boundaries,
        "five_zone_mapping": five_zone,
        "round_block_size": round_block_size,
        "guard_ratio_threshold": guard_threshold,
        "strength_upgrade_multiplier": strength_multiplier,
    }

    try:
        with open("config/default_params.json", "w", encoding="utf-8") as f:
            json.dump(new_params, f, ensure_ascii=False, indent=2)
        st.success("参数已保存！")
    except Exception as e:
        st.error(f"保存失败: {e}")

# 恢复默认
if st.button("🔄 恢复默认"):
    st.warning("恢复默认功能开发中")