"""Read-only monitoring of optional CSV produced by monitor_mqtt_live.py."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.unified_dashboard_service import age_seconds, quality_log_snapshot

st.title("Chất lượng dữ liệu và kết nối")
st.caption("Nhật ký này là quan sát từ chương trình MQTT monitor, không phải xác thực nguồn vật lý.")

if st.button("Làm mới nhật ký"):
    st.rerun()

try:
    log = quality_log_snapshot(ROOT, limit=500)
except (OSError, UnicodeError, ValueError) as exc:
    st.error("Không thể đọc nhật ký chất lượng: " + str(exc))
    st.stop()

if log['path'] is None:
    st.info("Chưa có nhật ký MQTT. Hãy chạy monitor riêng; không cần bật fake_sensor.")
    st.code(r".\.venv\Scripts\python.exe tools\monitor_mqtt_live.py", language="powershell")
    st.stop()

st.caption("Nguồn: " + log['path'])
if not log['rows']:
    st.info("Có file log nhưng chưa có bản ghi.")
    st.stop()

rows = log['rows']
cols = st.columns(3)
cols[0].metric("Dòng nhật ký", len(rows))
cols[1].metric("Bản tin lỗi", log['counts'].get('invalid', 0))
cols[2].metric("Bản tin đánh dấu giả lập", log['counts'].get('marked_simulation', 0))
last = log['last']
latest_time = last.get('received_utc') or ''
lag = age_seconds(latest_time)
st.write("Log cuối: ", latest_time or "Không có thời gian")
if lag is not None and lag > 10:
    st.warning("Không có dòng log mới trong 10 giây. Chưa thể khẳng định ESP32 hay broker đã ngắt.")
if 'missing_samples_cumulative' in last:
    st.write("Thiếu chu kỳ đo theo số thứ tự (trong phiên monitor): ", last.get('missing_samples_cumulative') or '—')
st.dataframe(pd.DataFrame(rows[-200:]), use_container_width=True, hide_index=True)
st.caption("Mất chu kỳ đo không đồng nghĩa với mất gói riêng do MQTT. Dữ liệu đúng định dạng cũng không chứng minh là dữ liệu thật.")
