"""Passive MQTT monitor: read-only subscribe, never publishes telemetry or changes SQLite."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

from telemetry_quality import StreamState, inspect_packet

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPIC = "building/water/node1/telemetry"
HEADERS = ["received_utc", "mqtt_topic", "kind", "device_id", "boot_id", "seq", "ts_ms", "flow_main", "flow_z1", "flow_z2", "missing_samples_cumulative", "problems", "warnings", "stream_flags"]


def main() -> int:
    p = argparse.ArgumentParser(description="Giam sat MQTT ESP32 3 flow (chi doc)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--topic", default=DEFAULT_TOPIC)
    p.add_argument("--timeout", type=float, default=5.0, help="Bao mat stream sau N giay")
    p.add_argument("--gap", type=float, default=2.5, help="Canh bao khi 2 ban tin cach nhau > N giay")
    p.add_argument("--log", type=Path, default=ROOT / "data" / "quality" / "mqtt_quality_v2.csv")
    args = p.parse_args()
    if args.timeout <= 0 or args.gap <= 0:
        p.error("--timeout va --gap phai > 0")
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("THIEU THU VIEN: .\\.venv\\Scripts\\python.exe -m pip install paho-mqtt")
        return 2

    args.log.parent.mkdir(parents=True, exist_ok=True)
    is_new = not args.log.exists() or args.log.stat().st_size == 0
    state = StreamState()
    connected = False
    saw_packet = False
    offline_reported = False
    last_packet_mono: float | None = None
    connected_at: float | None = None
    last_summary = time.monotonic()
    last_reconnect_attempt = 0.0

    with args.log.open("a", encoding="utf-8-sig" if is_new else "utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        if is_new:
            writer.writeheader()
            handle.flush()

        def on_connect(client, userdata, flags, reason_code, properties):
            nonlocal connected, connected_at, offline_reported
            if reason_code == 0:
                connected = True
                connected_at = time.monotonic()
                offline_reported = False
                client.subscribe(args.topic, qos=0)
                print(f"[MQTT] DA KET NOI broker={args.host}:{args.port}; topic={args.topic}")
                print("[WAITING] Chua khang dinh co ESP32. Dang doi telemetry...")
            else:
                connected = False
                print(f"[MQTT] TU CHOI KET NOI, reason_code={reason_code}")

        def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
            nonlocal connected
            connected = False
            print(f"[MQTT] NGAT KET NOI broker, reason_code={reason_code}")

        def on_message(client, userdata, message):
            nonlocal saw_packet, last_packet_mono, offline_reported
            now = time.monotonic()
            report = inspect_packet(message.payload)
            extra = state.record(report, now, args.gap)
            saw_packet = True
            last_packet_mono = now
            offline_reported = False
            record = {
                "received_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "mqtt_topic": message.topic,
                "kind": report.kind,
                "device_id": report.device_id or "",
                "boot_id": report.boot_id or "",
                "seq": report.seq if report.seq is not None else "",
                "ts_ms": report.ts_ms if report.ts_ms is not None else "",
                "flow_main": report.flows[0] if report.flows else "",
                "flow_z1": report.flows[1] if report.flows else "",
                "flow_z2": report.flows[2] if report.flows else "",
                "missing_samples_cumulative": state.missing_samples,
                "problems": " | ".join(report.problems),
                "warnings": " | ".join(report.warnings),
                "stream_flags": " | ".join(extra),
            }
            writer.writerow(record)
            handle.flush()
            label = {"format_esp32": "FORMAT_OK (chua xac minh nguon that)",
                     "marked_simulation": "CO_NHAN (khong tinh la REAL)",
                     "invalid": "PACKET_LOI"}[report.kind]
            if report.flows:
                nums = f"M={report.flows[0]:.3f} Z1={report.flows[1]:.3f} Z2={report.flows[2]:.3f}"
            else:
                nums = ""
            print(f"[{label}] {nums}" + (f" | {'; '.join(report.problems + report.warnings + extra)}" if report.problems or report.warnings or extra else ""))

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="project-ii-passive-quality-monitor")
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        print("Monitor CHI DOC: khong publish, khong sua water.db, khong train AI.")
        print(f"Log: {args.log}")
        try:
            client.connect(args.host, args.port, keepalive=30)
            while True:
                result = client.loop(timeout=1.0)
                now = time.monotonic()
                if result != mqtt.MQTT_ERR_SUCCESS and now - last_reconnect_attempt > 5.0:
                    last_reconnect_attempt = now
                    try:
                        client.reconnect()
                    except (OSError, ConnectionError) as exc:
                        print(f"[BROKER OFFLINE] Dang thu ket noi lai: {exc}")
                if connected and not offline_reported:
                    since = last_packet_mono if saw_packet else connected_at
                    if since is not None and now - since > args.timeout:
                        status = "MAT LUONG TELEMETRY" if saw_packet else "CHUA CO ESP32 / KHONG CO BAN TIN"
                        print(f"[{status}] Khong nhan ban tin trong >{args.timeout:g}s. Khong tu khang dinh thiet bi hong.")
                        offline_reported = True
                if now - last_summary >= 30:
                    print(f"[TONG HOP] nhan={state.received}, dung_dang={state.valid_shape}, "
                          f"co_nhan={state.marked_simulation}, loi={state.invalid}, "
                          f"khoang_ngat={state.long_gaps}, thieu_mau_seq={state.missing_samples}, "
                          f"khoi_dong_moi={state.boot_changes}, seq_trung={state.duplicate_seq}, "
                          f"seq_dao_thu_tu={state.out_of_order_seq}")
                    last_summary = now
        except KeyboardInterrupt:
            print("\nDa dung monitor, log CSV da duoc luu.")
        except OSError as exc:
            print(f"Khong ket noi duoc broker: {exc}")
            return 2
        finally:
            try:
                client.disconnect()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
