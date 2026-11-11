import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import apply_theme, empty_state, page_header, section_title, status_chip
from tools.experiment_log import SCENARIOS
from tools.experiment_service import (
    DEFAULT_DB, list_sessions, sample_rows, session_quality, start_session,
    stop_session, stream_status, summary, export_verified_session_csv,
)

apply_theme()
page_header(
    "Quản lý phiên thí nghiệm",
    "Thiết lập kịch bản, ghi nhận điều kiện vận hành, theo dõi chất lượng mẫu và xuất bộ dữ liệu của từng lần thử.",
    tag="EXPERIMENT WORKSPACE",
)

try:
    info = summary(DEFAULT_DB)
    stream = stream_status(DEFAULT_DB)
    sessions = list_sessions(DEFAULT_DB, limit=250)
except Exception as exc:
    st.error(f"Không đọc được dữ liệu thí nghiệm: {exc}")
    st.code(r".\.venv\Scripts\python.exe tools\experiment_log.py init", language="powershell")
    st.stop()

active = info["active"]
kpis = st.columns(4)
kpis[0].metric("Tổng telemetry", f"{info['total']:,}")
kpis[1].metric("Mẫu có nhãn lịch sử", f"{info['tagged_history']:,}")
kpis[2].metric("Tổng phiên", f"{len(sessions):,}")
kpis[3].metric("Phiên đang ghi", active["scenario_code"] if active else "Không có")

status_col, refresh_col = st.columns([4, 1])
with status_col:
    if stream["ready"]:
        status_chip("Có luồng ESP32 v2 mới đúng cấu trúc", "good")
        st.caption("Đây chỉ là kiểm tra định dạng và độ mới, không phải xác thực nguồn vật lý.")
    else:
        status_chip("Chưa đủ điều kiện bắt đầu phiên REAL", "warn")
        st.caption(" ".join(stream["reasons"][:3]))
with refresh_col:
    if st.button("↻ Làm mới", use_container_width=True):
        st.rerun()

tabs = st.tabs(["Tổng quan", "Phiên đo", "Lịch sử & chất lượng", "Danh mục kịch bản"])

with tabs[0]:
    section_title("Trạng thái thu thập", "Tóm tắt luồng dữ liệu gần nhất")
    a, b = st.columns(2)
    with a:
        st.markdown("**Bản ghi cuối cùng**")
        st.write(info["latest"] or "Chưa có bản ghi")
        st.write(f"Mã bản ghi mới nhất: **{stream['latest_id'] or '—'}**")
    with b:
        st.markdown("**Phiên hiện tại**")
        if active:
            st.warning(f"Đang mở phiên #{active['id']} · {active['scenario_code']}")
            st.write(active["start_utc"])
            st.caption(active.get("start_note") or "Không có ghi chú bắt đầu.")
        else:
            st.info("Hiện không có phiên thí nghiệm đang chạy.")
    st.markdown(
        '<div class="soft-note">Một phiên chỉ được ghi nhận là REAL khi luồng ESP32 v2 đáp ứng điều kiện kiểm tra, '
        'người vận hành xác nhận đã dừng fake_sensor và dữ liệu được ghi trong khoảng thời gian của phiên.</div>',
        unsafe_allow_html=True,
    )
    section_title("Các bước vận hành")
    flow = st.columns(4)
    for col, number, heading, detail in [
        (flow[0], "01", "Kiểm tra luồng", "Kiểm tra ESP32 v2 và thời gian nhận mẫu."),
        (flow[1], "02", "Chọn kịch bản", "Chọn trạng thái van, nhánh và điều kiện đo."),
        (flow[2], "03", "Ghi phiên", "Bắt đầu, ghi chú và kết thúc phiên đo."),
        (flow[3], "04", "Đánh giá", "Kiểm tra chất lượng và xuất CSV hợp lệ."),
    ]:
        with col:
            st.markdown(
                f'<div style="background:#fff;border:1px solid #e5ebf3;border-radius:14px;padding:15px;min-height:135px">'
                f'<div style="color:#2868d7;font-size:.76rem;font-weight:800">{number}</div>'
                f'<div style="font-weight:750;color:#17243b;margin:8px 0 5px">{heading}</div>'
                f'<div style="font-size:.82rem;color:#68778f;line-height:1.45">{detail}</div></div>',
                unsafe_allow_html=True,
            )
    section_title("Phiên gần đây")
    if sessions:
        recent = pd.DataFrame(sessions[:8])
        cols = [c for c in ["id", "scenario_code", "label", "zone", "start_utc", "end_utc"] if c in recent]
        st.dataframe(recent[cols], use_container_width=True, hide_index=True)
    else:
        empty_state("Chưa có phiên thí nghiệm", "Các phiên được lưu tại đây sau khi bắt đầu trên luồng ESP32 đã được kiểm tra.")

with tabs[1]:
    section_title("Điều khiển phiên", "Mỗi thời điểm chỉ cho phép một phiên đang mở")
    if active:
        st.markdown(
            f'<div class="soft-note"><b>Đang ghi phiên #{active["id"]} · {active["scenario_code"]}</b><br>'
            f'Bắt đầu lúc: {active["start_utc"]}<br>Ghi chú: {active.get("start_note") or "—"}</div>',
            unsafe_allow_html=True,
        )
        with st.form("stop_form", clear_on_submit=True):
            end_note = st.text_area("Ghi chú kết thúc", placeholder="Trạng thái van/bơm, điều kiện đo, sự cố...")
            submitted_stop = st.form_submit_button("Kết thúc phiên", type="primary", use_container_width=True)
        if submitted_stop:
            try:
                session_id = stop_session(end_note)
                st.success(f"Đã kết thúc phiên #{session_id}. Telemetry gốc không bị chỉnh sửa.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    else:
        with st.form("start_form", clear_on_submit=True):
            code = st.selectbox(
                "Kịch bản thực nghiệm",
                list(SCENARIOS),
                format_func=lambda key: f"{key} · {SCENARIOS[key][2]}",
            )
            note = st.text_area("Ghi chú bắt đầu", placeholder="Van đang mở/đóng, trạng thái bơm, vị trí điểm rò...")
            confirm = st.checkbox(
                "Tôi đã dừng fake_sensor, đang nhận dữ liệu từ ESP32 thật và đồng hồ máy tính đúng giờ."
            )
            submitted_start = st.form_submit_button(
                "Bắt đầu phiên REAL", type="primary",
                disabled=(not stream["ready"] or not confirm), use_container_width=True,
            )
        if submitted_start:
            try:
                session_id = start_session(code, note, confirm_real=confirm)
                st.success(f"Đã bắt đầu phiên #{session_id}.")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if not stream["ready"]:
            st.warning("Nút bắt đầu đang khóa vì luồng dữ liệu chưa vượt qua kiểm tra cấu trúc/độ mới.")
    section_title("Danh sách phiên đã ghi")
    if sessions:
        view = pd.DataFrame(sessions)
        state_filter = st.selectbox("Trạng thái phiên", ["Tất cả", "Đang chạy", "Đã kết thúc"], key="session_state")
        if state_filter == "Đang chạy":
            view = view[view["end_utc"].isna()]
        elif state_filter == "Đã kết thúc":
            view = view[view["end_utc"].notna()]
        st.dataframe(view, use_container_width=True, hide_index=True, height=340)
        st.download_button(
            "↓ Xuất danh sách phiên CSV",
            data=view.to_csv(index=False).encode("utf-8-sig"),
            file_name="experiment_sessions.csv",
            mime="text/csv",
        )
    else:
        empty_state("Chưa có phiên nào", "Bắt đầu một phiên REAL sau khi kết nối và xác nhận ESP32.")

with tabs[2]:
    section_title("Phân tích chất lượng phiên", "Chỉ đọc dữ liệu trong phiên đã chọn")
    if not sessions:
        empty_state("Chưa có dữ liệu phiên", "Sau khi hoàn thành phiên đo, các chỉ số chất lượng sẽ xuất hiện tại đây.")
    else:
        options = {int(s["id"]): s for s in sessions}
        sid = st.selectbox(
            "Chọn phiên",
            list(options),
            format_func=lambda key: f"#{key} · {options[key]['scenario_code']} · {options[key]['start_utc']}",
            key="quality_session",
        )
        selected = options[sid]
        q = session_quality(session_id=sid)
        metrics = st.columns(5)
        metrics[0].metric("Số mẫu", f"{q['loaded']:,}")
        metrics[1].metric("Khoảng ngắt >2,5 s", q["gaps_over_2_5s"])
        metrics[2].metric("Dòng lỗi", q["invalid_rows"])
        metrics[3].metric("Dưới dải đo", q["below_range_readings"])
        metrics[4].metric("Trên dải đo", q["above_range_readings"])
        if q["mean_abs_residual"] is not None:
            st.metric("Residual tuyệt đối trung bình", f"{q['mean_abs_residual']:.3f} L/min")
        rows = sample_rows(session_id=sid, limit=10000)
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["ts_server"] = pd.to_datetime(frame["ts_server"], utc=True, errors="coerce")
            frame = frame.dropna(subset=["ts_server"])
            st.markdown("**Diễn biến ba kênh lưu lượng**")
            st.line_chart(frame.set_index("ts_server")[["flow_main", "flow_z1", "flow_z2"]], height=300)
            frame["residual"] = frame["flow_main"] - frame["flow_z1"] - frame["flow_z2"]
            st.markdown("**Sai lệch cân bằng lưu lượng**")
            st.line_chart(frame.set_index("ts_server")[["residual"]], height=190)
            with st.expander("Xem dữ liệu chi tiết"):
                st.dataframe(frame.tail(500).iloc[::-1], use_container_width=True, hide_index=True)
        if q["limit_reached"]:
            st.warning("Đã chạm giới hạn đọc 10.000 mẫu cuối của phiên.")
        if selected["end_utc"]:
            try:
                csv_data = export_verified_session_csv(session_id=sid)
                st.download_button(
                    "↓ Xuất bộ dữ liệu phiên đã hoàn tất",
                    data=csv_data,
                    file_name=f"projectII_experiment_{sid}.csv",
                    mime="text/csv",
                    type="primary",
                )
                st.caption("CSV chỉ xuất khi phiên đã hoàn tất và vượt qua các kiểm tra dữ liệu REAL trong backend.")
            except (ValueError, OSError) as exc:
                st.warning(f"Chưa thể xuất phiên này: {exc}")
        else:
            st.info("Kết thúc phiên trước khi xuất CSV.")
        st.caption("Residual và các chỉ số chất lượng không tự chứng minh có rò rỉ hoặc xác nhận vị trí rò.")

with tabs[3]:
    section_title("Danh mục kịch bản", "Các mã kịch bản được định nghĩa trong experiment_log.py")
    scenario_rows = [
        {"Mã": key, "Nhãn": values[0], "Zone": values[1], "Mô tả": values[2]}
        for key, values in SCENARIOS.items()
    ]
    st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)
    st.caption("Kịch bản là cấu hình ghi nhận thí nghiệm; kết quả phải được đo từ phần cứng và kiểm tra độc lập.")
