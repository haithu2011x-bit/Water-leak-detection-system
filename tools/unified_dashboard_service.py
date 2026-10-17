"""Read-only data source for Project II unified dashboard.

Never tags measurements as REAL, never predicts leaks, never trains AI.
Does not create, alter, or delete any SQLite object.
"""
from __future__ import annotations

import csv
import math
import sqlite3
from collections import Counter, deque
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data' / 'water.db'
FLOW = ('flow_main', 'flow_z1', 'flow_z2')


def _open_readonly(db):
    path = Path(db).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Khong tim thay SQLite: {path}')
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _columns(con, table):
    return {r['name'] for r in con.execute(f'PRAGMA table_info({table})')}


def age_seconds(timestamp, now=None):
    if not timestamp:
        return None
    try:
        d = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
        if d.tzinfo is None:
            return None
        now = now or datetime.now(timezone.utc)
        return (now - d.astimezone(timezone.utc)).total_seconds()
    except (ValueError, TypeError, AttributeError):
        return None


def overview(db=DEFAULT_DB, now=None):
    """Informational snapshot. Fresh means a new DB row, not verified hardware."""
    with closing(_open_readonly(db)) as con:
        if not _table_exists(con, 'telemetry'):
            raise ValueError('Database chua co bang telemetry')
        needed = {'id', 'ts_server', *FLOW}
        cols = _columns(con, 'telemetry')
        missing = needed - cols
        if missing:
            raise ValueError('telemetry thieu cot: ' + ', '.join(sorted(missing)))
        labeled_expr = "(COALESCE(label,'') <> '' OR COALESCE(scenario_id,'') <> '')" if {'label', 'scenario_id'} <= cols else '0'
        count = con.execute(f'SELECT COUNT(*) AS total, COALESCE(SUM({labeled_expr}),0) AS tagged FROM telemetry').fetchone()
        optional = [col for col in ('device_id','boot_id','seq','ts_ms','label','scenario_id') if col in cols]
        fields = ['id','ts_server',*FLOW,*optional]
        last = con.execute('SELECT ' + ','.join(fields) + ' FROM telemetry ORDER BY id DESC LIMIT 1').fetchone()
        session_counts = {'total': 0, 'active': 0, 'completed': 0}
        if _table_exists(con, 'experiment_sessions'):
            row = con.execute('SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN end_utc IS NULL THEN 1 ELSE 0 END),0) AS active FROM experiment_sessions').fetchone()
            session_counts = {'total':row['total'], 'active':row['active'], 'completed':row['total']-row['active']}
        alert_counts = {state: 0 for state in ('open','acknowledged','closed')}
        if _table_exists(con, 'alerts'):
            alert_counts.update({r['state']:r['n'] for r in con.execute('SELECT state,COUNT(*) AS n FROM alerts GROUP BY state') if r['state'] in alert_counts})
    last = dict(last) if last else None
    freshness = age_seconds(last['ts_server'], now) if last else None
    annotated = bool(last and (last.get('label') or last.get('scenario_id')))
    flows_valid = bool(last and all(type(last[k]) in (float,int) and math.isfinite(last[k]) and last[k] >= 0 for k in FLOW))
    return {
        'total': count['total'], 'tagged_history': count['tagged'],
        'latest': last, 'age_seconds': freshness,
        'recent_row': freshness is not None and -3 <= freshness <= 12,
        'latest_marked_legacy': annotated, 'latest_flows_valid': flows_valid,
        'sessions': session_counts, 'alerts': alert_counts,
    }


def recent_history(db=DEFAULT_DB, limit=500):
    """Unverified telemetry viewer, intentionally does not attach real/leak labels."""
    limit = min(max(int(limit), 1), 2000)
    with closing(_open_readonly(db)) as con:
        required = {'id', 'ts_server', *FLOW}
        if not required <= _columns(con, 'telemetry'):
            raise ValueError('telemetry thieu cot luu luong')
        rows = con.execute('SELECT id,ts_server,flow_main,flow_z1,flow_z2 FROM telemetry ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(x) for x in reversed(rows)]


def quality_log_snapshot(root=ROOT, limit=300):
    """Read monitor CSV if present; absence is NOT proof of network failure."""
    root = Path(root)
    v2 = root / 'data' / 'quality' / 'mqtt_quality_v2.csv'
    v1 = root / 'data' / 'quality' / 'mqtt_quality.csv'
    file = v2 if v2.is_file() else v1
    if not file.is_file():
        return {'path': None, 'rows': [], 'counts': {}, 'last': None}
    with file.open('r', encoding='utf-8-sig', newline='') as handle:
        rows = list(deque(csv.DictReader(handle), maxlen=min(max(int(limit),1),2000)))
    counts = dict(Counter((r.get('kind') or 'unknown') for r in rows))
    return {'path': str(file), 'rows': rows, 'counts': counts, 'last': rows[-1] if rows else None}
