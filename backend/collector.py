"""MQTT -> SQLite, 3 cam bien flow (khong pressure).

Nang cap: gan nhan cac trang thai normal_* de huan luyen/kiem thu.
Du lieu ESP32 that khong co 'scenario' thi mac dinh KHONG nhan.
Tuong thich water.db cu, khong xoa/ghi de cot pressure_mv lich su.
"""

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "building/water/node1/telemetry"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB = PROJECT_ROOT / "data" / "water.db"
DB.parent.mkdir(parents=True, exist_ok=True)

NORMAL_SCENARIOS = {
    "normal", "normal_idle", "normal_z1", "normal_z2", "normal_both", "normal_long"
}
LEAK_SCENARIOS = {"leak_z1", "leak_z2", "leak_main"}

con = sqlite3.connect(DB)
con.execute("""
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_server TEXT NOT NULL,
    ts_ms INTEGER,
    flow_main REAL,
    flow_z1 REAL,
    flow_z2 REAL,
    label TEXT DEFAULT '',
    scenario_id TEXT DEFAULT '',
    device_id TEXT,
    boot_id TEXT,
    seq INTEGER
)
""")
# Non-destructive upgrade. Old rows and old pressure column are preserved.
existing_columns = {row[1] for row in con.execute("PRAGMA table_info(telemetry)")}
for col, sqltype in (("device_id", "TEXT"), ("boot_id", "TEXT"), ("seq", "INTEGER")):
    if col not in existing_columns:
        con.execute(f"ALTER TABLE telemetry ADD COLUMN {col} {sqltype}")
con.commit()
print("Database:", DB)


def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.subscribe(TOPIC)
    print("Subscribed:", TOPIC)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        readings = [float(data[k]) for k in ("flow_main", "flow_z1", "flow_z2")]
        if not all(math.isfinite(v) and 0 <= v <= 6.1 for v in readings):
            raise ValueError("Invalid flow reading")
        scenario = str(data.get("scenario", "")).strip().lower()
        if scenario in NORMAL_SCENARIOS:
            label = "normal"
        elif scenario in LEAK_SCENARIOS:
            label = "leak"
        else:
            scenario, label = "", ""  # sensor THAT chua duoc gan nhan

        # v2 traceability fields are optional: legacy fake packets remain readable.
        metadata_fields = ("device_id", "boot_id", "seq")
        provided = [field in data for field in metadata_fields]
        if any(provided) and not all(provided):
            raise ValueError("incomplete v2 metadata: require device_id, boot_id, seq")
        device_id = boot_id = seq = None
        if all(provided):
            device_id, boot_id, seq = data["device_id"], data["boot_id"], data["seq"]
            if device_id != "water-node-01":
                raise ValueError("unknown device_id")
            if not isinstance(boot_id, str) or len(boot_id) != 16 or any(ch not in "0123456789abcdefABCDEF" for ch in boot_id):
                raise ValueError("boot_id must be 16 hexadecimal characters")
            if type(seq) is not int or not 0 <= seq < 2**32:
                raise ValueError("seq must be a uint32 integer")
        row = (
            datetime.now(timezone.utc).isoformat(),
            data.get("ts_ms"),
            *readings, label, scenario, device_id, boot_id, seq,
        )
        con.execute("""
            INSERT INTO telemetry (
                ts_server, ts_ms, flow_main, flow_z1, flow_z2,
                label, scenario_id, device_id, boot_id, seq
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)
        con.commit()
        print(f"Saved | scenario={scenario or 'unlabelled'} label={label or 'unlabelled'} "
              f"main={readings[0]:.3f} z1={readings[1]:.3f} z2={readings[2]:.3f}")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("Bad message:", exc)
    except sqlite3.Error as exc:
        print("Database error:", exc)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    print("Connecting to Mosquitto...")
    client.connect(BROKER, PORT, 60)
    print("Collector running; Ctrl+C to stop")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping collector")
    finally:
        con.close()
        client.disconnect()


if __name__ == "__main__":
    main()
