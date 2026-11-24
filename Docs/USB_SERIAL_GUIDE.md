# Project II - ESP32 truyen du lieu USB Serial ve laptop

## Khi nao chon phuong an nay

Mo hinh hai zone song song tren ban thi nghiem co 3 YF-S401 (Main, Z1, Z2),
ESP32-WROOM-32D CP2102 Type-C, 4 van (2 su dung, 2 tao ro). Khong dung cam
bien ap suat. Cam bien hai nhanh nam **truoc vi tri van ro**.

USB Serial giup ESP32 vua nhan nguon 5V tu laptop, vua gui so lieu ve Python.
Khong can Wi-Fi, Mosquitto hay thu vien PubSubClient. **Bom 12V van phai co
nguon rieng**. Chi lay nguon 5V tu board cho 3 cam bien sau khi kiem tra gioi
han dong cua cong USB, board va module cam bien. TIN HIEU cam bien vao GPIO
phai duoc xu ly ve 0-3.3V; khong noi tin hieu 5V truc tiep vao ESP32.

## Duong truyen

3 flow sensors -> ESP32 -> cap USB Type-C co truyen data -> cong COM/ttyUSB
-> `backend/serial_collector.py` -> `data/water.db` -> dashboard Streamlit.

Firmware USB va MQTT duoc giu **thanh hai lua chon**. MQTT cu khong bi xoa.
Phan AI can data thuc, nhat ky thi nghiem va phe duyet nhu truoc. JSON v2
`device_id`, `boot_id`, `seq`, `ts_ms`, `flow_main`, `flow_z1`, `flow_z2`
duoc giu nguyen; **khong tu gan nhan normal/leak**.

## Buoc 1 - Nap va hieu chuan

1. Mo `firmware/water_node_usb/water_node_usb.ino` trong Arduino IDE.
2. Chon dung board ESP32 va cong COM. Dung cap USB-C co kha nang truyen data.
3. Giu `CALIBRATION_MODE = true` de doc xung, nap code, mo Serial Monitor 115200.
4. Do dung tich nuoc va xung tung cam bien theo
   `Docs/QUY_TRINH_HIEU_CHUAN.md` (co it nhat 3 luot CAL va CHECK doc lap).
5. Nhap ba he so `PULSES_PER_LITER_MAIN/Z1/Z2` tu nuoc that.
   Cac gia tri `0.0` ban dau chi la khoa an toan, KHONG phai he so dung.
6. Doi `CALIBRATION_MODE = false`, nap lai ESP32.
   Ban tin JSON duoc gui moi khoang 1 giay. Dong Serial Monitor truoc khi
   Python mo cong COM; mot cong COM thuong khong cho hai chuong trinh cung doc.

## Buoc 2 - Laptop nhan USB

Trong thu muc goc repository, su dung Python da cai cac thu vien dashboard:

```powershell
py -3 -m pip install pyserial
py -3 -m serial.tools.list_ports
py -3 tools\run_local.py --transport serial --serial-port COM5 --port 8501
```

Thay `COM5` bang cong that hien thi trong Device Manager hoac lenh liet ke.
Tren Linux, thuong la `/dev/ttyUSB0` va can quyen truy cap cong serial.
Truy cap `http://localhost:8501`. Dung bang Ctrl+C.

Co the chay tach rieng de debug:

```powershell
py -3 backend\serial_collector.py --port COM5 --baud 115200
py -3 -m streamlit run dashboard\unified_app.py
```

Khong chay dong thoi USB collector va MQTT collector tren cung `water.db` khi
kiem thu mot phien, tranh lai nhan hai nguon. Chuong trinh USB bo qua log khoi
dong, tu choi JSON loi, du lieu co `scenario/label`, ID thiet bi sai va mau
lap `device_id/boot_id/seq`. SQLite cu va cot `pressure_mv` lich su duoc giu.

## Luu y nghien cuu

- USB chi la cach truyen du lieu, khong tu lam tang do chinh xac YF-S401.
- Khi F1/F2 nam truoc van ro, `F0 - F1 - F2` co the van gan 0 du co ro phia
  sau cam bien. Can doi chung cac trang thai su dung/ro va danh gia sai so.
- JSON giong ESP32 va cap USB khong phai bang chung du lieu do tu nuoc that;
  van can anh, nhat ky do, xac nhan nguoi van hanh va tap test doc lap.
- `CALIBRATION_MODE = true` khong gui JSON L/min, do do collector se khong
  tao ban ghi do luu luong cho den khi ca 3 he so duoc hieu chuan.
