"""Alert center UI. The page manages decisions; it does not run leak detection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme, empty_state, page_header, section_title, status_chip
from tools.alert_service import DEFAULT_DB, get_actions, get_summary, list_alerts, transition

apply_theme()
page_header(
    "Cảnh báo",
    "Tiếp nhận, phân loại, xác nhận và đóng sự cố. Mọi thao tác đều được lưu trong nhật ký để truy vết.",
)

try:
    summary = get_summary(DEFAULT_DB)
except Exception as exc:
    st.error(f"Không thể khởi tạo hoặc đọc bảng cảnh báo: {exc}")
    st.stop()

metrics = st.columns(4)
metrics[0].metric("Đang mở", summary["open"])
metrics[1].metric("Đã xác nhận", summary["acknowledged"])
metrics[2].metric("Đã đóng", summary["closed"])
metrics[3].metric("Tổng sự kiện", summary["total"])

actions_col, info_col = st.columns([1, 4])
with actions_col:
    if st.button("Làm mới", use_container_width=True):
        st.rerun()
with info_col:
    st.caption(
        "Trang này quản lý sự cố đã được hệ thống ghi nhận; không tự chạy AI "
        "hoặc xác nhận nguồn dữ liệu vật lý."
    )

section_title("Danh sách sự cố", "Lọc theo trạng thái, zone, mức độ hoặc từ khóa")
f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    state = st.selectbox(
        "Trạng thái",
        ["all", "open", "acknowledged", "closed"],
        format_func=lambda value: {
            "all": "Tất cả", "open": "Đang mở",
            "acknowledged": "Đã xác nhận", "closed": "Đã đóng"
        }[value],
    )
with f2:
    zone_filter = st.selectbox("Vị trí", ["Tất cả", "main", "zone1", "zone2", "unknown"])
with f3:
    search = st.text_input("Tìm kiếm", placeholder="Mã thiết bị, loại sự cố, lý do...")

try:
    alerts = list_alerts(DEFAULT_DB, state=state, limit=500)
except Exception as exc:
    st.error(f"Không tải được danh sách cảnh báo: {exc}")
    st.stop()

if zone_filter != "Tất cả":
    alerts = [a for a in alerts if a.get("zone") == zone_filter]
if search.strip():
    term = search.casefold()
    alerts = [
        a for a in alerts
        if term in " ".join(str(a.get(k, "")) for k in
                            ("id", "device_id", "category", "zone", "severity", "source", "reasons_json")).casefold()
    ]

if not alerts:
    empty_state("Không tìm thấy cảnh báo phù hợp", "Thay đổi bộ lọc hoặc chờ một bộ phát hiện đã được kiểm chứng gửi quyết định.")
    st.stop()

view = pd.DataFrame(alerts)
view["reasons"] = view["reasons_json"].apply(
    lambda raw: "; ".join(json.loads(raw)) if raw else ""
)
columns = [
    "id", "first_seen_utc", "last_seen_utc", "device_id", "category", "zone",
    "severity", "state", "observations", "latest_score", "provenance", "reasons",
]
section_title("Bảng sự cố", f"{len(view):,} cảnh báo phù hợp bộ lọc")
st.dataframe(
    view[[column for column in columns if column in view.columns]],
    use_container_width=True,
    hide_index=True,
    height=330,
)
st.download_button(
    "Xuất danh sách CSV",
    data=view[[column for column in columns if column in view.columns]].to_csv(index=False).encode("utf-8-sig"),
    file_name="projectII_alerts.csv",
    mime="text/csv",
)

section_title("Chi tiết & xử lý sự cố", "Xem nguồn quyết định, lý do và lịch sử thay đổi")
by_id = {int(a["id"]): a for a in alerts}
selected_id = st.selectbox(
    "Chọn mã sự cố",
    list(by_id),
    format_func=lambda key: f"#{key} · {by_id[key]['category']} · {by_id[key]['zone']} · {by_id[key]['state']}",
)
selected = by_id[selected_id]
left, right = st.columns([1.15, 1])
with left:
    st.markdown(f"**Sự cố #{selected['id']}**")
    status_kind = {"open": "bad", "acknowledged": "warn", "closed": "good"}.get(selected["state"], "neutral")
    status_label = {"open": "Đang mở", "acknowledged": "Đã xác nhận", "closed": "Đã đóng"}.get(selected["state"], selected["state"])
    status_chip(status_label, status_kind)
    st.write(f"**Loại:** {selected['category']}")
    st.write(f"**Khu vực:** {selected['zone']} · **Mức độ:** {selected['severity']}")
    st.write(f"**Thiết bị:** {selected['device_id']}")
    st.write(f"**Nguồn quyết định:** {selected['source']} · **Nguồn dữ liệu:** {selected['provenance']}")
    st.write(f"**Số lần quan sát:** {selected['observations']}")
    st.write(f"**Lần đầu:** {selected['first_seen_utc']}")
    st.write(f"**Lần cuối:** {selected['last_seen_utc']}")
    st.markdown("**Lý do do bộ phát hiện cung cấp**")
    for reason in json.loads(selected["reasons_json"]):
        st.markdown(f"- {reason}")
    if selected.get("close_note"):
        st.info(f"Ghi chú đóng: {selected['close_note']}")
with right:
    st.markdown("**Cập nhật trạng thái**")
    if selected["state"] == "closed":
        st.success("Sự cố đã đóng. Lịch sử được giữ nguyên.")
    else:
        with st.form("process_alert", clear_on_submit=True):
            actor = st.text_input("Người thao tác", placeholder="Tên người vận hành")
            note = st.text_area("Ghi chú xử lý", placeholder="Mô tả bước kiểm tra hoặc kết quả xử lý...")
            next_action = st.radio(
                "Thao tác",
                ["acknowledge", "close"],
                horizontal=True,
                format_func=lambda value: "Xác nhận đã tiếp nhận" if value == "acknowledge" else "Đóng sự cố",
            )
            submitted = st.form_submit_button("Lưu thay đổi", type="primary", use_container_width=True)
        if submitted:
            try:
                result = transition(selected_id, next_action, actor, note, db=DEFAULT_DB)
                st.success(f"Đã cập nhật sự cố #{result['alert_id']}.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    st.caption("Xác nhận chỉ có nghĩa đã tiếp nhận/đang xử lý; không đồng nghĩa đã khắc phục rò rỉ.")

section_title("Nhật ký kiểm toán", "Lịch sử thao tác trên sự cố đang chọn")
try:
    action_rows = get_actions(selected_id, db=DEFAULT_DB)
    if action_rows:
        action_df = pd.DataFrame(action_rows)
        st.dataframe(action_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Xuất nhật ký thao tác",
            data=action_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"alert_{selected_id}_audit.csv",
            mime="text/csv",
        )
    else:
        empty_state("Chưa có thao tác", "Nhật ký sẽ xuất hiện khi có sự cố hoặc người vận hành cập nhật trạng thái.")
except Exception as exc:
    st.error(f"Không đọc được nhật ký thao tác: {exc}")
