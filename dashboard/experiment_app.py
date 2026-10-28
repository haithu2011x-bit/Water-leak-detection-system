import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.experiment_log import SCENARIOS
from tools.experiment_service import (
    DEFAULT_DB, list_sessions, sample_rows, session_quality, start_session,
    stop_session, stream_status, summary, export_verified_session_csv,
)

st.set_page_config(page_title="Project II | Nhật ký thí nghiệm", page_icon="💧", layout="wide")
st.title("Project II · Thu thập và quản lý dữ liệu")
st.caption("3 YF-S401 · 2 Zone · MQTT / SQLite · Không có cảm biến áp suất · Không chạy AI")
st.info("Dữ liệu lịch sử có thể là giả lập. Giao diện KHÔNG tự xem bản tin mới là dữ liệu cảm biến thật. Chỉ xác nhận phiên REAL khi đã kết nối và kiểm tra ESP32.")

try:
    info = summary(DEFAULT_DB)
    stream = stream_status(DEFAULT_DB)
    sessions = list_sessions(DEFAULT_DB)
except Exception as exc:
    st.error(f"Không đọc được dữ liệu: {exc}")
    st.code(r".\.venv\Scripts\python.exe tools\experiment_log.py init", language="powershell")
    st.stop()

metrics = st.columns(4)
metrics[0].metric("Bản ghi trong database", f"{info['total']:,}")
metrics[1].metric("Có nhãn từ chương trình cũ", f"{info['tagged_history']:,}")
metrics[2].metric("Phiên thí nghiệm", len(sessions))
metrics[3].metric("Phiên đang chạy", info["active"]["scenario_code"] if info["active"] else "Không có")
if stream["ready"]:
    st.success("Có bản tin mới đúng cấu trúc ESP32. Đây chỉ là kiểm tra định dạng và độ mới; không tự xác minh nguồn vật lý.")
else:
    st.warning("Chưa đủ điều kiện bắt đầu phiên REAL. " + " ".join(stream["reasons"][:2]))
if st.button("Tải lại dữ liệu"):
    st.rerun()

tab_overview, tab_sessions, tab_history, tab_guide = st.tabs([
    "Tổng quan", "Phiên thí nghiệm", "Lịch sử & chất lượng", "Hướng dẫn"
])

with tab_overview:
    st.subheader("Dữ liệu và trạng thái")
    st.write("Bản ghi mới nhất (UTC):", info["latest"] or "Chưa có")
    st.write("Bản ghi mới nhất có mã ID:", stream["latest_id"] or "Chưa có")
    st.caption("Để tránh dùng nhầm dữ liệu giả, biểu đồ REAL chỉ hiển thị theo một phiên đã được người thực hiện xác nhận.")
    available = [x for x in sessions if x["source"] == "real"]
    if available:
        ids = [s["id"] for s in available]
        selected = st.selectbox("Chọn phiên để xem biểu đồ", ids,
                                format_func=lambda sid: next(f"#{x['id']} · {x['scenario_code']} · {x['start_utc']}" for x in available if x['id'] == sid),
                                key="overview_session")
        rows = sample_rows(session_id=selected, limit=1500)
        if rows:
            frame = pd.DataFrame(rows)
            frame["ts_server"] = pd.to_datetime(frame["ts_server"], utc=True, errors="coerce")
            frame = frame.dropna(subset=["ts_server"])
            st.line_chart(frame.set_index("ts_server")[["flow_main", "flow_z1", "flow_z2"]])
            frame["residual"] = frame["flow_main"] - frame["flow_z1"] - frame["flow_z2"]
            st.line_chart(frame.set_index("ts_server")[["residual"]])
            st.caption("Residual chỉ là chênh lệch lưu lượng, không tự kết luận rò rỉ. Hiển thị tối đa 1.500 bản ghi cuối của phiên.")
        else:
            st.info("Phiên này chưa có mẫu đo trong khoảng thời gian ghi nhận.")
    else:
        st.info("Chưa có phiên dữ liệu thật được xác nhận. Bạn có thể dùng giao diện này ngay để kiểm tra bố cục; biểu đồ thực sẽ có khi kết nối ESP32.")

with tab_sessions:
    st.subheader("Quản lý phiên thử nghiệm")
    active = info["active"]
    if active:
        st.warning(f"Đang ghi phiên #{active['id']} – {active['scenario_code']} (bắt đầu {active['start_utc']} UTC)")
        with st.form("stop_form"):
            end_note = st.text_area("Ghi chú kết thúc (trạng thái van/bơm, sự cố, điều kiện đo)")
            submitted_stop = st.form_submit_button("Kết thúc phiên đang chạy")
        if submitted_stop:
            try:
                session_id = stop_session(end_note)
                st.success(f"Đã kết thúc phiên #{session_id}; không sửa telemetry.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    else:
        with st.form("start_form"):
            code = st.selectbox("Mã tình huống thực nghiệm", list(SCENARIOS),
                                format_func=lambda s: f"{s} · {SCENARIOS[s][2]}")
            note = st.text_area("Ghi chú bắt đầu: van, bơm, vị trí điểm rò, điều kiện đo")
            confirm = st.checkbox("Tôi xác nhận đã dừng fake_sensor, đang nhận dữ liệu từ ESP32 thật và đồng hồ máy tính đúng giờ")
            submitted_start = st.form_submit_button("Bắt đầu phiên REAL", disabled=not stream["ready"])
        if submitted_start:
            try:
                session_id = start_session(code, note, confirm_real=confirm)
                st.success(f"Đã bắt đầu phiên #{session_id}.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if not stream["ready"]:
            st.caption("Nút bắt đầu được khóa khi chưa có bản tin mới thỏa định dạng. Không cần tạo dữ liệu giả để mở khóa.")

    st.subheader("Danh sách phiên")
    if sessions:
        st.dataframe(pd.DataFrame(sessions)[["id", "scenario_code", "label", "zone", "source", "start_utc", "end_utc", "start_note", "end_note"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có phiên nào. Danh sách sẽ được cập nhật khi có phần cứng và bạn bắt đầu phiên đo.")

with tab_history:
    st.subheader("Kiểm tra lịch sử đo và chất lượng dữ liệu")
    if sessions:
        sid = st.selectbox("Chọn phiên đo", [x["id"] for x in sessions],
                           format_func=lambda x: f"Phiên #{x}", key="history_session")
        q = session_quality(session_id=sid)
        c = st.columns(4)
        c[0].metric("Mẫu đã đọc", q["loaded"])
        c[1].metric("Khoảng ngắt >2,5 s", q["gaps_over_2_5s"])
        c[2].metric("Dòng dữ liệu lỗi", q["invalid_rows"])
        c[3].metric("|Residual| trung bình", f"{q['mean_abs_residual']:.3f} L/min" if q["mean_abs_residual"] is not None else "—")
        st.caption(f"Số giá trị dưới 0,3 L/phút (nhưng >0): {q['below_range_readings']} · Trên 6 L/phút: {q['above_range_readings']}. Đếm theo giá trị cảm biến, không phải số dòng.")
        if q["limit_reached"]:
            st.warning("Mới kiểm tra 10.000 bản ghi cuối của phiên. Hãy chia nhỏ nếu phiên dài.")
        rows = sample_rows(session_id=sid, limit=1000)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có bản ghi cho phiên này.")
        selection = next(x for x in sessions if x["id"] == sid)
        if selection["end_utc"]:
            try:
                blob = export_verified_session_csv(session_id=sid)
                st.download_button("Tải CSV của phiên đã hoàn tất", data=blob,
                                   file_name=f"projectII_experiment_{sid}.csv", mime="text/csv")
                st.caption("CSV có nguồn real_operator_confirmed (xác nhận của người vận hành), không phải xác thực thiết bị tự động.")
            except (ValueError, OSError) as exc:
                st.warning(f"Chưa thể xuất CSV của phiên này: {exc}")
        else:
            st.caption("Chỉ xuất CSV sau khi kết thúc phiên.")
    else:
        st.info("Chưa có dữ liệu thực nghiệm đã xác nhận. Không có kết quả giả tạo.")
        show_unverified = st.checkbox("Xem tối đa 100 mẫu lịch sử chưa xác minh (chỉ kiểm tra giao diện)")
        if show_unverified:
            st.warning("Những mẫu dưới đây có thể là dữ liệu giả lập, KHÔNG được dùng làm kết quả thực nghiệm thật.")
            st.dataframe(pd.DataFrame(sample_rows(limit=100)), use_container_width=True, hide_index=True)

