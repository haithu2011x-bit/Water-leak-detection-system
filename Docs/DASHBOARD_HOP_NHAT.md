# Dashboard hợp nhất — Project II

Thêm trình điều hướng **Streamlit** trên nền các giao diện có sẵn. Sử dụng `st.navigation` và `st.Page` (Streamlit >= 1.36).

### Chạy thử (Windows)

Sau khi checkout nhánh và cài thư viện:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_unified_dashboard.py" -v
.\.venv\Scripts\python.exe -m streamlit run dashboard\unified_app.py --server.port 8504
```

Truy cập http://localhost:8504. Cổng 8504 giúp giữ nguyên các trang hiện tại 8501, 8502, 8503.

Các mục: Tổng quan; Biểu đồ lưu lượng (trang cũ); Chất lượng kết nối; Phiên thí nghiệm (trang cũ); Quản lý cảnh báo (trang cũ).

**Không thay Collector, SQLite hoặc firmware.** Tổng quan và nhật ký chất lượng chỉ đọc. Các thao tác phiên và xử lý cảnh báo tiếp tục đi qua dịch vụ có sẵn và có thể ghi dữ liệu như trước. Không tự chạy AI hoặc tạo dữ liệu giả. Sự hiện diện của bản tin mới không chứng minh nguồn dữ liệu vật lý.

Nếu thấy database chưa tồn tại, giao diện Tổng quan thông báo khởi động Collector; không cần chạy fake_sensor. Công cụ giám sát MQTT chạy độc lập nếu muốn ghi log.

Sau khi đã kiểm tra giao diện hợp nhất, có thể thay cổng 8504 bằng 8501 **sau khi đóng tiến trình cũ**.
