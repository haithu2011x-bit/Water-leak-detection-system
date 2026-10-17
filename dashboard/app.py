import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "water.db"

st.set_page_config(page_title="Water Leak Monitor", layout="wide")
st.title("Water Leak Monitor")
st.caption("Project II - Hệ thống IoT - AI phát hiện rò rỉ nước")

@st.cache_data(ttl=2)
def load_data():
    if not DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB) as con:
        frame = pd.read_sql_query("""
            SELECT id, ts_server, flow_main, flow_z1, flow_z2,
                   label, scenario_id
            FROM telemetry ORDER BY id DESC LIMIT 600
        """, con)
    return frame.sort_values("id")

df = load_data()
if df.empty:
    st.warning("Chưa có dữ liệu. Chạy collector và fake_sensor trước.")
    st.stop()

df["balance_residual"] = df["flow_main"] - df["flow_z1"] - df["flow_z2"]
last = df.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Flow Main (L/min)", f"{last['flow_main']:.2f}")
c2.metric("Zone 1 (L/min)", f"{last['flow_z1']:.2f}")
c3.metric("Zone 2 (L/min)", f"{last['flow_z2']:.2f}")
c4.metric("Residual (L/min)", f"{last['balance_residual']:.2f}")

st.caption("Residual = Flow Main - Zone 1 - Zone 2.")
st.subheader("Lưu lượng gần đây")
st.line_chart(df.set_index("id")[["flow_main", "flow_z1", "flow_z2"]])
st.subheader("Chênh lệch cân bằng lưu lượng")
st.line_chart(df.set_index("id")[["balance_residual"]])
st.subheader("Dữ liệu mới nhất")
st.dataframe(df.tail(20).sort_values("id", ascending=False), use_container_width=True)
if st.button("Refresh"):
    st.cache_data.clear()
    st.rerun()
