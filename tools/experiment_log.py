"""Ghi nhat ky thu nghiem VAT LY. Khong chinh sua bang telemetry hoac train AI.
Run from project root: python tools/experiment_log.py init|start|stop|status|list
"""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / 'data' / 'water.db'

# Mỗi scenario có nhãn và vị trí kỳ vọng được khóa để tránh nhập sai.
SCENARIOS = {
    'N0': ('normal', 'none', 'Khong dung nuoc'),
    'N1': ('normal', 'z1', 'Chi dung Zone 1 ngat quang'),
    'N2': ('normal', 'z2', 'Chi dung Zone 2 ngat quang'),
    'N3': ('normal', 'both', 'Hai zone dong thoi'),
    'N4': ('normal', 'z1', 'Zone 1 dung lien tuc hop le'),
    'L1': ('leak', 'z1', 'Ro ri nho Zone 1'),
    'L2': ('leak', 'z2', 'Ro ri nho Zone 2'),
    'L3': ('leak', 'z1', 'Ro ri vua Zone 1'),
    'L4': ('leak', 'z2', 'Ro ri vua Zone 2'),
    'L5': ('leak', 'main', 'Ro ri chinh GIUA meter tong va meter nhanh'),
    'F1': ('fault', 'unknown', 'Loi cam bien / mat tin hieu'),
}

CREATE_SQL = '''
CREATE TABLE IF NOT EXISTS experiment_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 scenario_code TEXT NOT NULL,
 label TEXT NOT NULL,
 zone TEXT NOT NULL,
 source TEXT NOT NULL DEFAULT 'real' CHECK(source = 'real'),
 start_utc TEXT NOT NULL,
 end_utc TEXT,
 start_note TEXT NOT NULL DEFAULT '',
 end_note TEXT NOT NULL DEFAULT ''
)
'''


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def db_open(db_path):
    if not db_path.is_file():
        raise SystemExit(f'Khong tim thay database: {db_path}. Hay chay collector truoc.')
    con = sqlite3.connect(str(db_path), timeout=10)
    con.row_factory = sqlite3.Row
    return con


def ensure_table(con):
    con.execute(CREATE_SQL)
    con.commit()


def verify_telemetry(con):
    schema = con.execute('PRAGMA table_info(telemetry)').fetchall()
    columns = {r['name'] for r in schema}
    needed = {'id', 'ts_server', 'flow_main', 'flow_z1', 'flow_z2'}
    if not needed.issubset(columns):
        raise SystemExit(f'Telemetry thieu cot: {sorted(needed - columns)}')


def active_session(con):
    return con.execute('SELECT * FROM experiment_sessions WHERE end_utc IS NULL ORDER BY id DESC LIMIT 1').fetchone()


def cli():
    p = argparse.ArgumentParser(description='Nhat ky thu nghiem REAL, giu nguyen du lieu cu.')
    p.add_argument('--db', type=Path, default=DEFAULT_DB, help='Duong dan data/water.db (de test)')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    start = sub.add_parser('start')
    start.add_argument('--code', required=True, type=str.upper, choices=sorted(SCENARIOS))
    start.add_argument('--confirm-real', action='store_true', required=True,
                       help='Xac nhan da dung fake_sensor va DANG dung thiet bi that')
    start.add_argument('--note', default='', help='Trang thai bom, van, vi tri ro, dieu kien do')
    stop = sub.add_parser('stop')
    stop.add_argument('--note', default='', help='Ghi chu ket thuc, su co, luu luong ro uoc tinh')
    sub.add_parser('status')
    sub.add_parser('list')
    args = p.parse_args()
    with db_open(args.db) as con:
        verify_telemetry(con)
        ensure_table(con)
        running = active_session(con)
        if args.command == 'init':
            print('Da tao/kiem tra bang experiment_sessions. KHONG thay doi telemetry.')
        elif args.command == 'start':
            if running is not None:
                raise SystemExit(f'Chua ket thuc phien #{running["id"]} ({running["scenario_code"]}). Chay stop truoc.')
            label, zone, desc = SCENARIOS[args.code]
            cursor = con.execute('''INSERT INTO experiment_sessions
              (scenario_code,label,zone,source,start_utc,start_note)
              VALUES (?,?,?,"real",?,?)''', (args.code, label, zone, utc_now(), args.note))
            con.commit()
            print(f'BAT DAU #{cursor.lastrowid}: {args.code} ({desc}); nhan={label}; zone={zone}')
            print('Ghi nhan mốc thoi gian server UTC. Khi xong chay: python tools/experiment_log.py stop')
        elif args.command == 'stop':
            if running is None:
                raise SystemExit('Khong co phien dang mo.')
            end = utc_now()
            con.execute('UPDATE experiment_sessions SET end_utc=?, end_note=? WHERE id=?',
                        (end, args.note, running['id']))
            con.commit()
            n = con.execute('''SELECT COUNT(*) FROM telemetry WHERE ts_server >= ? AND ts_server < ?''',
                            (running['start_utc'], end)).fetchone()[0]
            print(f'KET THUC #{running["id"]} ({running["scenario_code"]}). Co {n} dong telemetry trong khoang thoi gian.')
        elif args.command == 'status':
            if running is None:
                print('Khong co phien thu nghiem nao dang mo.')
            else:
                n = con.execute('SELECT COUNT(*) FROM telemetry WHERE ts_server >= ?',
                                (running['start_utc'],)).fetchone()[0]
                print(f'DANG THU #{running["id"]}: {running["scenario_code"]}; bat dau {running["start_utc"]}; {n} mau.')
        elif args.command == 'list':
            rows = con.execute('SELECT * FROM experiment_sessions ORDER BY id DESC LIMIT 25').fetchall()
            for r in rows:
                print(f'#{r["id"]:02} {r["scenario_code"]:2} {r["label"]:6} {r["start_utc"]} => {r["end_utc"] or "DANG THU"}')
            if not rows:
                print('Chua co phien thu nghiem.')


if __name__ == '__main__':
    cli()
