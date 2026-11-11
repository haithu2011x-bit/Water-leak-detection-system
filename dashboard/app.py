import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme, empty_state, page_header, section_title
from dashboard.data_filters import prepare_telemetry_history, filter_telemetry_dates

DB = ROOT / "data" / "water.db"

apply_theme()
page_header(
    "Lưu lượng & lịch sử đo",
    "Theo dõi biến thiên của đường ống tổng và hai zone, đối chiếu cân bằng lưu lượng và xuất dữ liệu phục vụ phân tích.",
    tag="TELEMETRY EXPLORER",
)

@st.cache_data(ttl=3)
def load_data(limit: int) -> pd.DataFrame:
    if not DB.is_file():
        return pd.DataFrame()
    with sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as con:
        frame = pd.read_sql_query(
            """
            SELECT id, ts_server, flow_main, flow_z1, flow_z2, label, scenario_id
            FROM telemetry ORDER BY id DESC LIMIT ?
            """,
            con,
            params=(int(limit),),
        )
    return frame.sort_values("id").reset_index(drop=True)

top = st.columns([1, 1, 3])
with top[0]:
    row_limit = st.selectbox("Số mẫu tải", [100, 300, 600, 1200, 3000], index=2)
with top[1]:
    if st.button("↻ Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df = load_data(row_limit)
except (sqlite3.Error, OSError, ValueError) as exc:
    st.error(f"Không thể đọc dữ liệu telemetry: {exc}")
    st.stop()
if df.empty:
    empty_state("Chưa có telemetry", "Kiểm tra Collector, MQTT broker hoặc kết nối USB Serial. Không dùng dữ liệu giả để thay thế số đo thật.")
    st.stop()

df = prepare_telemetry_history(df)
if df.empty:
    st.warning("Có bản ghi nhưng không có mẫu hợp lệ để vẽ biểu đồ.")
    st.stop()

section_title("Bộ lọc hiển thị", f"{len(df):,} mẫu đã tải")
f1, f2 = st.columns([1, 2])
with f1:
    channels = st.multiselect(
        "Kênh lưu lượng",
        ["flow_main", "flow_z1", "flow_z2"],
        default=["flow_main", "flow_z1", "flow_z2"],
        format_func=lambda x: {"flow_main": "Đường ống tổng", "flow_z1": "Zone 1", "flow_z2": "Zone 2"}[x],
    )
with f2:
    date_min = df["ts_server"].min().date()
    date_max = df["ts_server"].max().date()
    date_range = st.date_input("Khoảng ngày (UTC)", value=(date_min, date_max), min_value=date_min, max_value=date_max)

filtered = filter_telemetry_dates(df, date_range)

if filtered.empty:
    empty_state("Không có mẫu trong bộ lọc", "Thay đổi khoảng ngày để xem lại dữ liệu.")
else:
    st.caption("Các chỉ số bên dưới được tính từ mẫu cuối trong khoảng ngày đang chọn (UTC).")
    last = df.iloc[-1]
    metrics = st.columns(4)
    metrics[0].metric("Đường ống tổng", f"{last['flow_main']:.2f} L/min")
    metrics[1].metric("Zone 1", f"{last['flow_z1']:.2f} L/min")
    metrics[2].metric("Zone 2", f"{last['flow_z2']:.2f} L/min")
    metrics[3].metric("Residual", f"{last['residual']:+.2f} L/min")
    
    
    section_title("Biểu đồ lưu lượng", "Đơn vị: lít/phút")
    if channels:
        labels = {"flow_main": "Main", "flow_z1": "Zone 1", "flow_z2": "Zone 2"}
        chart = filtered.set_index("ts_server")[channels].rename(columns=labels)
        st.line_chart(chart, height=360)
    else:
        st.info("Chọn ít nhất một kênh để hiển thị biểu đồ.")
    section_title("Sai lệch cân bằng", "Residual = Main − Zone 1 − Zone 2")
    st.line_chart(filtered.set_index("ts_server")[["residual"]], height=210)
    avg_abs = filtered["residual"].abs().mean()
    max_abs = filtered["residual"].abs().max()
    a, b, c = st.columns(3)
    a.metric("Residual trung bình tuyệt đối", f"{avg_abs:.3f} L/min")
    b.metric("Residual tuyệt đối lớn nhất", f"{max_abs:.3f} L/min")
    c.metric("Số mẫu đang xem", f"{len(filtered):,}")
    st.caption("Residual có thể chịu ảnh hưởng của sai số cảm biến, hiệu chuẩn, độ trễ và vị trí lắp đặt; không dùng riêng chỉ số này để kết luận rò rỉ.")

    section_title("Bảng dữ liệu", "Các mẫu mới nhất được hiển thị trước")
    table = filtered.sort_values("id", ascending=False).copy()
    table["ts_server"] = table["ts_server"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    st.dataframe(table, use_container_width=True, hide_index=True, height=360)
    st.download_button(
        "↓ Xuất dữ liệu CSV",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="water_telemetry_history.csv",
        mime="text/csv",
        use_container_width=False,
    )

st.caption("Nguồn dữ liệu: SQLite telemetry. Dữ liệu lịch sử có thể bao gồm mẫu chưa xác minh hoặc đã đánh dấu kịch bản.")
