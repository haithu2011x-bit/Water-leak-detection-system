# Cấu hình mô hình thực tế - 24/11/2026

## Ánh xạ cảm biến

| Sensor | Vị trí | GPIO | JSON |
|---|---|---|---|
| S0 | Ống chính | 25 | flow_main |
| S1 | Nhánh A | 26 | flow_z1 |
| S2 | Nhánh B | 27 | flow_z2 |

## Mô hình thủy lực

Bồn cấp -> Bơm -> S0 -> T chia nhánh.

- Nhánh A: điểm tạo rò A -> S1 -> đường hồi.
- Nhánh B: điểm tạo rò B -> S2 -> đường hồi.
- Hai van tạo rò điều khiển hai đường xả rò riêng.
- Đóng van rò không đồng nghĩa ngừng dòng nước tuần hoàn.

Residual = flow_main - flow_z1 - flow_z2.

Residual có thể ước tính tổng lưu lượng rò trong điều kiện ổn định
sau khi hiệu chuẩn. Không tự xác định chính xác nhánh rò.

## Firmware

- water_node_sensor_test: kiểm tra xung, Serial 115200.
- water_node_usb: hiệu chuẩn và truyền JSON qua USB.
- water_node: phương án MQTT dự phòng.

Giữ CALIBRATION_MODE = true và hệ số pulse/L bằng 0
trước khi có kết quả hiệu chuẩn thật.

## Điều kiện hiệu chuẩn

Hai van rò phải đóng. Không bịt đồng thời hai đường hồi
khi bơm đang chạy. Chỉ thay đổi đường ống khi đã dừng bơm.

Quy trình hiệu chuẩn một nhánh trong tài liệu cũ chỉ áp dụng
khi có bố trí thủy lực phù hợp đã được kiểm chứng.
Nếu hai nhánh cùng chảy, cần đo thể tích riêng của từng nhánh
trong cùng khoảng thời gian và dùng tổng thể tích cho S0.
Phải kiểm tra lại template và công cụ hiệu chuẩn trước khi
sử dụng phương án đo hai nhánh đồng thời.

## Trạng thái nghiệm thu

- Đã lắp mô hình thủy lực.
- Đã đồng bộ ánh xạ GPIO trong mã nguồn.
- Chưa nghiệm thu đầu nối và an toàn điện.
- Chưa xác nhận xung, chưa hiệu chuẩn.
- Chưa truyền dữ liệu cảm biến thật.
- Chưa đánh giá AI bằng thực nghiệm.
