"""Alert Engine for Project II (ESP32 -> MQTT -> SQLite -> AI).

Independent of telemetry collection and ML models. This module does not generate
or classify leaks: an upstream, separately verified detector supplies decisions.
All SQLite connections close explicitly, including on Windows.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "water.db"
SOURCES = {"ai", "rule", "hybrid", "quality", "system"}
CATEGORIES = {"leak_suspected", "telemetry_offline", "sensor_fault", "data_quality"}
ZONES = {"main", "zone1", "zone2", "unknown"}
SEVERITIES = {"info": 0, "warning": 1, "critical": 2}
STATES = {"open", "acknowledged", "closed"}
PROVENANCE = {"unverified", "operator_confirmed"}


@dataclass(frozen=True)
class AlertDecision:
    """One *new* upstream event. event_id must be stable across retries.

    Pass e.g. device_id:boot_id:seq:model_version as event_id for AI decisions.
    This class never assumes a matching format is physical proof of provenance.
    """
    event_id: str
    device_id: str
    source: str
    category: str
    zone: str
    severity: str
    reasons: tuple[str, ...]
    score: float | None = None
    provenance: str = "unverified"


def _now_str(now: datetime | None = None) -> str:
    t = now if now is not None else datetime.now(timezone.utc)
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Clock needs a timezone-aware datetime")
    return t.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _connection(db: str | Path):
    path = Path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    return con


def init_db(db: str | Path = DEFAULT_DB) -> None:
    """Add only alert-specific tables; never ALTER or UPDATE telemetry."""
    with closing(_connection(db)) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_key TEXT NOT NULL,
            device_id TEXT NOT NULL,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            zone TEXT NOT NULL,
            severity TEXT NOT NULL,
            provenance TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'open',
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            observations INTEGER NOT NULL DEFAULT 1,
            latest_score REAL,
            reasons_json TEXT NOT NULL,
            ack_actor TEXT,
            ack_utc TEXT,
            close_actor TEXT,
            close_utc TEXT,
            close_note TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_state_time ON alerts(state, last_seen_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_alerts_group ON alerts(group_key, id DESC);
        CREATE TABLE IF NOT EXISTS alert_observations (
            event_id TEXT PRIMARY KEY,
            alert_id INTEGER NOT NULL REFERENCES alerts(id),
            received_utc TEXT NOT NULL,
            disposition TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alert_observations_alert ON alert_observations(alert_id);
        CREATE TABLE IF NOT EXISTS alert_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL REFERENCES alerts(id),
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            acted_utc TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alert_actions_alert ON alert_actions(alert_id, id);
        """)


def _validate(decision: AlertDecision) -> None:
    for key in ("event_id", "device_id"):
        value = getattr(decision, key)
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"Invalid {key}")
    if decision.source not in SOURCES:
        raise ValueError("Invalid source")
    if decision.category not in CATEGORIES:
        raise ValueError("Invalid category")
    if decision.zone not in ZONES:
        raise ValueError("Invalid zone")
    if decision.severity not in SEVERITIES:
        raise ValueError("Invalid severity")
    if decision.provenance not in PROVENANCE:
        raise ValueError("Invalid provenance; simulation is not allowed in production alerts")
    if not isinstance(decision.reasons, tuple) or not 1 <= len(decision.reasons) <= 8:
        raise ValueError("Require 1..8 reasons")
    if any(not isinstance(r, str) or not r.strip() or len(r) > 500 for r in decision.reasons):
        raise ValueError("Invalid reason")
    if decision.score is not None:
        import math
        if type(decision.score) not in (float, int) or not math.isfinite(decision.score):
            raise ValueError("Score must be a finite number")


def publish(decision: AlertDecision, db: str | Path = DEFAULT_DB,
            now: datetime | None = None, cooldown_seconds: int = 60) -> dict[str, Any]:
    """Idempotent ingestion. Group repeated events into one active incident.

    After close, suppress *new* events in the same group during cooldown.
    No AI thresholds / decision logic here.
    """
    _validate(decision)
    if cooldown_seconds < 0:
        raise ValueError("cooldown_seconds must be nonnegative")
    init_db(db)
    ts = _now_str(now)
    group = "|".join((decision.device_id, decision.source, decision.category, decision.zone))
    with closing(_connection(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            repeated = con.execute("SELECT alert_id FROM alert_observations WHERE event_id=?", (decision.event_id,)).fetchone()
            if repeated:
                con.commit()
                return {"status": "duplicate_event", "alert_id": repeated["alert_id"]}
            active = con.execute("""SELECT * FROM alerts WHERE group_key=? AND state IN ('open','acknowledged')
                                    ORDER BY id DESC LIMIT 1""", (group,)).fetchone()
            if active:
                alert_id = active["id"]
                severity = max((active["severity"], decision.severity), key=lambda s: SEVERITIES[s])
                con.execute("""UPDATE alerts SET last_seen_utc=?, observations=observations+1,
                               latest_score=?, reasons_json=?, severity=? WHERE id=?""",
                            (ts, decision.score, json.dumps(decision.reasons, ensure_ascii=False), severity, alert_id))
                disposition = "merged"
                result = "merged"
            else:
                last_closed = con.execute("""SELECT id, close_utc FROM alerts WHERE group_key=? AND state='closed'
                                            ORDER BY id DESC LIMIT 1""", (group,)).fetchone()
                if last_closed and last_closed["close_utc"]:
                    closed_at = datetime.fromisoformat(last_closed["close_utc"])
                    now_dt = datetime.fromisoformat(ts)
                    if timedelta(0) <= now_dt - closed_at < timedelta(seconds=cooldown_seconds):
                        alert_id = last_closed["id"]
                        con.execute("INSERT INTO alert_observations(event_id,alert_id,received_utc,disposition) VALUES(?,?,?,?)",
                                    (decision.event_id, alert_id, ts, "suppressed_cooldown"))
                        con.commit()
                        return {"status": "suppressed_cooldown", "alert_id": alert_id}
                cur = con.execute("""INSERT INTO alerts (group_key,device_id,source,category,zone,severity,
                    provenance,state,first_seen_utc,last_seen_utc,observations,latest_score,reasons_json)
                    VALUES (?,?,?,?,?,?,?,'open',?,?,1,?,?)""",
                    (group, decision.device_id, decision.source, decision.category, decision.zone, decision.severity,
                     decision.provenance, ts, ts, decision.score, json.dumps(decision.reasons, ensure_ascii=False)))
                alert_id = cur.lastrowid
                con.execute("INSERT INTO alert_actions(alert_id,action,actor,note,acted_utc) VALUES(?,'opened','engine','',?)",
                            (alert_id, ts))
                disposition = "opened"
                result = "created"
            con.execute("INSERT INTO alert_observations(event_id,alert_id,received_utc,disposition) VALUES(?,?,?,?)",
                        (decision.event_id, alert_id, ts, disposition))
            con.commit()
            return {"status": result, "alert_id": alert_id}
        except Exception:
            con.rollback()
            raise


def transition(alert_id: int, action: str, actor: str, note: str = "",
               db: str | Path = DEFAULT_DB, now: datetime | None = None) -> dict[str, Any]:
    """Operator acknowledgement (not fix) or closure with audit history."""
    if type(alert_id) is not int or alert_id <= 0:
        raise ValueError("Invalid alert ID")
    if action not in {"acknowledge", "close"}:
        raise ValueError("Action must be acknowledge or close")
    if not isinstance(actor, str) or not 2 <= len(actor.strip()) <= 80:
        raise ValueError("Provide operator name (2-80 characters)")
    if not isinstance(note, str) or len(note) > 1000:
        raise ValueError("Invalid note")
    if action == "close" and not note.strip():
        raise ValueError("Closing requires a resolution note")
    init_db(db)
    ts = _now_str(now)
    with closing(_connection(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            row = con.execute("SELECT state FROM alerts WHERE id=?", (alert_id,)).fetchone()
            if not row:
                raise ValueError("Alert ID not found")
            if action == "acknowledge":
                if row["state"] != "open":
                    raise ValueError("Only open alerts can be acknowledged")
                con.execute("UPDATE alerts SET state='acknowledged', ack_actor=?, ack_utc=? WHERE id=?",
                            (actor.strip(), ts, alert_id))
            else:
                if row["state"] == "closed":
                    raise ValueError("Alert is already closed")
                con.execute("UPDATE alerts SET state='closed', close_actor=?, close_utc=?, close_note=? WHERE id=?",
                            (actor.strip(), ts, note.strip(), alert_id))
            con.execute("INSERT INTO alert_actions(alert_id, action, actor, note, acted_utc) VALUES(?,?,?,?,?)",
                        (alert_id, action, actor.strip(), note.strip(), ts))
            con.commit()
        except Exception:
            con.rollback()
            raise
    return {"alert_id": alert_id, "state": "acknowledged" if action == "acknowledge" else "closed"}


def list_alerts(db: str | Path = DEFAULT_DB, state: str = "all", limit: int = 200) -> list[dict[str, Any]]:
    if state not in STATES | {"all"}:
        raise ValueError("Invalid state filter")
    if not 1 <= limit <= 1000:
        raise ValueError("Limit must be in 1..1000")
    init_db(db)
    with closing(_connection(db)) as con:
        query = "SELECT * FROM alerts"
        params: list[Any] = []
        if state != "all":
            query += " WHERE state=?"
            params.append(state)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [dict(x) for x in con.execute(query, params).fetchall()]


def get_actions(alert_id: int, db: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    init_db(db)
    with closing(_connection(db)) as con:
        return [dict(x) for x in con.execute("SELECT * FROM alert_actions WHERE alert_id=? ORDER BY id", (alert_id,))]


def get_summary(db: str | Path = DEFAULT_DB) -> dict[str, int]:
    init_db(db)
    with closing(_connection(db)) as con:
        counts = {row["state"]: row["n"] for row in con.execute("SELECT state, COUNT(*) AS n FROM alerts GROUP BY state")}
        counts = {k: counts.get(k, 0) for k in ("open", "acknowledged", "closed")}
        counts["total"] = sum(counts.values())
        return counts
