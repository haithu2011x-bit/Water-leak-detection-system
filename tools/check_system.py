"""Kiem tra moi truong va DB, khong sinh data, khong train."""
import importlib.util
import socket
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'water.db'


def main():
    print('Project root:', ROOT)
    print('Python:', sys.version.split()[0])
    for package in ('paho', 'pandas', 'streamlit', 'sklearn', 'joblib'):
        print(f'Thu vien {package:12}:', 'OK' if importlib.util.find_spec(package) else 'THIEU')
    for rel in ('backend/collector.py', 'dashboard/app.py', 'ai/features.py'):
        print(f'File {rel:24}:', 'OK' if (ROOT / rel).is_file() else 'THIEU')
    try:
        with socket.create_connection(('127.0.0.1', 1883), timeout=1):
            print('Mosquitto TCP localhost:1883: CO KET NOI')
    except OSError:
        print('Mosquitto TCP localhost:1883: CHUA KET NOI (kiem tra service Mosquitto)')
    if not DB.is_file():
        print('water.db: CHUA CO - hay chay collector truoc')
        return
    with sqlite3.connect(DB) as c:
        tables = {row[0] for row in c.execute('SELECT name FROM sqlite_master WHERE type="table"')}
        print('water.db: OK | tables:', ', '.join(sorted(tables)))
        if 'telemetry' in tables:
            cols = {r[1] for r in c.execute('PRAGMA table_info(telemetry)')}
            needed = {'id', 'ts_server', 'flow_main', 'flow_z1', 'flow_z2'}
            print('Telemetry columns:', 'OK' if cols.issuperset(needed) else f'THIEU {sorted(needed-cols)}')
            print('Telemetry rows (co the la FAKE):', c.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0])


if __name__ == '__main__':
    main()
