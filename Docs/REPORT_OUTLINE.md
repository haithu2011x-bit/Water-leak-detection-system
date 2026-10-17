# Đề cương báo cáo có thể viết ngay, không cần dữ liệu giả

1. **Mở đầu:** vấn đề rò rỉ nước, mục tiêu phát hiện sớm, định vị **theo zone**; phạm vi mô hình trên bàn, không tuyên bố triển khai cả tòa nhà.
2. **Cơ sở lý thuyết:** IoT, ESP32, MQTT, nguyên lý Hall flow meter, số xung/lít, SQLite, đặc trưng chuỗi thời gian, Isolation Forest; nguyên lý mass balance.
3. **Thiết kế hệ thống:** đường ống gồm 1 flow Main + 2 flow zone; ESP32 → MQTT → SQLite → AI → Dashboard. **Không dùng cảm biến áp suất.** Hợp đồng JSON, sơ đồ khối, schema DB, sơ đồ tiến trình thu nhận và kiểm soát chất lượng.
4. **Cài đặt:** phiên bản hệ điều hành, thư viện, firmware (hoàn thiện khi có board), collector, dashboard, nhật ký thí nghiệm, features, rule baseline, Isolation Forest, cảnh báo có giải thích.
5. **Thực nghiệm:** ma trận normal/leak/ lỗi thiết bị, cách gắn nhãn bằng người vận hành, phân tách train/validation/test theo phiên, đo Precision, Recall, F1, False Alarm Rate, Detection Time, Zone Accuracy. **Chừa trống kết quả thực cho tới khi có số đo thật.**
6. **Kết luận & hạn chế:** dải đo cảm biến, giới hạn rò nhỏ, nhận dạng leak vs. sử dụng hợp lệ sau meter nhánh, độ ổn định và hướng phát triển.

### Việc có thể viết ngay

Mục tiêu, phạm vi, kiến trúc phần mềm, hợp đồng MQTT, sơ đồ luồng dữ liệu, database schema, kế hoạch test, tiêu chí đánh giá, lý do chọn Isolation Forest.

### Tuyệt đối để sau

Thông số hiệu chuẩn, kết quả phát hiện rò rỉ thực, bảng metric chính thức, hình ảnh đo thật, kết luận độ chính xác, so sánh thực nghiệm.
