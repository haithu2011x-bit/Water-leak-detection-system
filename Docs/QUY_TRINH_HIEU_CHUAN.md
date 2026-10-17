# Quy trình đo và hiệu chuẩn thực tế — 3 cảm biến YF-S401

## I. Chuẩn hóa mô hình và hệ số

Đồ hình: Bồn → bơm → **MAIN** → T → hai nhánh **Z1** và **Z2**, mỗi nhánh có van tay/đầu xả. Không dùng cảm biến áp suất. Dùng **firmware v2 có `boot_id`/`seq`**; trong giai đoạn hiệu chuẩn luôn giữ `CALIBRATION_MODE = true` nên không publish MQTT hay làm bẩn dữ liệu train.

Firmware đo bằng bộ đếm xung ngắt và in: `dt=... | win M=... Z1=... Z2=... | TOTAL M=... Z1=... Z2=...`. Đây là **số xung tích lũy** sau khi ESP32 khởi động hoặc sau lệnh `r` trên Serial Monitor. Ta đọc hai mốc *bắt đầu* và *kết thúc* ở cùng một lần chạy để tính `pulses = pulses_end - pulses_start`.

Hệ số cho từng cảm biến riêng:

`PULSES_PER_LITER = (tổng số xung các lượt CAL) / (tổng thể tích đo thật của chính cảm biến, đơn vị L)`.

Ở một lượt thử chỉ **Z1 mở**, dòng qua MAIN và Z1 đi tới một điểm xả. Vì vậy cả hai cảm biến được đối chiếu với *cùng thể tích đo ở đầu ra Z1* nếu ống không có rò ngoài ý muốn. Khi chỉ **Z2 mở**, làm tương tự với MAIN và Z2. Cần cân đối sự phân bố tốc độ dòng để MAIN được kiểm tra tại các mức hoạt động khác nhau.

## II. Thao tác ghi 1 lượt

1. Bảo đảm tín hiệu logic 0–3,3 V vào ESP32, bơm dùng nguồn DC tách biệt; kiểm tra ống kín và Sensor đúng hướng.
2. Đặt `CALIBRATION_MODE = true`; Serial 115200; đóng cả hai van, chờ yên, đọc `TOTAL` làm giá trị bắt đầu (hoặc nhập `r` rồi đọc lại). Không cần giả định bộ đếm bắt đầu bằng 0.
3. Chỉ mở **một** nhánh Z1 hoặc Z2, hứng nước bằng dụng cụ có chia mL. Bấm thời gian bắt đầu, đo dòng ổn định, đóng nhánh và đọc `TOTAL` sau khi xung ngừng tăng. Nếu có nước chảy chưa hứng vào bình (lúc mở/đóng), lượt đó không đủ tin cậy — đo lại.
4. Ghi `volume_ml`, `pulses_start`, `pulses_end`, `duration_sec` cho MAIN và nhánh đã mở, cùng `run_id`. Dòng MAIN và nhánh trong cùng lượt thường có chung `volume_ml` và `duration_sec`, nhưng mỗi sensor có số xung của riêng nó.
5. `CAL` ba lượt mỗi nhánh ở tốc độ **trong dải 0,3–6 L/phút**; tốc độ phải được đo từ thể tích và thời gian, không suy từ thông số danh định bơm.
6. Giữ riêng ít nhất một lượt `CHECK` cho mỗi nhánh, **không dùng để tính hệ số**. Không chọn hay sửa lại hệ số bằng CHECK nếu còn muốn gọi đó là đánh giá độc lập; nếu điều chỉnh, phải thu một lượt CHECK mới.
7. Trước khi thu dữ liệu AI, ngoài kiểm chứng thể tích từng sensor, làm thêm bài thử hai nhánh đồng thời để so sánh `Main - Z1 - Z2`. Xác định dung sai từ dữ liệu thật.

**Cảnh báo:** Dải 0,3–6 L/phút được người dùng xác nhận đối với YF-S401 đã chọn; hiệu năng trong dải vẫn cần đo và hiệu chuẩn. Một nhánh có thể nhỏ hơn 0,3 L/phút dù MAIN đo đủ lưu lượng; công cụ sẽ đánh dấu lượt nằm ngoài dải. Bơm được giới thiệu mức danh định 2 L/phút, không coi đó là số đo thực tế.

## III. Điền bảng và xuất hệ số

1. Chép `docs/calibration_trials_template.csv` thành `data/calibration/calibration_trials.csv` (thư mục `data/calibration` có thể tự tạo).
2. Điền giá trị **thật** vào các cột `volume_ml`, `pulses_start`, `pulses_end`, `duration_sec`. Không sửa `phase`, `sensor_id`, `flow_path` trừ khi bố trí thực nghiệm thay đổi có ghi chú rõ. Không sao chép các số minh họa vào bảng này.
3. Kiểm tra cấu trúc (có thể chạy ngay lúc chưa có thiết bị):

```powershell
.\.venv\Scripts\python.exe tools\flow_calibration.py check --input docs\calibration_trials_template.csv
```

4. Khi có đủ lượt đo thực, xuất hệ số và báo cáo:

```powershell
.\.venv\Scripts\python.exe tools\flow_calibration.py report --input data\calibration\calibration_trials.csv --output data\calibration\ket_qua_hieu_chuan.txt
```

5. Xem các cảnh báo biến thiên hệ số giữa các lượt CAL và sai số phần CHECK. Mốc 5% trong báo cáo **chỉ là ngưỡng gợi ý xem lại**, không phải cam kết sai số nhà sản xuất.
6. Nhập `PULSES_PER_LITER_MAIN/Z1/Z2` vào `firmware/water_node/water_node.ino`. **Công cụ không sửa firmware tự động**. Sau Verify lần cuối, điền IP laptop, Wi-Fi, đổi `CALIBRATION_MODE = false` rồi mới Upload.

## IV. Lưu trữ phục vụ báo cáo

- Giữ file CSV gốc, ảnh sơ đồ đấu ống, nhãn từng cảm biến, ngày thử, điều kiện bơm/van, ghi chú dụng cụ đo, phiên bản firmware.
- `ket_qua_hieu_chuan.txt` có kết quả hệ số xung/L, độ dao động giữa các lượt CAL và sai số thể tích ước lượng ở lượt CHECK.
- Không sửa hoặc xoá 7.512 dòng giả lập cũ để hiệu chuẩn; chúng thuộc bộ dữ liệu lịch sử riêng.
- Chỉ dùng số đo thật cho thử nghiệm AI sau này, và dành phiên test độc lập không đưa vào huấn luyện.
