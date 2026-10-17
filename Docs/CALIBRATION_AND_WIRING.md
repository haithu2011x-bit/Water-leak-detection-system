# ESP32 + YF-S401: đấu nối và hiệu chuẩn (khi nhận hàng)

## 1. Cấu hình cố định

- ESP32-WROOM-32D DevKit 38 chân; 3 × YF-S401: Main → GPIO27; Zone 1 → GPIO26; Zone 2 → GPIO25.
- Không dùng cảm biến áp suất. Dải đo mà người thực hiện đã xác minh cho YF-S401: 0,3–6 L/phút.
- 5V cấp cho cảm biến **không đồng nghĩa** tín hiệu output an toàn cho ESP32: chân GPIO chỉ chấp nhận 3,3V. Cần kiểm tra nhãn/datasheet từng module, dùng tầng chuyển mức/tạo mức logic phù hợp. Không nối trực tiếp tín hiệu 5V vào ESP32. Phải có GND tham chiếu chung nếu dùng giao tiếp không cách ly.
- Chân `INPUT` trong firmware giả định tầng điều hòa đã tạo tín hiệu 0–3,3V ổn định. Nếu output sensor là open collector, xác nhận và dùng mạch kéo lên 3,3V phù hợp; không tự đoán dây/pinout theo màu.
- Không đặt điện áp 220V, ổ cắm, nguồn adapter ở nơi có thể bị bắn nước. Bơm DC 12V dùng nguồn riêng, không lấy nguồn từ GPIO hoặc USB ESP32.

## 2. Đấu ống

Bồn → Bơm DC → Flow Main → T chia hai nhánh.
Nhánh 1: Flow Z1 → van tay → đầu ra. Nhánh 2: Flow Z2 → van tay → đầu ra.

Điểm xả tạo rò kiểm soát nên đặt rõ ràng, đánh dấu vị trí **trước/sau** cảm biến nhánh. Điều này quyết định có nhận diện được vùng rò từ dữ liệu lưu lượng hay không.

## 3. Cách hiệu chuẩn từng sensor

1. Trong `water_node.ino`, giữ `CALIBRATION_MODE = true`, và **không kết nối firmware vào broker ở giai đoạn này**.
2. Nạp vào ESP32. Mở Serial Monitor baud 115200, gửi ký tự `r` để xóa bộ đếm tổng trước mỗi phép đo.
3. Chỉ mở một nhánh, xả nước vào bình đong. Đo thể tích thực bằng mL và ghi lại bộ đếm tổng `TOTAL` của Main và nhánh đang mở.
4. Tính `PULSES_PER_LITER = số xung / (thể tích đo được mL / 1000)`. Ví dụ minh họa: 680 xung qua đúng 1.00 L => 680 pulse/L. **Đây không phải hệ số của YF-S401 được xác minh.**
5. Lặp lại cho nhánh còn lại; đo lặp ít nhất 3 lần và lấy thống kê trung bình, độ lệch. Đo đủ ở các tốc độ dòng phù hợp dải sensor.
6. Điền riêng ba hệ số `PULSES_PER_LITER_MAIN`, `PULSES_PER_LITER_Z1`, `PULSES_PER_LITER_Z2`; kiểm tra sai số với thể tích chưa dùng hiệu chuẩn.
7. Sau khi các giá trị hợp lý, điền Wi-Fi và IP LAN của laptop, chuyển `CALIBRATION_MODE = false`, nạp firmware để gửi MQTT thật.

Ghi chú: khi tốc độ qua một sensor nằm dưới 0,3 L/phút, thông số YF-S401 chưa đảm bảo độ chính xác; cần đánh dấu dưới dải đo chứ không dùng để kết luận định lượng rò rỉ nhỏ.

## 4. Kiểm tra lên server

- Dùng `ipconfig` trên Windows để tìm IPv4 Wi-Fi/LAN của laptop. Khai báo `MQTT_HOST` là IP này, KHÔNG dùng `localhost` trong ESP32.
- Mosquitto cần listener nhận kết nối LAN và Windows Firewall phải cho phép TCP 1883 trong mạng tin cậy. Service mặc định có thể chỉ nghe ở localhost. Không mở cổng ra Internet; với mạng ngoài phòng lab phải bổ sung xác thực và kiểm soát truy cập.
- Chạy `backend/collector.py` trên laptop rồi quan sát topic bằng `mosquitto_sub`. Dừng mọi `fake_sensor.py` trước khi xác nhận các phiên REAL.
- Dữ liệu MQTT thật gửi đúng 4 trường `ts_ms`, `flow_main`, `flow_z1`, `flow_z2`; không kèm `pressure_mv`, `scenario`, `label`. `ts_ms` là `millis()` uint32, không phải epoch thời gian Unix.
- Kiểm tra `localhost:8502` nhận ít nhất 3 bản ghi liên tiếp hợp lệ rồi mới mở phiên thí nghiệm REAL. Đây là **kiểm tra dấu hiệu**, không thay cho việc xác nhận thủ công nguồn tín hiệu.
- Khi mất Wi-Fi/MQTT, firmware tiếp tục đếm xung nhưng **không lưu đệm mẫu offline** ở bản v1. Khoảng ngắt gửi phải được ghi nhận trong kiểm thử độ tin cậy.

## 5. Tiêu chí chấp nhận

- [ ] Cả ba tín hiệu vào ESP32 đã được xác minh 0–3,3 V, không nối 5V vào GPIO.
- [ ] Có bảng ghi xung, thể tích, hệ số pulse/L riêng cho từng sensor và kiểm tra lặp.
- [ ] Khi đóng hết van, lưu lượng về 0 (trong giới hạn nhiễu); khi mở Z1/Z2 đúng cảm biến tăng.
- [ ] `flow_main ≈ flow_z1 + flow_z2` khi hệ thống kín (xét sai số đo thực).
- [ ] ESP32 tự kết nối lại sau khi mất Wi-Fi và MQTT.
- [ ] SQLite chỉ lưu dữ liệu thật khi sender ESP32 đang hoạt động; các phiên được ghi nhật ký bằng giao diện 8502.
- [ ] Không dùng model đã train từ dữ liệu fake làm kết quả đánh giá hệ thống thực.
