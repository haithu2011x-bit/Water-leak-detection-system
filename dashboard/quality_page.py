import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.ui import (RESIDUAL_COLOR, apply_theme, empty_state,
                          page_header, section_title, status_chip)
from dashboard.data_filters import filter_quality_log
from tools.unified_dashboard_service import age_seconds, quality_log_snapshot

apply_theme()
page_header(
    "Chất lượng dữ liệu & kết nối",
    "Theo dõi nhật ký MQTT, bản tin lỗi, mẫu đánh dấu giả lập và các dấu hiệu gián đoạn trong chuỗi telemetry.",
)

top = st.columns([1, 4])
with top[0]:
    if st.button("Làm mới", use_container_width=True):
        st.rerun()

try:
    log = quality_log_snapshot(ROOT, limit=1000)
except (OSError, UnicodeError, ValueError) as exc:
    st.error(f"Không thể đọc nhật ký chất lượng: {exc}")
    st.stop()

if log["path"] is None:
    empty_state("Chưa có nhật ký giám sát", "Chạy tools/monitor_mqtt_live.py để bắt đầu ghi nhận chất lượng bản tin MQTT.")
    st.code(r".\.venv\Scripts\python.exe tools\monitor_mqtt_live.py", language="powershell")
    st.stop()

rows = log["rows"]
st.caption(f"Nguồn nhật ký: {log['path']}")
if not rows:
    empty_state("Nhật ký chưa có bản ghi", "File đã tồn tại nhưng chưa ghi nhận được mẫu nào.")
    st.stop()

df = pd.DataFrame(rows)
last = log["last"] or {}
latest_time = last.get("received_utc") or ""
lag = age_seconds(latest_time)
kinds = df["kind"].fillna("unknown").astype(str) if "kind" in df else pd.Series(["unknown"] * len(df))
invalid_count = int((kinds == "invalid").sum())
sim_count = int((kinds == "marked_simulation").sum())
valid_count = int((kinds == "format_esp32").sum())

metrics = st.columns(5)
metrics[0].metric("Dòng nhật ký", f"{len(df):,}")
metrics[1].metric("Bản tin đúng định dạng", f"{valid_count:,}")
metrics[2].metric("Bản tin lỗi", f"{invalid_count:,}")
metrics[3].metric("Đánh dấu giả lập", f"{sim_count:,}")
metrics[4].metric("Mẫu thiếu tích lũy", last.get("missing_samples_cumulative", "—"))

section_title("Trạng thái giám sát", "Thông tin theo bản ghi cuối trong file log")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Thời điểm nhận gần nhất**")
    st.write(latest_time or "Không có thời gian")
    if lag is None:
        status_chip("Chưa xác định", "neutral")
    elif lag <= 10:
        status_chip("Log mới", "good")
    else:
        status_chip("Log đã cũ", "warn")
with c2:
    st.markdown("**Bản tin gần nhất**")
    status_chip(str(last.get("kind", "unknown")), "good" if last.get("kind") == "format_esp32" else "warn")
    st.write(last.get("problems") or "Không ghi nhận lỗi định dạng ở mẫu cuối.")
with c3:
    st.markdown("**Theo dõi chuỗi mẫu**")
    st.write(f"Thiếu mẫu tích lũy: {last.get('missing_samples_cumulative', '—')}")
    st.write(f"Boot ID: {last.get('boot_id', '—')} · Seq: {last.get('seq', '—')}")

if lag is not None and lag > 10:
    st.warning("Không có dòng log mới trong hơn 10 giây. Đây là dấu hiệu cần kiểm tra, chưa đủ để kết luận ESP32 hoặc broker đã ngắt.")
if invalid_count:
    st.warning(f"Nhật ký hiện có {invalid_count} bản tin lỗi định dạng. Nên kiểm tra payload và firmware gửi dữ liệu.")
if sim_count:
    st.info(f"Có {sim_count} bản tin được đánh dấu mô phỏng; không dùng chúng làm bằng chứng thực nghiệm.")

section_title("Nhật ký bản tin", "Lọc theo loại và tìm kiếm nội dung")
filter_col, search_col = st.columns([1, 2])
with filter_col:
    kind_options = sorted(kinds.unique().tolist())
    selected_kinds = st.multiselect("Loại bản tin", kind_options, default=kind_options)
with search_col:
    query = st.text_input("Tìm trong nhật ký", placeholder="Ví dụ: seq, JSON, timeout, flow_z1")

filtered = filter_quality_log(df, selected_kinds, query)

if "received_utc" in filtered.columns:
    filtered["received_utc"] = pd.to_datetime(filtered["received_utc"], utc=True, errors="coerce")
    chart_source = filtered.dropna(subset=["received_utc"]).copy()
    if "missing_samples_cumulative" in chart_source:
        chart_source["missing_samples_cumulative"] = pd.to_numeric(chart_source["missing_samples_cumulative"], errors="coerce")
        chart_source = chart_source.dropna(subset=["missing_samples_cumulative"])
        if not chart_source.empty:
            st.markdown("**Số mẫu thiếu tích lũy theo thời gian**")
            st.line_chart(chart_source.set_index("received_utc")[["missing_samples_cumulative"]], height=240, color=RESIDUAL_COLOR)

st.dataframe(filtered.tail(300).iloc[::-1], use_container_width=True, hide_index=True, height=390)
st.download_button(
    "Xuất nhật ký CSV",
    data=filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name="mqtt_quality_log.csv",
    mime="text/csv",
)
st.caption("Số mẫu thiếu theo seq không đồng nghĩa chắc chắn với mất gói MQTT. Bản tin đúng định dạng cũng không tự xác thực nguồn ESP32 vật lý.")
