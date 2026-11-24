"""Offline read-only audit of SQLite telemetry. Never marks anything REAL."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

from telemetry_quality import inspect_packet

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "water.db"
REQUIRED = ("id", "ts_server", "ts_ms", "flow_main", "flow_z1", "flow_z2")


def check_rows(database: Path, limit: int = 2000, gap: float = 2.5) -> dict:
    """Read only; label 'format_esp32' means format only, NOT physical origin."""
    if not database.is_file():
        raise ValueError(f"Khong tim thay database: {database}")
    db_uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(db_uri, uri=True, timeout=3)) as con:
        cols = {row[1] for row in con.execute("PRAGMA table_info(telemetry)")}
        missing = set(REQUIRED) - cols
        if missing:
            raise ValueError(f"Thieu cot: {sorted(missing)}")
        label_field = "COALESCE(label, '') AS label" if "label" in cols else "'' AS label"
        scenario_field = "COALESCE(scenario_id, '') AS scenario_id" if "scenario_id" in cols else "'' AS scenario_id"
        total = con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
        query = f"""SELECT id, ts_server, ts_ms, flow_main, flow_z1, flow_z2,
                    {label_field}, {scenario_field}
                    FROM telemetry ORDER BY id DESC LIMIT ?"""
        rows = con.execute(query, (limit,)).fetchall()

    counted = Counter()
    warning_samples: list[tuple[int, str]] = []
    last_t: datetime | None = None
    gap_count = 0
    nonincreasing_time = 0
    for row in reversed(rows):
        idx, ts_server, ts_ms, main, z1, z2, label, scenario = row
        pkt = {"ts_ms": ts_ms, "flow_main": main, "flow_z1": z1, "flow_z2": z2}
        if label:
            pkt["label"] = label
        if scenario:
            pkt["scenario"] = scenario
        result = inspect_packet(pkt)
        counted[result.kind] += 1
        if result.warnings:
            counted["rows_with_warnings"] += 1
        if result.problems:
            counted["rows_with_problems"] += 1
        if (result.warnings or result.problems) and len(warning_samples) < 6:
            warning_samples.append((idx, "; ".join(result.problems + result.warnings)))
        try:
            t = datetime.fromisoformat(str(ts_server).replace("Z", "+00:00"))
            if t.tzinfo is None:
                raise ValueError("timezone missing")
            t = t.astimezone(timezone.utc)
        except (ValueError, TypeError):
            counted["bad_server_timestamp"] += 1
            last_t = None
            continue
        if last_t is not None:
            delta = (t - last_t).total_seconds()
            if delta > gap:
                gap_count += 1
            elif delta <= 0:
                nonincreasing_time += 1
        last_t = t

    return {"database": str(database), "total": total, "checked": len(rows),
            "counts": dict(counted), "server_gaps": gap_count,
            "server_timestamp_nonincreasing": nonincreasing_time,
            "examples": warning_samples}


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiem tra chat luong SQLite, CHI DOC")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--gap", type=float, default=2.5)
    args = parser.parse_args()
    if args.limit <= 0 or args.gap <= 0:
        parser.error("--limit, --gap phai > 0")
    try:
        result = check_rows(args.db, args.limit, args.gap)
    except (sqlite3.Error, ValueError) as exc:
        print("AUDIT FAILED:", exc)
        return 2

    print("AUDIT SQLITE (CHI DOC; KHONG DANH DAU DU LIEU THAT)")
    print(f"Database: {result['database']}")
    print(f"Tong so ban ghi: {result['total']}; mau duoc xem: {result['checked']}")
    print("Pham vi: chi cac mau moi nhat; khong khang dinh nguon goc vat ly.")
    for key in ("format_esp32", "marked_simulation", "invalid", "rows_with_warnings", "rows_with_problems", "bad_server_timestamp"):
        print(f"  {key}: {result['counts'].get(key, 0)}")
    print(f"  Khoang cach server > {args.gap:g}s: {result['server_gaps']}")
    print(f"  Timestamp server trung/nguoc chieu: {result['server_timestamp_nonincreasing']}")
    if result["examples"]:
        print("Vi du (toi da 6 dong):")
        for idx, reason in result["examples"]:
            print(f"  id={idx}: {reason}")
    print("Chu y: `format_esp32` la hop le ve DINH DANG, khong phai chung thuc ESP32 that.")
    print("Khoang ngat du lieu != so goi tin MQTT mat; muon dem goi tin can bo sung sequence number.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
