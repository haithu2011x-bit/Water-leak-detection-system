# Đặc tả giao tiếp dữ liệu — phiên bản flow-only v1

## Phạm vi cố định

- 1 ESP32-WROOM-32, 3 cảm biến YF-S401: Main / Zone 1 / Zone 2.
- **Không có pressure sensor.** Máy bơm DC định mức ~2 L/phút.
- Dải đo YF-S401 người thực hiện đã kiểm tra: **0,3–6 L/phút**; dữ liệu đo ngoài dải không được coi là chính xác nếu chưa kiểm chứng.
- Không dùng cảm biến phụ để đo nhu cầu sử dụng hợp lệ; chỉ có 3 flow — cần công bố giới hạn phân biệt leak với demand.

## MQTT

- Topic giữ nguyên để tương thích code đang chạy: `building/water/node1/telemetry`
- Broker: Mosquitto trên laptop, trong LAN; port 1883 khi test cục bộ. Khi kết nối qua Wi-Fi từ ESP32, dùng **IP LAN của laptop**, không dùng localhost, và cấu hình listener/firewall phù hợp; không mở broker ra Internet.
- Nhịp gửi mục tiêu: **một bản tin/giây**; lưu thời điểm nhận tại server để kiểm tra delay/gap.
- JSON tối thiểu, hợp đồng dữ liệu cho firmware ESP32 trong tương lai:

```json
{"ts_ms": 152350, "flow_main": 1.2, "flow_z1": 0.7, "flow_z2": 0.5}
```

Trong đó:
- `ts_ms`: thời gian kể từ khi ESP32 khởi động (`millis()`), **không phải UNIX epoch**. Hiện `fake_sensor.py` cũ dùng Unix milliseconds; KHÔNG dựa vào trường này để gán nhãn. `ts_server` do `collector.py` tạo là thời gian UTC của server.
- `flow_main`, `flow_z1`, `flow_z2`: đơn vị **L/phút**, số hữu hạn >= 0, dấu thập phân `.`.
- Không phát `pressure_mv`, không đẩy `label` hay `scenario` từ firmware thật. Việc gán nhãn do **nhật ký thí nghiệm** ghi lại.
- Có thể mở rộng `device_id`, `sequence`, `firmware_version`, `pulse_main`, `pulse_z1`, `pulse_z2` sau này; `collector.py` hiện tại chỉ lưu các trường có sẵn. Những trường bổ sung chưa phải điều kiện bắt buộc.

## Kiểm thử JSON ngay (không lưu dữ liệu fake)

Chạy ở thư mục Project II:

```powershell
.\.venv\Scripts\python.exe tools\validate_packet.py --file docs\mqtt_packet_example.json
```

Kết quả `PASS` cho biết đúng định dạng, **không chứng minh cảm biến chính xác**.

## SQLite

- Giữ nguyên bảng `telemetry`: `id`, `ts_server`, `ts_ms`, `flow_main`, `flow_z1`, `flow_z2`, `label`, `scenario_id` (bảng cũ có `pressure_mv` thì giữ, nhưng **không sử dụng**).
- Thêm bảng `experiment_sessions` để lưu mốc bắt đầu/kết thúc cùng người vận hành xác nhận nguồn đo **real**. **Không gán nhãn bằng cách sửa trực tiếp telemetry**.
- Trích xuất dữ liệu theo khoảng thời gian có nhật ký, không trộn fake cũ với mẫu thật.

## Yêu cầu chất lượng đầu vào

- Không âm, không NaN/null; kiểm tra lặp bản tin và mất gói theo timestamp server.
- Giá trị `0 < flow < 0.3` có thể xuất hiện nhưng nằm dưới dải đo đã xác nhận, nên phải đánh dấu *ngoài dải* thay vì coi là định lượng đáng tin cậy.
- Cân bằng lưu lượng: `main - z1 - z2`; khác 0 không tự động kết luận rò rỉ vì cần xét sai số cảm biến, vị trí điểm rò và trạng thái vận hành.
- Ngay khi có dữ liệu thật, cần đo/hiệu chuẩn **từng YF-S401**, lưu lại hệ số pulses-per-liter riêng cho 3 cảm biến.
