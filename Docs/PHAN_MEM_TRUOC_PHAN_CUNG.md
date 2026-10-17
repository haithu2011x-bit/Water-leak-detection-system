# Project II — Bàn giao phần mềm trước khi nhận phần cứng

## Trạng thái phạm vi

Cơ sở: ESP32-WROOM-32D, 3 YF-S401 (Main, Zone 1, Zone 2), bơm 12V.
**Không sử dụng cảm biến áp suất.** Topic: `building/water/node1/telemetry`.
Mọi dòng có `scenario/label` từ dữ liệu giả lập cũ không phải chứng cứ thực nghiệm.

### Phần có thể lập trình/kiểm thử ngay

- Firmware đo xung 3 flow sensor, ngắt, seq và boot_id, Wi-Fi/MQTT reconnect: đã có mã, chưa kiểm thử phần cứng thực.
- MQTT collector SQLite, schema v2, bảo toàn cột lịch sử, kiểm tra input và logging.
- Theo dõi MQTT và chất lượng dữ liệu, phân biệt gián đoạn chu kỳ với mất gói MQTT.
- Quản lý các phiên thí nghiệm có xác nhận người vận hành, xuất CSV có nguồn gốc.
- Alert Engine: chống trùng, nâng mức, xác nhận/đóng và nhật ký; không tự sinh cảnh báo.
- Dashboard hợp nhất: Tổng quan, lịch sử lưu lượng, MQTT quality, phiên thí nghiệm, cảnh báo.
- Pipeline AI chỉ hoạt động khi TẤT CẢ điều kiện phê duyệt dữ liệu/model + arming + chuỗi đo liên tiếp đạt.
- Chương trình huấn luyện Isolation Forest trên CSV **đã xuất từ các phiên thực nghiệm thật**; train/validation phân tách theo experiment_id.
- Đánh giá holdout REAL riêng cho bình thường/rò rỉ; tạo báo cáo, không tự cấp quyền vận hành.
- Sao lưu SQLite online bằng SQLite Backup API; không ghi đè backup hoặc DB nguồn.
- Lệnh khởi chạy phần mềm một lần và CI kiểm thử Windows/Linux.

### KHÔNG thể xác nhận khi chưa có phần cứng

- Mức điện áp xung YF-S401 vào GPIO (phải bảo vệ ở mức 3.3V), hướng dòng chảy, bơm/van/ống an toàn, đường nối mass chung.
- Hiệu chuẩn xung/lít từng cảm biến với nước thật và thể tích chuẩn; đo ở nhiều mức lưu lượng trong **0.3–6 L/min**.
- Kiểm tra độ trễ thực, gói MQTT khi Wi-Fi yếu, khởi động lại và giữ số thứ tự mẫu.
- Thu thập dữ liệu đủ đa dạng các chế độ **normal** và **leak** qua nhiều phiên độc lập.
- Train/validation/test theo PHIÊN riêng; đánh giá precision, recall, F1, false alarms, latency và nhầm zone trên holdout thật.
- Kiểm chứng định vị: rò sau đồng hồ nhánh vẫn có thể giữ `Main ≈ Zone1 + Zone2`; residual riêng lẻ không chứng minh rò. Zone hiện là **nghi ngờ**, không phải vị trí chính xác.
- Bảo mật MQTT khi kết nối ngoài LAN: xác thực broker, mạng riêng, hạn chế thiết bị lạ. `device_id/boot_id` chỉ là metadata chẩn đoán.

## Khởi chạy (Windows, sau khi clone)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
# Start Mosquitto service before launching collector:
.\.venv\Scripts\python.exe tools\run_local.py --port 8501 --monitor
```

Truy cập `http://localhost:8501`. Dừng bằng Ctrl+C.
Không chạy `backend/fake_sensor.py` để tạo dữ liệu huấn luyện/thí nghiệm.
Trong lúc chờ hàng: Dashboard có thể trống hoặc hiển thị dữ liệu lịch sử **chưa xác minh**.

Nếu Dashboard 8501 cũ đang chạy, hãy dừng nó trước khi khởi chạy chương trình mới; có thể dùng `--port 8504` để chạy song song.

### Sao lưu trước khi thí nghiệm/migrate schema

```powershell
.\.venv\Scripts\python.exe tools\backup_sqlite.py
```

Bản sao nằm dưới `data/backups/` và được Git bỏ qua. Định kỳ sao lưu ra ổ khác; kiểm tra `integrity_check` đã được tự động thực hiện.
Khôi phục thủ công: **dừng Collector/Dashboard**, sao lưu thêm DB hiện hành, sau đó mới thay bằng DB snapshot đã kiểm chứng. Công cụ không tự khôi phục và không tự xóa dữ liệu.

## Cách AI được chuẩn bị, nhưng CHƯA kích hoạt

Kiểm tra trạng thái không làm thay đổi database:

```powershell
.\.venv\Scripts\python.exe tools\realtime_detection.py --mode check
```

Kết quả `NOT READY` là **đúng** trước khi có dữ liệu thật. Dù còn file mô hình demo `ai/iforest.joblib`, nó vẫn bị khóa vì metadata chưa chứng nhận xuất xứ REAL và thiếu phê duyệt.

Sau khi hoàn tất hiệu chuẩn/thu thập đo thật:

1. Xuất CSV từ giao diện Phiên thí nghiệm. Kiểm tra bằng chứng nguồn vật lý bằng nhật ký, ảnh/sơ đồ, kiểm tra thiết bị ngoài phần mềm. Trường `real_operator_confirmed` **chỉ là người vận hành xác nhận**, không phải chữ ký hay xác thực MQTT.
2. Chuẩn bị **ít nhất 3 nhóm phiên khác nhau**: (a) normal training, (b) normal validation, (c) real normal + leak HOLDOUT; không dùng chung `experiment_id`.
3. Huấn luyện candidate trên các phiên normal thực:

```powershell
.\.venv\Scripts\python.exe ai\train_real.py --train data\real_exports\train_N1.csv data\real_exports\train_N2.csv --validation data\real_exports\valid_N3.csv
```

Đường dẫn ở trên là **ví dụ**, không phải tên file mặc định sẵn có. Model được lưu `ai/iforest_real_candidate.joblib` và `ai/iforest_real_candidate_meta.json`; không tự ghi đè mô hình demo.
4. Đánh giá trên **phiên holdout độc lập** của cả normal và leak:

```powershell
.\.venv\Scripts\python.exe ai\evaluate_real.py --holdout data\real_exports\holdout_N4.csv data\real_exports\holdout_L1.csv --output data\real_exports\holdout_report.json
```

5. Người thực hiện đọc báo cáo sai số, kiểm tra hiệu suất/zone và bằng chứng rồi mới quyết định có phê duyệt không. Sau khi duyệt thủ công, chép **candidate thật** sang `ai/iforest.joblib`, `ai/iforest_meta.json`; ghi SHA256 của hai file và dẫn nguồn kết quả kiểm thử vào `config/model_approval.json` (mẫu `config/model_approval.example.json`).
6. Khi đo từ ESP32 vật lý và đã bảo đảm dừng fake_sensor, tạo `config/runtime_arming.json` từ `config/runtime_arming.example.json`, điền người xác nhận và hạn tối đa 24 giờ. Mỗi phiên arming phải được người vận hành xác nhận ngoài thực địa; file này **không phải xác thực thiết bị**.
7. Lệnh `--mode watch` chỉ được phép sau khi cả hai file và chuỗi 10 mẫu ESP32 v2 thỏa điều kiện. Cảnh báo yêu cầu >=3 mẫu có điểm bất thường liên tiếp, hiển thị **nghi rò rỉ** và zone nghi ngờ, không kết luận chắc chắn.

**Không tạo phê duyệt model hoặc arming khi chưa có phần cứng và kết quả thực nghiệm.** Cả 2 JSON thật đều nằm trong `.gitignore`.

## Kiểm thử/nghiệm thu phần mềm

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe tools\check_system.py
.\.venv\Scripts\python.exe tools\check_mqtt_broker.py
.\.venv\Scripts\python.exe tools\realtime_detection.py --mode check
```

- Unit tests dùng SQLite tạm; không đào tạo AI hoặc tạo data giả để báo cáo hiệu suất.
- MQTT diagnostic chỉ dùng topic riêng, không bắn telemetry vào Collector.
- Streamlit cần được người dùng kiểm tra thao tác thật trên Windows; CI không thay thế nghiệm thu thiết bị.

## An toàn trước khi bảo vệ đồ án

Trình bày rõ **chức năng đã lập trình** và **chức năng đã thử nghiệm vật lý**. Chưa thể nói phát hiện sớm, định vị chính xác, hoặc đo precision/recall thực tế trước giai đoạn thử nghiệm và hiệu chuẩn.
