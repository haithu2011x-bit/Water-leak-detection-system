from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.telemetry_quality import inspect_packet

DEFAULT_DB = ROOT / "data" / "water.db"
DEVICE_ID = "water-node-01"


def open_database(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Migrate in place, retaining historical rows and old pressure columns."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts_server TEXT NOT NULL,
            ts_ms INTEGER, flow_main REAL, flow_z1 REAL, flow_z2 REAL,
            label TEXT DEFAULT '', scenario_id TEXT DEFAULT '',
            device_id TEXT, boot_id TEXT, seq INTEGER)""")
        existing = {row[1] for row in con.execute("PRAGMA table_info(telemetry)")}
        for name, sql_type in (("label", "TEXT DEFAULT ''"),
                               ("scenario_id", "TEXT DEFAULT ''"),
                               ("device_id", "TEXT"), ("boot_id", "TEXT"),
                               ("seq", "INTEGER")):
            if name not in existing:
                con.execute(f"ALTER TABLE telemetry ADD COLUMN {name} {sql_type}")
        con.commit()
        return con
    except sqlite3.Error:
        con.close()
        raise


def parse_line(raw: bytes | str) -> tuple[dict | None, str | None]:
    """Ignore boot diagnostics; reject broken and labeled/simulated messages."""
    try:
        line = raw.decode("utf-8", errors="strict") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError:
        return None, "invalid UTF-8"
    if not line.strip().startswith("{"):
        return None, None
    report = inspect_packet(line)
    if not report.ok:
        return None, "; ".join(report.problems)
    if report.kind != "format_esp32":
        return None, "scenario/label must not be imported as real telemetry"
    if report.device_id != DEVICE_ID or report.boot_id is None or report.seq is None:
        return None, "device_id, boot_id, seq from ESP32 v2 are required"
    return json.loads(line), None


def save_packet(con: sqlite3.Connection, packet: dict) -> bool:
    """Store unlabeled data; ignore a duplicate device/boot/sequence."""
    key = (packet["device_id"], packet["boot_id"], packet["seq"])
    if con.execute("SELECT 1 FROM telemetry WHERE device_id=? AND boot_id=? AND seq=? LIMIT 1", key).fetchone():
        return False
    with con:
        con.execute("""INSERT INTO telemetry
            (ts_server, ts_ms, flow_main, flow_z1, flow_z2,
             label, scenario_id, device_id, boot_id, seq)
            VALUES (?, ?, ?, ?, ?, '', '', ?, ?, ?)""", (
                datetime.now(timezone.utc).isoformat(), packet["ts_ms"],
                float(packet["flow_main"]), float(packet["flow_z1"]),
                float(packet["flow_z2"]), *key))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect ESP32 readings over USB Serial")
    parser.add_argument("--port", required=True, help="Windows COM5 or Linux /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    if not 1200 <= args.baud <= 1000000:
        parser.error("invalid baud rate")
    try:
        import serial  # pyserial is only required for USB mode
    except ImportError as exc:
        raise SystemExit("Install pyserial: python -m pip install pyserial") from exc
    try:
        port = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        raise SystemExit(f"Cannot open {args.port}: {exc}") from exc
    try:
        con = open_database(args.db)
        print(f"USB Serial {args.port} @ {args.baud}; database: {args.db}", flush=True)
        print("Close Arduino Serial Monitor. Ctrl+C to stop.", flush=True)
        try:
            while True:
                raw = port.readline(8193)
                if not raw:
                    continue
                packet, error = parse_line(raw)
                if error:
                    print("Skipped Serial line:", error, flush=True)
                elif packet is not None and save_packet(con, packet):
                    print(f"Saved seq={packet['seq']} | M={packet['flow_main']} "
                          f"Z1={packet['flow_z1']} Z2={packet['flow_z2']}", flush=True)
        except KeyboardInterrupt:
            print("\nStopped USB collector.")
        finally:
            con.close()
    finally:
        port.close()


if __name__ == "__main__":
    main()
