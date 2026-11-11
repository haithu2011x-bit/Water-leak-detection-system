"""Main navigation and visual shell for the Project II dashboard."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme

st.set_page_config(
    page_title="Water Intelligence | Project II",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

with st.sidebar:
    st.markdown(
        """
        <div style="padding:12px 10px 18px">
          <div style="font-size:2rem;line-height:1">💧</div>
          <div style="font-size:1.05rem;font-weight:800;letter-spacing:.01em;margin-top:9px;color:#fff">
            WATER INTELLIGENCE
          </div>
          <div style="font-size:.75rem;color:#9fb4cd;margin-top:4px">PROJECT II · IoT / AI MONITOR</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("**ĐIỀU HƯỚNG HỆ THỐNG**")
    st.caption("Giám sát dữ liệu và vận hành thí nghiệm trên cùng một giao diện.")
    st.divider()
    st.markdown(
        '<div style="font-size:.75rem;color:#a9bfd8;line-height:1.6">'
        'THIẾT BỊ<br><b style="color:#fff">ESP32 · 3 × YF-S401</b><br><br>'
        'LƯU TRỮ<br><b style="color:#fff">SQLite · Local</b><br><br>'
        'DASHBOARD<br><b style="color:#fff">Streamlit</b></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Chế độ hiện tại: giám sát cục bộ")
    st.caption("Dữ liệu hiển thị không tự chứng minh nguồn cảm biến vật lý.")

pages = {
    "GIÁM SÁT": [
        st.Page("overview_page.py", title="Tổng quan", icon=":material/dashboard:", default=True),
        st.Page("app.py", title="Lưu lượng & lịch sử", icon=":material/water_drop:"),
        st.Page("quality_page.py", title="Chất lượng dữ liệu", icon=":material/monitor_heart:"),
    ],
    "VẬN HÀNH": [
        st.Page("experiment_app.py", title="Phiên thí nghiệm", icon=":material/science:"),
        st.Page("alerts_app.py", title="Trung tâm cảnh báo", icon=":material/notifications_active:"),
    ],
}

st.navigation(pages, position="sidebar").run()
