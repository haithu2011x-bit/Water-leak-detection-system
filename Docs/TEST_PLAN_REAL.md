# Kế hoạch thu dữ liệu THẬT — chuẩn bị trước khi lắp phần cứng

## Trước khi thử

1. Kiểm tra các ren/kẹp/ống, sàn khô; adapter và laptop tránh xa nước.
2. Chụp ảnh sơ đồ vị trí 3 flow meter, van và **vị trí điểm tạo rò**; phân biệt rõ leak trước hay sau sensor nhánh.
3. Kiểm tra phần điện trước khi nối: **ESP32 GPIO chỉ phù hợp mức logic 3,3V**; xác minh điện áp SIGNAL cảm biến và xử lý hạ mức khi cần. Dùng nguồn DC thấp áp.
4. Dùng thể tích nước chuẩn để hiệu chuẩn từng cảm biến, ghi pulses-per-liter, điều kiện thử, ngày đo. Không tin hệ số quảng cáo.
5. Dừng tất cả fake_sensor, bảo đảm mô hình ESP32 thật đang publish; chạy collector.
6. `python tools/experiment_log.py start --code ... --confirm-real --note "..."`, sau mỗi phiên chạy `stop`.

## Ma trận kịch bản — dùng để thực nghiệm

| Mã | Tình huống | Nhãn | Ghi nhận |
|---|---|---|---|
| N0 | Không dùng nước | normal | Dòng zero và mức nhiễu |
| N1 | Chỉ Zone 1 dùng ngắt quãng | normal | Lưu lượng/nhịp mở đóng |
| N2 | Chỉ Zone 2 dùng ngắt quãng | normal | Như N1 |
| N3 | Dùng đồng thời cả 2 zone | normal | Cân bằng 3 cảm biến |
| N4 | Zone 1 dùng lâu hợp lệ | normal | Tránh nhầm với rò rỉ kéo dài |
| L1 | Rò nhỏ Zone 1 | leak | Vị trí rò, lưu lượng rò thực đo, thời điểm bắt đầu |
| L2 | Rò nhỏ Zone 2 | leak | Như L1 |
| L3 | Rò vừa Zone 1 | leak | Detection time |
| L4 | Rò vừa Zone 2 | leak | Detection time |
| L5 | Rò trên đoạn giữa flow Main và 2 flow nhánh | leak | Flow residual |
| F1 | Cảm biến báo lỗi/mất gói | fault | Không được nhầm với leak |

Lặp mỗi scenario trong các điều kiện bơm/van khác nhau nếu khả thi; tách buổi thu dữ liệu để train và buổi test. Không dùng cùng một phiên để vừa chọn ngưỡng vừa đo kết quả cuối.

### Giới hạn nhận dạng bắt buộc nêu trong báo cáo

**Với chỉ 3 flow sensor**, rò sau flow meter nhánh **có thể không thể phân biệt** với người dùng đang mở vòi hợp lệ ở cùng nhánh nếu tín hiệu đo giống nhau. Đây là giới hạn quan sát của hệ thống, không phải chỉ do AI yếu. Cần thử tình huống N4 và báo cáo vùng nghi ngờ có độ bất định, không hứa định vị chính xác mét.

## Kết quả cần lưu sau mỗi lần thử

- Mã scenario; start/end theo UTC từ logger; thời điểm chính xác mở van tạo leak; cấu hình bơm/van; thể tích xả; ảnh/video tham chiếu; sự cố mất kết nối.
- Đảm bảo các dòng đầu/cuối ổn định, không dùng pha chuyển đổi do người vận hành gán nhãn sai.
- Dùng `python tools/export_real_data.py` để xuất CSV từ phiên hoàn tất; kiểm tra thủ công trước khi train.
