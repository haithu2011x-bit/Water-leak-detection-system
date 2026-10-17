"""Read-only overview. Fresh SQLite rows do not prove physical ESP32 provenance."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.unified_dashboard_service import DEFAULT_DB, overview, recent_history

st.title("Tổng quan hệ thống IoT–AI")
st.caption("3 cảm biến YF-S401 · Main / Zone 1 / Zone 2 · Không có cảm biến áp suất")
st.info("Chưa kích hoạt phát hiện rò rỉ bằng AI trên dữ liệu thực. Không dùng dữ liệu giả lập để xác nhận rò rỉ.")

try:
    snap = overview(DEFAULT_DB)
except (OSError, ValueError) as exc:
    st.warning("Chưa có database hợp lệ để giám sát: " + str(exc))
    st.code(r".\.venv\Scripts\python.exe backend\collector.py", language="powershell")
    st.caption("Chỉ cần Collector tạo database; không chạy fake_sensor để có số liệu.")
    st.stop()

cols = st.columns(5)
cols[0].metric("Bản ghi", f"{snap['total']:,}")
cols[1].metric("Có nhãn cũ", f"{snap['tagged_history']:,}")
cols[2].metric("Phiên đang mở", snap['sessions']['active'])
cols[3].metric("Cảnh báo mở", snap['alerts']['open'])
cols[4].metric("Đã xác nhận", snap['alerts']['acknowledged'])

latest = snap['latest']
if latest:
    st.write(f"Mẫu cuối: #{latest['id']} · {latest['ts_server']}")
    if not snap['recent_row']:
        st.warning("Không thấy bản ghi mới trong 12 giây gần đây; chưa đủ cơ sở kết luận MQTT bị mất kết nối.")
    else:
        st.info("SQLite có bản ghi mới. Thời gian mới không xác minh nguồn ESP32 vật lý.")
    if snap['latest_marked_legacy']:
        st.warning("Mẫu cuối có nhãn/kịch bản từ dữ liệu lịch sử; không coi là mẫu thật.")
    if not snap['latest_flows_valid']:
        st.error("Mẫu cuối có giá trị lưu lượng không hợp lệ.")
else:
    st.info("Chưa có bản ghi đo trong SQLite.")

st.subheader("Trạng thái AI / cảnh báo rò rỉ")
from tools.realtime_detection import artifacts_ready
reasons, _ = artifacts_ready()
if reasons:
    st.warning("AI chưa được phép phát cảnh báo rò rỉ (đúng trạng thái khi chưa có phần cứng).")
    with st.expander("Điều kiện còn thiếu"):
        for issue in reasons:
            st.write("- " + issue)
else:
    st.success("Tệp phê duyệt mô hình và phiên arming hợp lệ. Vẫn phải kiểm tra dữ liệu cảm biến mới trong pipeline.")
st.caption("Không tự khởi động AI từ giao diện. Bản tin mới không chứng minh nguồn vật lý.")

st.subheader("Dữ liệu lịch sử — chưa xác minh nguồn")
if st.checkbox("Cho phép xem dữ liệu lịch sử (không dùng làm bằng chứng thực nghiệm)"):
    data = pd.DataFrame(recent_history(DEFAULT_DB, limit=300))
    if data.empty:
        st.info("Chưa có dữ liệu để hiển thị.")
    else:
        data["ts_server"] = pd.to_datetime(data["ts_server"], utc=True, errors="coerce")
        for key in ("flow_main", "flow_z1", "flow_z2"):
            data[key] = pd.to_numeric(data[key], errors="coerce")
        data = data.dropna(subset=["ts_server", "flow_main", "flow_z1", "flow_z2"])
        if not data.empty:
            data["residual"] = data["flow_main"] - data["flow_z1"] - data["flow_z2"]
            st.line_chart(data.set_index("ts_server")[["flow_main", "flow_z1", "flow_z2"]])
            st.line_chart(data.set_index("ts_server")[["residual"]])
            st.caption("Residual không thể một mình khẳng định có rò rỉ hoặc định vị chính xác zone.")
