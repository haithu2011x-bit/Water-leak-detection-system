# Project II — Quy ước Alert Engine v1

## Chức năng
- Alert Engine **không tự quyết định rò rỉ**, không huấn luyện AI và không đọc lịch sử fake_sensor để cảnh báo.
- Bộ phát hiện/AI sau khi được nghiệm thu trên dữ liệu thực sẽ gọi `tools.alert_service.publish()`.
- `acknowledged` = đã đọc và đang xử lý, không đồng nghĩa đã khắc phục.
- `closed` = có người vận hành đóng kèm ghi chú, lịch sử thao tác không bị xoá.
- Một nhóm cảnh báo đang mở sẽ được gộp vào một sự cố (cùng thiết bị, nguồn, loại, zone).
- `event_id` duy nhất tránh ghi trùng khi retry. Gợi ý khi có ESP32 thật: `device_id:boot_id:seq:model_version`.
- Khi sự cố đã đóng, các sự kiện tương tự trong 60 giây kế tiếp chỉ được ghi là `suppressed_cooldown`, không mở cảnh báo mới. Có thể cấu hình khác theo yêu cầu thực nghiệm.

## Trường quyết định

| Trường | Ví dụ | Ghi chú |
|---|---|---|
| `event_id` | `water-node-01:aabbccddeeff0011:101:iforest-v2` | Duy nhất theo lần đánh giá; giữ ổn định khi retry |
| `device_id` | `water-node-01` | Node nguồn |
| `source` | `ai` | `ai`, `rule`, `hybrid`, `quality`, `system` |
| `category` | `leak_suspected` | Hoặc `telemetry_offline`, `sensor_fault`, `data_quality` |
| `zone` | `zone2` | `zone1`, `zone2`, `main`, `unknown` |
| `severity` | `warning` | `info`, `warning`, `critical` |
| `reasons` | `('Flow Z2 deviates from verified baseline',)` | 1–8 lý do dạng text |
| `score` | `0.61` | Tùy chọn; không dùng để tự đặt ngưỡng |
| `provenance` | `unverified` | `operator_confirmed` chỉ khi người vận hành xác nhận; không khẳng định xác thực mật mã |

**Ví dụ tích hợp ở tương lai, không chạy với model giả lập cũ:**

```python
from tools.alert_service import AlertDecision, publish

# Gọi sau khi detector đã được kiểm chứng với dữ liệu thật.
result = publish(AlertDecision(
    event_id=f"{device_id}:{boot_id}:{seq}:{model_version}",
    device_id=device_id,
    source="ai", category="leak_suspected", zone="zone2",
    severity="warning",
    reasons=("AI anomaly score vượt ngưỡng hiệu chuẩn trên dữ liệu thật",),
    score=score, provenance="unverified",
))
```

> Không đưa `fake_sensor.py`, dữ liệu có nhãn giả lập cũ hoặc các thông số hiệu suất từ dataset giả vào pipeline ra quyết định thật. Chưa có bộ phát hiện được kiểm chứng thì giao diện sẽ hiển thị 0 cảnh báo.

## Trạng thái và lịch sử

`open → acknowledged → closed`, hoặc `open → closed` nếu xử lý trực tiếp. Không hỗ trợ đổi trạng thái của cảnh báo đã đóng; sự cố mới sau cooldown tạo bản ghi mới. `alert_actions` là nhật ký thao tác. `alert_observations` chỉ dùng quản lý chống trùng sự kiện đầu vào.

## Phạm vi và giới hạn
- Alert Engine không đóng van, không gửi SMS/email, không tuyên bố định vị chính xác theo mét.
- Không có đăng nhập; chỉ dùng Dashboard trên `localhost` khi chưa triển khai xác thực.
- Mỗi lần chạy `publish` chỉ lưu quyết định đã được tính bên ngoài, không sửa bảng `telemetry`.
- Một nhóm cảnh báo cùng zone nhưng khác nguồn (`ai` và `rule`) hiện tách riêng. Khi tích hợp Hybrid sẽ thống nhất nguồn `hybrid` để tránh cảnh báo hai lần.
- Nếu cần chống nhập liệu giả mạo trên MQTT, phải bổ sung bảo vệ mạng/broker và định danh thiết bị; `device_id` trong payload không tự chứng minh nguồn gốc vật lý.
