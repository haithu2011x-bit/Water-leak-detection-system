"""Backend for the real-experiment Streamlit UI. Never mutates telemetry or trains models.

Requires tools/experiment_log.py from the previous Project II package.
"""
import csv
import io
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.experiment_log import SCENARIOS, CREATE_SQL

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "water.db"
FLOW_KEYS = ("flow_main", "flow_z1", "flow_z2")
FIELDS = ("id", "ts_server", "ts_ms", *FLOW_KEYS, "label", "scenario_id")


def utc_now():
    return datetime.now(timezone.utc)


def db_connect(db=DEFAULT_DB):
    db = Path(db)
    if not db.is_file():
        raise ValueError(f"Chưa tìm thấy {db}. Không tạo database mới.")
    con = sqlite3.connect(str(db), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    return con


def setup_schema(con):
    required = {"id", "ts_server", "ts_ms", *FLOW_KEYS, "label", "scenario_id"}
    have = {r[1] for r in con.execute("PRAGMA table_info(telemetry)")}
    if not required.issubset(have):
        raise ValueError("Bảng telemetry thiếu cột: " + ", ".join(sorted(required - have)))
    con.execute(CREATE_SQL)
    con.commit()


def _time(s):
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def _recent_stream_check(con, now=None):
    """Heuristic only: confirms fresh packets match ESP32 data CONTRACT, not physical provenance."""
    now = now or utc_now()
    rows = con.execute("""SELECT id, ts_server, ts_ms, flow_main, flow_z1, flow_z2,
      COALESCE(label,'') AS label, COALESCE(scenario_id,'') AS scenario_id
      FROM telemetry ORDER BY id DESC LIMIT 5""").fetchall()
    messages = []
    if len(rows) < 3:
        return False, ["Cần ít nhất 3 bản tin mới liên tiếp từ ESP32."], rows
    parsed = []
    for r in reversed(rows):
        t = _time(r["ts_server"])
        if t is None:
            messages.append(f"Bản ghi #{r['id']}: thời gian server không hợp lệ.")
        else:
            parsed.append(t)
        if type(r["ts_ms"]) is not int or not 0 <= r["ts_ms"] < 2**32:
            messages.append(f"Bản ghi #{r['id']}: ts_ms không có dạng uptime uint32 ESP32.")
        if r["scenario_id"] or r["label"]:
            messages.append(f"Bản ghi #{r['id']}: có nhãn/kịch bản (có thể là dữ liệu giả).")
        for k in FLOW_KEYS:
            v = r[k]
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                messages.append(f"Bản ghi #{r['id']}: {k} không hợp lệ.")
    if len(parsed) == len(rows):
        age = (now - parsed[-1]).total_seconds()
        if age < -3 or age > 12:
            messages.append(f"Chưa có dữ liệu mới (mẫu cuối cách hiện tại {age:.1f} giây).")
        if any((b-a).total_seconds() <= 0 or (b-a).total_seconds() > 8
               for a, b in zip(parsed[:-1], parsed[1:])):
            messages.append("Bản tin cuối có khoảng thời gian không liên tục (>8s), trùng hoặc đảo thứ tự.")
    return not messages, messages, rows


def stream_status(db=DEFAULT_DB, now=None):
    with db_connect(db) as con:
        setup_schema(con)
        valid, messages, rows = _recent_stream_check(con, now)
    return {"ready": valid, "reasons": messages,
            "latest_id": rows[0]["id"] if rows else None,
            "latest_time": rows[0]["ts_server"] if rows else None}


def summary(db=DEFAULT_DB):
    with db_connect(db) as con:
        setup_schema(con)
        total = con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
        legacy = con.execute("SELECT COUNT(*) FROM telemetry WHERE COALESCE(scenario_id,'') != ''").fetchone()[0]
        sessions = con.execute("SELECT COUNT(*) FROM experiment_sessions").fetchone()[0]
        active = con.execute("SELECT id, scenario_code, start_utc FROM experiment_sessions WHERE end_utc IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        newest = con.execute("SELECT ts_server FROM telemetry ORDER BY id DESC LIMIT 1").fetchone()
    return {"total": total, "tagged_history": legacy, "sessions": sessions,
            "active": dict(active) if active else None, "latest": newest[0] if newest else None}


def list_sessions(db=DEFAULT_DB, limit=100):
    with db_connect(db) as con:
        setup_schema(con)
        rows = con.execute("SELECT * FROM experiment_sessions ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [dict(r) for r in rows]


def start_session(code, note, confirm_real=False, db=DEFAULT_DB, now=None):
    code = code.upper().strip()
    if code not in SCENARIOS:
        raise ValueError(f"Mã kịch bản không hợp lệ: {code}")
    if not confirm_real:
        raise ValueError("Bạn phải xác nhận đã ngừng fake_sensor và chỉ đang đo từ ESP32 thật.")
    with db_connect(db) as con:
        setup_schema(con)
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM experiment_sessions WHERE end_utc IS NULL LIMIT 1").fetchone():
            raise ValueError("Đã có phiên đang mở; hãy kết thúc phiên đó trước.")
        valid, errors, _ = _recent_stream_check(con, now)
        if not valid:
            raise ValueError("Chưa đủ điều kiện ghi REAL: " + " | ".join(errors[:4]))
        label, zone, _ = SCENARIOS[code]
        timestamp = (now or utc_now()).isoformat(timespec="microseconds")
        cur = con.execute("""INSERT INTO experiment_sessions
            (scenario_code,label,zone,source,start_utc,start_note)
            VALUES (?,?,?,'real',?,?)""", (code, label, zone, timestamp, note.strip()))
        con.commit()
        return cur.lastrowid


def stop_session(note="", db=DEFAULT_DB, now=None):
    with db_connect(db) as con:
        setup_schema(con)
        con.execute("BEGIN IMMEDIATE")
        active = con.execute("SELECT id, start_utc FROM experiment_sessions WHERE end_utc IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if active is None:
            raise ValueError("Không có phiên nào đang mở.")
        timestamp = (now or utc_now()).isoformat(timespec="microseconds")
        if _time(timestamp) <= _time(active["start_utc"]):
            raise ValueError("Thời điểm kết thúc phải sau thời điểm bắt đầu.")
        con.execute("UPDATE experiment_sessions SET end_utc=?,end_note=? WHERE id=?",
                    (timestamp, note.strip(), active["id"]))
        con.commit()
        return active["id"]


def _session(con, session_id):
    result = con.execute("SELECT * FROM experiment_sessions WHERE id=?", (int(session_id),)).fetchone()
    if result is None:
        raise ValueError("Không tìm thấy phiên thử nghiệm.")
    return dict(result)


def _where_for_session(session):
    end = session["end_utc"] or utc_now().isoformat()
    return "ts_server >= ? AND ts_server < ?", (session["start_utc"], end)


def sample_rows(db=DEFAULT_DB, session_id=None, limit=1500):
    limit = min(max(int(limit), 1), 10000)
    with db_connect(db) as con:
        setup_schema(con)
        where, args = "1=1", ()
        if session_id is not None:
            session = _session(con, session_id)
            where, args = _where_for_session(session)
        rows = con.execute("""SELECT id, ts_server, ts_ms, flow_main, flow_z1, flow_z2,
                COALESCE(label,'') AS label, COALESCE(scenario_id,'') AS scenario_id
                FROM telemetry WHERE """ + where + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
    return list(reversed([dict(r) for r in rows]))


def session_quality(db=DEFAULT_DB, session_id=None):
    rows = sample_rows(db=db, session_id=session_id, limit=10000)
    gaps = 0
    too_low = too_high = invalid = 0
    residuals = []
    last_t = None
    for r in rows:
        t = _time(r["ts_server"])
        if t and last_t and (t-last_t).total_seconds() > 2.5:
            gaps += 1
        if t: last_t = t
        if any(not isinstance(r[x], (int, float)) or not math.isfinite(r[x]) or r[x] < 0 for x in FLOW_KEYS):
            invalid += 1
            continue
        too_low += sum(0 < r[x] < 0.3 for x in FLOW_KEYS)
        too_high += sum(r[x] > 6 for x in FLOW_KEYS)
        residuals.append(r["flow_main"] - r["flow_z1"] - r["flow_z2"])
    return {"loaded": len(rows), "gaps_over_2_5s": gaps, "invalid_rows": invalid,
            "below_range_readings": too_low, "above_range_readings": too_high,
            "mean_abs_residual": round(sum(abs(x) for x in residuals)/len(residuals), 4) if residuals else None,
            "limit_reached": len(rows) == 10000}


def export_verified_session_csv(db=DEFAULT_DB, session_id=None):
    """Only completed, operator-confirmed, flow-only session; won't silently mix old fake labels."""
    with db_connect(db) as con:
        setup_schema(con)
        sess = _session(con, session_id)
        if sess["source"] != "real" or sess["end_utc"] is None:
            raise ValueError("Chỉ xuất CSV cho phiên REAL đã kết thúc.")
        where, args = _where_for_session(sess)
        rows = con.execute("""SELECT id, ts_server, ts_ms, flow_main, flow_z1, flow_z2,
            COALESCE(label,'') AS original_label, COALESCE(scenario_id,'') AS original_scenario
            FROM telemetry WHERE """ + where + " ORDER BY id", args).fetchall()
    if not rows:
        raise ValueError("Phiên chưa có dữ liệu cảm biến.")
    output = io.StringIO()
    columns = ["id", "ts_server", "ts_ms", *FLOW_KEYS, "label", "scenario_id", "zone", "experiment_id", "source"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        if r["original_scenario"] or r["original_label"]:
            raise ValueError(f"Có bản ghi #{r['id']} mang nhãn/kịch bản cũ. Không xuất dưới tên dữ liệu thật.")
        if type(r["ts_ms"]) is not int or not 0 <= r["ts_ms"] < 2**32:
            raise ValueError(f"Bản ghi #{r['id']} không dùng timestamp uptime ESP32.")
        if any(not isinstance(r[k], (int, float)) or not math.isfinite(r[k]) or r[k] < 0 for k in FLOW_KEYS):
            raise ValueError(f"Bản ghi #{r['id']} có lưu lượng lỗi.")
        writer.writerow({**{k: r[k] for k in ("id", "ts_server", "ts_ms", *FLOW_KEYS)},
                         "label": sess["label"], "scenario_id": sess["scenario_code"], "zone": sess["zone"],
                         "experiment_id": sess["id"], "source": "real_operator_confirmed"})
    return output.getvalue().encode("utf-8-sig")
