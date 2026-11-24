# Chuẩn MQTT v2 — Project II, 3 flow sensors

**Topic:** `building/water/node1/telemetry`, mỗi mẫu khoảng 1 giây khi firmware không bị chặn; QoS hiện thời 0.

Bắt buộc: `flow_main`, `flow_z1`, `flow_z2` (L/min, float >=0); `ts_ms` (uint32 uptime). Ở bản firmware v2: thêm `device_id` (chuỗi `water-node-01`), `boot_id` (16 ký tự hex), `seq` (uint32).

`seq` tăng theo chu kỳ đo, không chỉ theo số lần gửi thành công. Tránh báo nhầm mất mẫu do `boot_id` thay đổi khi khởi động mới; tránh báo thiếu mẫu với duplicate và các bản tin đến đảo thứ tự. `boot_id` là mã chẩn đoán, không phải biện pháp xác thực thiết bị.

Dữ liệu cảm biến thật không tự có nhãn `normal`/`leak` trong packet. Nhãn xuất phát từ người vận hành ghi phiên thử nghiệm và thao tác van có kiểm soát. Các bản tin giống ESP32 **không tự chứng minh** nguồn gốc vật lý.

`data/quality/mqtt_quality_v2.csv`: CSV ghi nhận hành vi luồng dữ liệu và `missing_samples_cumulative` (số chu kỳ được đánh số nhưng không thấy tại subscriber kể từ lúc công cụ chạy). Đây **không phải** số gói mất riêng do MQTT; thời gian không nhận được gói chỉ là khoảng ngắt truyền thông.
