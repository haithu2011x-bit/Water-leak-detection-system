"""Entry point and navigation for the local water-monitoring application."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme

st.set_page_config(
    page_title="Giám sát nước | Dự án II",
    page_icon=":material/water_drop:",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

with st.sidebar:
    st.markdown("### Giám sát nước")
    st.caption("Dự án II · Hệ thống cục bộ")
    st.divider()
    st.caption("Thiết bị: ESP32 · 3 cảm biến YF-S401")
    st.caption("Lưu trữ: SQLite")
    st.divider()
    st.caption("Số đo đúng định dạng chưa xác nhận nguồn phần cứng.")

pages = {
    "Theo dõi": [
        st.Page("overview_page.py", title="Tổng quan", icon=":material/dashboard:", default=True),
        st.Page("app.py", title="Lưu lượng & lịch sử", icon=":material/water_drop:"),
        st.Page("quality_page.py", title="Chất lượng dữ liệu", icon=":material/monitor_heart:"),
    ],
    "Vận hành": [
        st.Page("experiment_app.py", title="Phiên thí nghiệm", icon=":material/science:"),
        st.Page("alerts_app.py", title="Cảnh báo", icon=":material/notifications_active:"),
    ],
}

st.navigation(pages, position="sidebar").run()
