# Hệ thống IoT AI phát hiện sớm và định vị rò rỉ nước

Dự án Project II sử dụng ESP32-WROOM-32D và ba cảm biến lưu lượng YF-S401
(F0 đường chính, F1 Zone 1, F2 Zone 2). Mô hình gồm hai zone song song,
hai van sử dụng và hai van tạo rò rỉ có kiểm soát; không dùng cảm biến áp suất.

## Truyền dữ liệu từ ESP32 đến laptop

Đối với mô hình đặt cạnh laptop, **ưu tiên USB Serial**:

`YF-S401 → ESP32 → cáp USB Type-C → Python → SQLite → Dashboard Streamlit`

USB vừa cấp nguồn cho ESP32 vừa truyền dữ liệu. Máy bơm 12V vẫn cần nguồn
riêng. Tín hiệu từ cảm biến vào GPIO phải có mức logic an toàn 0–3,3V.

Hướng dẫn đầy đủ: [Docs/USB_SERIAL_GUIDE.md](Docs/USB_SERIAL_GUIDE.md).

1. Nạp `firmware/water_node_usb/water_node_usb.ino`, giữ `CALIBRATION_MODE = true`.
2. Hiệu chuẩn **riêng từng cảm biến** bằng nước thật theo
   [quy trình hiệu chuẩn](Docs/QUY_TRINH_HIEU_CHUAN.md).
3. Điền ba hệ số xung/lít thực đo, chuyển `CALIBRATION_MODE = false` và nạp lại.
4. Cài `pyserial` và chạy trên Windows (thay `COM5` bằng cổng thực tế):

   ```powershell
   py -3 -m pip install pyserial
   py -3 tools\run_local.py --transport serial --serial-port COM5 --port 8501
   ```

5. Truy cập `http://localhost:8501` để theo dõi dashboard.

**Lưu ý:** đóng Arduino Serial Monitor trước khi chạy Python, vì một cổng COM
thường không thể được mở đồng thời bởi hai chương trình.

## Phương án Wi-Fi/MQTT vẫn được giữ

Firmware `firmware/water_node/water_node.ino` và `backend/collector.py`
tiếp tục hỗ trợ MQTT/Mosquitto. Khởi chạy chế độ MQTT cũ bằng:

```powershell
py -3 tools\run_local.py --transport mqtt --port 8501
```

Không chạy đồng thời cả hai collector vào cùng một phiên đo thực nghiệm.

## Tình trạng kiểm chứng

- Có mã nguồn đọc ba kênh, nhận qua USB hoặc MQTT, lưu SQLite và hiển thị.
- Các bài kiểm thử phần mềm dùng cơ sở dữ liệu tạm, không giả mạo dữ liệu thật.
- **Chưa có xác nhận hiệu chuẩn hoặc độ chính xác trên hệ thống vật lý** từ mã nguồn.
- Mô hình Isolation Forest và cảnh báo thực phải sử dụng dữ liệu thật đã được
  kiểm tra, đánh giá và phê duyệt theo tài liệu dự án.
- Với F1/F2 đặt trước van rò, chỉ số `F0-(F1+F2)` không đủ tự chứng minh
  rò rỉ phía sau cảm biến; định vị zone vẫn cần thực nghiệm có đối chứng.
