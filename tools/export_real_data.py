"""Xuat CSV tu cac phien co nguoi dung xac nhan do THAT, khong dong vao DB goc."""
import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'water.db'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', type=Path, default=DB)
    p.add_argument('--out', type=Path, default=None)
    args = p.parse_args()
    if not args.db.is_file():
        raise SystemExit('Chua co data/water.db')
    with sqlite3.connect(args.db) as con:
        con.row_factory = sqlite3.Row
        has_table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='experiment_sessions'").fetchone()
        if not has_table:
            raise SystemExit('Hay chay python tools/experiment_log.py init truoc.')
        telemetry_cols = {row[1] for row in con.execute('PRAGMA table_info(telemetry)')}
        if 'scenario_id' not in telemetry_cols:
            raise SystemExit('Bang telemetry can cot scenario_id de chan du lieu gia lap khi xuat REAL.')
        sessions = con.execute('''SELECT * FROM experiment_sessions
            WHERE source='real' AND end_utc IS NOT NULL ORDER BY id''').fetchall()
        if not sessions:
            raise SystemExit('Chua co phien thu nghiem REAL hoan tat. Khong xuat du lieu fake.')
        results = []
        for e in sessions:
            samples = con.execute('''SELECT id, ts_server, ts_ms, flow_main, flow_z1, flow_z2,
                     COALESCE(scenario_id, '') AS original_scenario
              FROM telemetry WHERE ts_server >= ? AND ts_server < ? ORDER BY id''',
              (e['start_utc'], e['end_utc'])).fetchall()
            for r in samples:
                # The user's fake_sensor sent Unix epoch milliseconds while
                # the ESP32 contract requires uint32 uptime milliseconds.
                if r['original_scenario']:
                    raise SystemExit(
                        f'Phien #{e["id"]} co mau id={r["id"]} mang scenario gia lap. '
                        'Khong xuat CSV REAL. Kiem tra lai nguon MQTT va nhat ky.'
                    )
                uptime = r['ts_ms']
                if not isinstance(uptime, int) or not (0 <= uptime < 2**32):
                    raise SystemExit(
                        f'Phien #{e["id"]} co ts_ms khong phai ESP32 uptime '
                        f'o id={r["id"]}: {uptime}. Khong xuat CSV REAL.'
                    )
                if any(r[k] is None for k in ('flow_main', 'flow_z1', 'flow_z2')):
                    continue
                results.append({
                    'id': r['id'], 'ts_server': r['ts_server'], 'ts_ms': r['ts_ms'],
                    'flow_main': r['flow_main'], 'flow_z1': r['flow_z1'], 'flow_z2': r['flow_z2'],
                    'label': e['label'], 'scenario_id': e['scenario_code'],
                    'zone': e['zone'], 'experiment_id': e['id'], 'source': 'real_operator_confirmed'
                })
    if not results:
        raise SystemExit('Cac phien REAL hien chua co mau telemetry hop le.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or ROOT / 'data' / 'processed' / f'real_experiments_{stamp}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f'Khong ghi de file CSV co san: {out}')
    with out.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f'Da xuat {len(results)} mau: {out}')
    print('Chu y: source=real_operator_confirmed theo xac nhan cua nguoi thu, KHONG phai xac thuc tu dong.')


if __name__ == '__main__':
    main()
