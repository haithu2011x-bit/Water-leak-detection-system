# Checklist an toàn khi phần cứng đến — Project II (3 YF-S401, không áp suất)

## A. Trước khi nối điện
- [ ] Kiểm kê 1 ESP32-WROOM-32D, 3 × YF-S401 (dải đã kiểm tra **0,3–6 L/phút**), bơm DC 12 V, nguồn phù hợp, ống, cút, van, khay hứng.
- [ ] Xem nhãn/datasheet **đúng phiên bản** để xác định nguồn VCC/GND/SIGNAL; không suy theo màu dây.
- [ ] Xác nhận mức tín hiệu đi vào GPIO ESP32 là **0–3,3 V**, có tầng chuyển mức/kéo lên phù hợp nếu cần. Không nối tín hiệu 5 V trực tiếp vào GPIO.
- [ ] Tách adapter/ổ điện 220 V và laptop ra khỏi khay nước; dùng nguồn bơm DC riêng.
- [ ] Gắn sensor đúng chiều; nhánh chính GPIO27, Z1 GPIO26, Z2 GPIO25 theo firmware hiện tại.

## B. Chạy riêng chế độ hiệu chuẩn
- [ ] Verify và Upload bản mới nhất `firmware/water_node/water_node.ino`; giữ `CALIBRATION_MODE = true`.
- [ ] Mở Serial Monitor **115200 baud**, chờ đủ dòng hiển thị `TOTAL M=... Z1=... Z2=...`.
- [ ] Kiểm tra tại trạng thái đóng van, xung không tự đếm bất thường.
- [ ] Chỉ mở một nhánh và lấy đúng lượng nước ở đầu xả. Ghi `pulses_start`, `pulses_end`, thể tích mL, thời gian s, `flow_path`.
- [ ] Có >=3 lần CAL mỗi sensor và >=1 lần CHECK riêng, không dùng CHECK để tính hệ số.
- [ ] Các phép đo hiệu chuẩn nằm trong vùng lưu lượng đã xác minh 0,3–6 L/phút; riêng lưu lượng nhánh có thể rơi dưới 0,3 L/phút.

## C. Khi đủ kết quả đo thực
- [ ] Chạy `tools/flow_calibration.py report ...`, kiểm tra độ lặp và sai số CHECK.
- [ ] Điền 3 hệ số thực vào firmware; lưu file báo cáo hiệu chuẩn và ảnh chụp sơ đồ thực tế.
- [ ] Điền Wi-Fi và IP laptop cho MQTT. Giữ kiểm tra nguồn dữ liệu thật độc lập, không dùng `fake_sensor.py`.
- [ ] Chuyển `CALIBRATION_MODE = false`, Verify lại rồi mới Upload.
- [ ] Xác nhận `device_id`, `boot_id`, `seq` xuất hiện trong JSON trên MQTT và SQLite.
- [ ] Chỉ bắt đầu phiên REAL trên dashboard `localhost:8502` khi tự xác nhận nguồn gửi là ESP32 thật.

## D. Tiêu chí trước khi thu dataset
- [ ] Kiểm tra van đóng → cả ba flow gần 0 (nếu ổn định).
- [ ] Chỉ Z1 hoạt động → Main và Z1 tăng, Z2 gần 0; đảo lại với Z2.
- [ ] Hai zone chạy đồng thời → kiểm tra `Main ≈ Z1 + Z2`, xét dung sai đo thực.
- [ ] Kiểm tra reboot, mất Wi-Fi, MQTT reconnect và dấu `seq`/`boot_id`.
- [ ] Hoàn thành các kịch bản N0–N4, L1–L5, F1 theo `docs/TEST_PLAN_REAL.md` đã có.

**Không đặt ngưỡng AI hay khẳng định khả năng phát hiện rò nhỏ chỉ từ giả lập.** Rò sau cảm biến nhánh có thể tạo số đo giống sử dụng hợp lệ; cần mô tả giới hạn này trong báo cáo.
