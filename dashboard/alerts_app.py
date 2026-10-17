"""Alert management UI. No model execution and no simulated telemetry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.alert_service import DEFAULT_DB, get_actions, get_summary, list_alerts, transition

st.set_page_config(page_title="Project II | Cảnh báo", layout="wide")
st.title("Project II · Quản lý cảnh báo")
st.caption("3 cảm biến YF-S401 · Không dùng cảm biến áp suất · Giao diện độc lập với mô hình AI")
st.info("Alert Engine chỉ lưu và quản lý quyết định do bộ phát hiện gửi đến. Chưa có AI được kết nối thì không tự phát sinh cảnh báo. Dữ liệu giả lập cũ không được tự chuyển thành cảnh báo thực.")

try:
    summary = get_summary(DEFAULT_DB)
except Exception as exc:
    st.error(f"Không thể khởi tạo bảng alerts: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Đang mở", summary["open"])
c2.metric("Đã xác nhận", summary["acknowledged"])
c3.metric("Đã đóng", summary["closed"])
c4.metric("Tổng sự kiện cảnh báo", summary["total"])

if st.button("Làm mới"):
    st.rerun()

selected_state = st.selectbox(
    "Lọc theo trạng thái",
    ["all", "open", "acknowledged", "closed"],
    format_func=lambda state: {"all": "Tất cả", "open": "Đang mở", "acknowledged": "Đã xác nhận", "closed": "Đã đóng"}[state],
)
try:
    alerts = list_alerts(DEFAULT_DB, state=selected_state, limit=300)
except Exception as exc:
    st.error(f"Không tải được cảnh báo: {exc}")
    st.stop()

if not alerts:
    st.info("Chưa có cảnh báo trong bộ lọc này. Đây là trạng thái bình thường khi chưa kết nối bộ phát hiện sử dụng dữ liệu thật.")
    st.stop()

st.subheader("Danh sách cảnh báo")
view = pd.DataFrame(alerts)
view["reasons"] = view["reasons_json"].apply(lambda s: "; ".join(json.loads(s)))
columns = ["id", "first_seen_utc", "last_seen_utc", "device_id", "category", "zone", "severity", "state", "observations", "latest_score", "provenance", "reasons"]
st.dataframe(view[columns], use_container_width=True, hide_index=True)
st.download_button("Xuất danh sách cảnh báo CSV", view[columns].to_csv(index=False).encode("utf-8-sig"),
                   file_name="projectII_alerts.csv", mime="text/csv")

st.subheader("Xem và xử lý cảnh báo")
ids = [int(r["id"]) for r in alerts]
selected_id = st.selectbox("Mã cảnh báo", ids, format_func=lambda x: f"#{x}")
selected = next(a for a in alerts if a["id"] == selected_id)

st.write(f"**Loại:** `{selected['category']}` · **Vùng:** `{selected['zone']}` · **Mức:** `{selected['severity']}`")
st.write(f"**Nguồn quyết định:** `{selected['source']}` · **Nguồn gốc dữ liệu:** `{selected['provenance']}`")
st.write("**Lý do được bộ phát hiện cung cấp:**")
for reason in json.loads(selected["reasons_json"]):
    st.write("- " + reason)
st.caption("Xác nhận cảnh báo = đã đọc/đang xử lý; không có nghĩa đã khắc phục rò rỉ.")

with st.form("process_alert"):
    name = st.text_input("Người thao tác", placeholder="Ví dụ: nguoi_van_hanh")
    note = st.text_area("Ghi chú (bắt buộc khi đóng)")
    next_action = st.radio("Thao tác", ["acknowledge", "close"], horizontal=True,
                           format_func=lambda x: "Xác nhận đã nhận" if x == "acknowledge" else "Đóng cảnh báo")
    disabled = selected["state"] == "closed" or (next_action == "acknowledge" and selected["state"] != "open")
    submitted = st.form_submit_button("Lưu trạng thái", disabled=disabled)
if submitted:
    try:
        result = transition(selected_id, next_action, name, note, db=DEFAULT_DB)
        st.success(f"Đã chuyển cảnh báo #{result['alert_id']} sang '{result['state']}'.")
        st.rerun()
    except (ValueError, OSError) as exc:
        st.error(str(exc))

st.subheader("Nhật ký thao tác")
try:
    actions = get_actions(selected_id, db=DEFAULT_DB)
    st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)
except Exception as exc:
    st.error(f"Không đọc được nhật ký: {exc}")
