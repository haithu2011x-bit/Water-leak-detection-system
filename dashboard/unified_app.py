"""Unified navigation for Project II: existing pages remain separate and reusable.

Streamlit >=1.36 is required for st.Page / st.navigation.
Run on port 8504 first to leave the three original dashboards untouched.
"""
import streamlit as st

st.set_page_config(page_title="Project II | IoT-AI Water Monitor", layout="wide")

pages = {
    "Giám sát": [
        st.Page("overview_page.py", title="Tổng quan", icon=":material:dashboard:", default=True),
        st.Page("app.py", title="Biểu đồ lưu lượng (lịch sử)", icon=":material:show_chart:"),
        st.Page("quality_page.py", title="Chất lượng kết nối", icon=":material:monitor_heart:"),
    ],
    "Vận hành": [
        st.Page("experiment_app.py", title="Phiên thí nghiệm", icon=":material:science:"),
        st.Page("alerts_app.py", title="Quản lý cảnh báo", icon=":material:notifications:"),
    ],
}

st.navigation(pages).run()
