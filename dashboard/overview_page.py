"""System overview: read-only operational snapshot and recent flow trends."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.data_filters import prepare_telemetry_history
from dashboard.ui import (
    FLOW_COLORS, RESIDUAL_COLOR, apply_theme, empty_state, page_header,
    section_title, status_chip,
)
from tools.unified_dashboard_service import DEFAULT_DB, overview, recent_history
from tools.realtime_detection import artifacts_ready

apply_theme()
page_header(
    "Tổng quan",
    "Số liệu thu thập, phiên đo và trạng thái hệ thống tại thời điểm tải trang.",
)

toolbar = st.columns([1, 5])
with toolbar[0]:
    if st.button("Làm mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    snap = overview(DEFAULT_DB)
except (sqlite3.Error, OSError, ValueError) as exc:
    st.error(f"Không thể đọc database: {exc}")
    st.code(r".\.venv\Scripts\python.exe backend\collector.py", language="powershell")
    st.stop()

latest = snap["latest"]
cols = st.columns(5)
cols[0].metric("Tổng bản ghi", f"{snap['total']:,}")
cols[1].metric("Bản ghi có nhãn", f"{snap['tagged_history']:,}")
cols[2].metric("Phiên đang ghi", snap["sessions"]["active"])
cols[3].metric("Cảnh báo mở", snap["alerts"]["open"])
cols[4].metric("Đã xác nhận", snap["alerts"]["acknowledged"])

section_title("Trạng thái vận hành", "Theo dữ liệu SQLite và cấu hình hiện tại")
c1, c2, c3 = st.columns(3, gap="large")
with c1:
    st.markdown("**Thu thập dữ liệu**")
    if latest and snap["recent_row"]:
        status_chip("Dữ liệu mới", "good")
        st.caption("Đã nhận bản ghi trong khoảng thời gian giám sát.")
    elif latest:
        status_chip("Cần kiểm tra kết nối", "warn")
        st.caption("Bản ghi cuối đã cũ; kiểm tra Collector và broker.")
    else:
        status_chip("Chưa có dữ liệu")
        st.caption("Chưa nhận được telemetry.")
    if latest:
        st.caption(f"Mẫu #{latest['id']} · {latest['ts_server']}")
with c2:
    st.markdown("**Tính hợp lệ của mẫu cuối**")
    if latest and snap["latest_flows_valid"]:
        status_chip("Lưu lượng hợp lệ", "good")
        st.caption("Ba giá trị có kiểu số và không âm.")
    elif latest:
        status_chip("Giá trị không hợp lệ", "bad")
        st.caption("Cần kiểm tra bộ thu dữ liệu.")
    else:
        status_chip("Chưa có mẫu")
    if snap["latest_marked_legacy"]:
        st.warning("Mẫu cuối có nhãn lịch sử/kịch bản; không dùng làm chứng cứ đo thật.")
with c3:
    st.markdown("**Điều kiện phát hiện AI**")
    try:
        reasons, _ = artifacts_ready()
    except Exception as exc:
        reasons = [f"Không kiểm tra được điều kiện: {exc}"]
    if reasons:
        status_chip("Chưa sẵn sàng", "warn")
        with st.expander("Xem điều kiện còn thiếu"):
            for item in reasons:
                st.write(f"• {item}")
    else:
        status_chip("Đã đủ điều kiện cấu hình", "good")
    st.caption("Trạng thái cấu hình không chứng minh độ chính xác của mô hình.")

section_title("Lưu lượng gần đây", "Tối đa 300 mẫu · thời gian UTC · lít/phút")
try:
    data = pd.DataFrame(recent_history(DEFAULT_DB, limit=300))
except (sqlite3.Error, OSError, ValueError) as exc:
    st.error(f"Không tải được lịch sử: {exc}")
    data = pd.DataFrame()

if data.empty:
    empty_state("Chưa có lịch sử đo", "Kết nối Collector để nhận dữ liệu telemetry.")
else:
    data = prepare_telemetry_history(data)
    if data.empty:
        empty_state("Không có mẫu hợp lệ", "Kiểm tra thời gian và giá trị lưu lượng đã lưu.")
    else:
        left, right = st.columns([1.7, 1], gap="large")
        with left:
            st.markdown("**Ba kênh lưu lượng**")
            st.line_chart(
                data.set_index("ts_server")[["flow_main", "flow_z1", "flow_z2"]],
                color=list(FLOW_COLORS), height=320,
            )
        with right:
            st.markdown("**Sai lệch cân bằng**")
            st.line_chart(
                data.set_index("ts_server")[["residual"]],
                color=RESIDUAL_COLOR, height=320,
            )
            st.caption("Main − Zone 1 − Zone 2. Không dùng riêng chỉ số này để kết luận rò rỉ.")
        with st.expander("Xem 30 mẫu gần nhất"):
            st.dataframe(
                data.tail(30).sort_values("ts_server", ascending=False),
                use_container_width=True, hide_index=True,
            )

st.caption("Dữ liệu có thể chưa được xác minh nguồn vật lý, dù thời gian và định dạng hợp lệ.")
