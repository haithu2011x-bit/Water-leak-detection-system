# Water Leak Detection System — Project II

Hệ thống IoT–AI thử nghiệm phát hiện sớm và gợi ý **zone nghi ngờ rò rỉ nước** trên mô hình đường ống 2 nhánh. Sử dụng **3 cảm biến lưu lượng YF-S401** (Main, Zone 1, Zone 2), **không dùng cảm biến áp suất**.

## Kiến trúc

ESP32 → Wi-Fi / MQTT (Mosquitto) → Python Collector → SQLite → Dashboard.

Nhánh xử lý AI thử nghiệm: dữ liệu có nhãn → feature engineering → Isolation Forest → đánh giá. Giao diện cảnh báo sử dụng Alert Engine độc lập; chỉ kích hoạt cảnh báo phát hiện rò rỉ thực tế sau khi mô hình được kiểm chứng bằng dữ liệu đo thật.

## Cấu trúc thư mục

- `firmware/water_node/water_node.ino`: chương trình ESP32.
- `backend/collector.py`: nhận MQTT và lưu SQLite.
- `backend/fake_sensor.py`: dữ liệu **giả lập**, chỉ phục vụ kiểm thử phần mềm.
- `dashboard/app.py`: xem lưu lượng, lịch sử.
- `dashboard/experiment_app.py`: quản lý phiên thí nghiệm.
- `dashboard/alerts_app.py`: quản lý cảnh báo.
- `ai/`: xử lý feature, huấn luyện, đánh giá thử nghiệm.
- `tools/`: kiểm tra dữ liệu, quản lý cảnh báo/thí nghiệm, hiệu chuẩn và giám sát kết nối.
- `tests/`: bài kiểm thử tự động.
- `Docs/`: quy trình, kế hoạch và tài liệu kỹ thuật.

## Cài đặt trên Windows (PowerShell)

Yêu cầu: Python 3.13 (hoặc phiên bản tương thích), Git, Mosquitto; Arduino IDE và thư viện ESP32/PubSubClient để biên dịch firmware.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

### Chạy ứng dụng

Khởi động Mosquitto trước. Chạy các lệnh sau trong các Terminal khác nhau, tại thư mục gốc của dự án:

```powershell
.\.venv\Scripts\python.exe backend\collector.py
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501
.\.venv\Scripts\python.exe -m streamlit run dashboard\experiment_app.py --server.port 8502
.\.venv\Scripts\python.exe tools\alert_cli.py init
.\.venv\Scripts\python.exe -m streamlit run dashboard\alerts_app.py --server.port 8503
```

Các trang chạy trên máy cục bộ tại `http://localhost:8501`, `:8502`, `:8503`. Không cần bật mọi trang cùng lúc.

## Firmware và dữ liệu thực

Mở `firmware/water_node/water_node.ino` trong Arduino IDE. Firmware hiện ở **chế độ hiệu chuẩn**; cần hiệu chuẩn hệ số xung/lít cho từng YF-S401, kiểm tra an toàn điện áp GPIO 3,3 V và cấu hình Wi-Fi/MQTT trước khi gửi dữ liệu thật.

Dữ liệu giả lập, mô hình huấn luyện demo và kết quả đánh giá trên dữ liệu giả **không phải bằng chứng hiệu suất trên hệ thống thật**. Chỉ sử dụng dữ liệu đã ghi nguồn gốc và nhật ký thí nghiệm để huấn luyện, đánh giá thực tế.

## Quản lý dữ liệu và bảo mật

`data/water.db`, dữ liệu giám sát, mô hình `.joblib`, file `.env` và các khóa/mật khẩu cá nhân không đưa vào Git. SQLite sẽ được tạo/cập nhật bởi chương trình khi chạy; các bài kiểm thử phần lớn sử dụng cơ sở dữ liệu tạm, không cần sao chép bộ dữ liệu giả lập cũ.

Tài liệu chi tiết xem trong `Docs/`.


## Bản phần mềm tích hợp trước phần cứng

**Hướng dẫn chuẩn mới:** [Docs/PHAN_MEM_TRUOC_PHAN_CUNG.md](Docs/PHAN_MEM_TRUOC_PHAN_CUNG.md).

Sau khi cài đặt thư viện và bật Mosquitto trên máy, có thể khởi động Collector + Dashboard hợp nhất + monitor chất lượng MQTT bằng một lệnh:

```powershell
.\.venv\Scripts\python.exe tools\run_local.py --port 8501 --monitor
```

Dashboard hợp nhất gồm Tổng quan, biểu đồ lưu lượng, chất lượng MQTT, quản lý thí nghiệm, Alert Engine. Các giao diện Streamlit riêng trước đây vẫn được giữ để tương thích ngược. Nếu cổng 8501 đang bị dùng, đóng ứng dụng trước hoặc chạy `--port 8504`.

### Bảo vệ kết quả đồ án

- **Không có phần cứng = không có phép đo hiệu suất thực**. Mô hình Isolation Forest demo trong lịch sử không được phép tạo cảnh báo vận hành thực.
- `tools/realtime_detection.py --mode check` dùng để kiểm tra các điều kiện kích hoạt; trước khi hiệu chuẩn và phê duyệt thật, kết quả **NOT READY** là đúng.
- `ai/train_real.py` và `ai/evaluate_real.py` chỉ chạy sau khi có các CSV phiên đo thật, độc lập; không tự phê duyệt mô hình.
- `tools/backup_sqlite.py` sao lưu nhất quán, không xóa hay ghi đè database cũ.
- GitHub Actions tự kiểm thử Windows/Linux, Python 3.13; thử nghiệm vật lý và đánh giá khả năng định vị vẫn là bước bắt buộc.

Các file phê duyệt thực tế và cấu hình kích hoạt được bỏ qua bằng `.gitignore`; chỉ các bản `.example.json` an toàn được đưa lên Git.
