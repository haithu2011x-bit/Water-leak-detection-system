# Checklist lúc nhận hàng (để không phải làm lại phần mềm)

- [ ] 1 ESP32 DevKit, 3 cảm biến YF-S401, bơm, dây, van, ống, phụ kiện đủ.
- [ ] Xác nhận đúng dải đo 0,3–6 L/phút của phiên bản YF-S401 nhận hàng; kiểm tra mã model/in thực tế.
- [ ] Kiểm tra ESP32 nhận COM và nạp firmware mẫu, chưa nối nước.
- [ ] Xác định dây VCC / GND / SIGNAL bằng tài liệu hoặc kiểm tra chắc chắn, **không suy theo màu dây**.
- [ ] Đo/kiểm tra mức HIGH của tín hiệu SIGNAL trước khi nối GPIO ESP32 3,3V; dùng giải pháp chuyển mức thích hợp nếu cần.
- [ ] Lắp 3 flow theo đúng chiều; bơm và nước hoạt động ổn định, không rò ngoài ý muốn.
- [ ] Xác định chính xác điểm tạo leak trước/sau cảm biến của mỗi zone.
- [ ] Kiểm tra từng cảm biến bằng thể tích chuẩn, hiệu chuẩn 3 hệ số xung/lít độc lập.
- [ ] MQTT trên laptop nhận đúng JSON theo `Docs/MQTT_DATA_CONTRACT.md`.
- [ ] `collector.py` lưu được dữ liệu thực, `Dashboard` hiển thị, đồng hồ UTC máy tính chính xác.
- [ ] Stop `fake_sensor.py` hoàn toàn trước khi bắt đầu ghi nhật ký REAL.
- [ ] Sau đủ dataset thực mới train lại Isolation Forest và đánh giá trên phiên test khác.
