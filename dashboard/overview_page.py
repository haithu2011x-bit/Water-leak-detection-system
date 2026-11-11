import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme, empty_state, page_header, section_title
from tools.unified_dashboard_service import DEFAULT_DB, overview, recent_history
from tools.realtime_detection import artifacts_ready

apply_theme()
page_header(
    "Tổng quan hệ thống",
    "Trạng thái vận hành, lưu lượng ba nhánh và mức sẵn sàng của pipeline IoT–AI.",
    tag="MAIN · ZONE 1 · ZONE 2",
)

toolbar = st.columns([1, 5])
with toolbar[0]:
    if st.button("↻ Làm mới", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    snap = overview(DEFAULT_DB)
except (OSError, ValueError) as exc:
    st.error(f"Không thể đọc database: {exc}")
    st.code(r".\.venv\Scripts\python.exe backend\collector.py", language="powershell")
    st.stop()

latest = snap["latest"]
cols = st.columns(5)
cols[0].metric("Tổng bản ghi", f"{snap['total']:,}")
cols[1].metric("Bản ghi lịch sử có nhãn", f"{snap['tagged_history']:,}")
cols[2].metric("Phiên đang chạy", snap["sessions"]["active"])
cols[3].metric("Cảnh báo đang mở", snap["alerts"]["open"])
cols[4].metric("Đã xác nhận", snap["alerts"]["acknowledged"])

section_title("Tình trạng hệ thống", "Ảnh chụp từ SQLite và cấu hình tại thời điểm tải trang")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Luồng dữ liệu**")
    if latest and snap["recent_row"]:
        st.success("Có bản ghi mới trong khoảng thời gian giám sát.")
    elif latest:
        st.warning("Bản ghi cuối đã cũ; cần kiểm tra Collector / broker.")
    else:
        st.info("Chưa có bản ghi telemetry.")
    if latest:
        st.caption(f"Mẫu cuối: #{latest['id']} · {latest['ts_server']}")
with c2:
    st.markdown("**Kiểm tra dữ liệu cuối**")
    if latest and snap["latest_flows_valid"]:
        st.success("Ba giá trị lưu lượng hợp lệ về kiểu và miền giá trị.")
    elif latest:
        st.error("Có giá trị lưu lượng không hợp lệ.")
    else:
        st.info("Chưa có dữ liệu để kiểm tra.")
    if snap["latest_marked_legacy"]:
        st.warning("Mẫu cuối mang nhãn lịch sử / kịch bản; không dùng làm bằng chứng đo thật.")
with c3:
    st.markdown("**Mức sẵn sàng AI**")
    try:
        reasons, _ = artifacts_ready()
    except Exception as exc:
        reasons = [f"Không kiểm tra được điều kiện AI: {exc}"]
    if reasons:
        st.warning("Chưa đủ điều kiện cho phép AI phát cảnh báo.")
        with st.expander("Điều kiện còn thiếu"):
            for item in reasons:
                st.write(f"• {item}")
    else:
        st.success("Các tệp phê duyệt và arming hiện hợp lệ.")
    st.caption("Đây không phải xác nhận độ chính xác thực nghiệm của mô hình.")

section_title("Lưu lượng gần đây", "Lịch sử chưa xác minh nguồn · tối đa 300 mẫu")
try:
    data = pd.DataFrame(recent_history(DEFAULT_DB, limit=300))
except (OSError, ValueError) as exc:
    st.error(f"Không tải được lịch sử: {exc}")
    data = pd.DataFrame()

if data.empty:
    empty_state("Chưa có dữ liệu lịch sử", "Kết nối Collector để bắt đầu nhận telemetry.")
else:
    data["ts_server"] = pd.to_datetime(data["ts_server"], utc=True, errors="coerce")
    for key in ("flow_main", "flow_z1", "flow_z2"):
        data[key] = pd.to_numeric(data[key], errors="coerce")
    data = data.dropna(subset=["ts_server", "flow_main", "flow_z1", "flow_z2"])
    data["residual"] = data["flow_main"] - data["flow_z1"] - data["flow_z2"]
    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("**Phân bố lưu lượng theo thời gian**")
        st.line_chart(data.set_index("ts_server")[["flow_main", "flow_z1", "flow_z2"]], height=300)
    with right:
        st.markdown("**Cân bằng lưu lượng**")
        st.line_chart(data.set_index("ts_server")[["residual"]], height=300)
        st.caption("Residual = Main − Zone 1 − Zone 2. Chỉ là chỉ số tham khảo, không tự kết luận rò rỉ.")
    with st.expander("Xem bảng dữ liệu gần nhất"):
        st.dataframe(data.tail(30).sort_values("ts_server", ascending=False), use_container_width=True, hide_index=True)

st.caption("Lưu ý: bản tin mới hoặc đúng định dạng không chứng minh dữ liệu đến từ ESP32 vật lý.")
