"""Temporary SQLite tests: NO fake training data, no access to Project II water.db."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from tools.experiment_service import (utc_now, stream_status, start_session, stop_session,
                                      sample_rows, list_sessions, export_verified_session_csv, session_quality)


class TestExperimentService(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.db = Path(self.t.name) / "test.db"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""CREATE TABLE telemetry (id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_server TEXT NOT NULL, ts_ms INTEGER, flow_main REAL, flow_z1 REAL,
                flow_z2 REAL, pressure_mv REAL, label TEXT DEFAULT '', scenario_id TEXT DEFAULT '',
                device_id TEXT, boot_id TEXT, seq INTEGER)""")

    def tearDown(self):
        self.t.cleanup()

    def add_records(self, labeled=False, epoch=False):
        now = utc_now()
        with closing(sqlite3.connect(self.db)) as con, con:
            for i in range(5):
                timestamp = (now - timedelta(seconds=5-i)).isoformat(timespec="microseconds")
                con.execute("""INSERT INTO telemetry
                (ts_server,ts_ms,flow_main,flow_z1,flow_z2,label,scenario_id,device_id,boot_id,seq)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (timestamp, 1_700_000_000_000+i*1000 if epoch else 10000+i*1000,
                 1.2, 0.7, 0.5, 'leak' if labeled else '', 'leak_z1' if labeled else '',
                 'water-node-01', '0123456789abcdef', i))
            con.commit()

    def test_no_samples_cannot_start(self):
        with self.assertRaises(ValueError):
            start_session('N0', '', confirm_real=True, db=self.db)
        self.assertEqual(len(list_sessions(self.db)), 0)

    def test_reject_old_simulation_signals(self):
        self.add_records(labeled=True, epoch=True)
        result = stream_status(self.db)
        self.assertFalse(result['ready'])
        with self.assertRaises(ValueError):
            start_session('N1', '', confirm_real=True, db=self.db)

    def test_session_lifecycle_without_mutating_telemetry(self):
        self.add_records()
        self.assertTrue(stream_status(self.db)['ready'])
        with self.assertRaises(ValueError):
            start_session('N1', '', confirm_real=False, db=self.db)
        count_before = len(sample_rows(self.db))
        sid = start_session('N1', 'Bơm đang chạy', confirm_real=True, db=self.db)
        self.assertEqual(len(list_sessions(self.db)), 1)
        with self.assertRaises(ValueError):
            start_session('N2', '', confirm_real=True, db=self.db)
        stop_session('Kết thúc', db=self.db)
        self.assertEqual(len(sample_rows(self.db)), count_before)
        self.assertIsNotNone(list_sessions(self.db)[0]['end_utc'])
        self.assertEqual(sid, list_sessions(self.db)[0]['id'])

    def test_export_checks_real_session_and_does_not_overwrite(self):
        self.add_records()
        sid = start_session('N1', 'Kiểm tra bộ xuất', confirm_real=True, db=self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""INSERT INTO telemetry (ts_server,ts_ms,flow_main,flow_z1,flow_z2,device_id,boot_id,seq)
              VALUES (?,?,?,?,?,?,?,?)""", (utc_now().isoformat(timespec='microseconds'), 15000, 0.9, 0.5, 0.4,
              'water-node-01', '0123456789abcdef', 5))
        stop_session('OK', db=self.db)
        csv_bytes = export_verified_session_csv(db=self.db, session_id=sid)
        self.assertIn(b'real_operator_confirmed', csv_bytes)
        self.assertIn(b'N1', csv_bytes)
        self.assertEqual(len(sample_rows(self.db)), 6)

    def test_export_rejects_fake_inside_session(self):
        self.add_records()
        sid = start_session('N1', 'Kiểm tra chặn fake', confirm_real=True, db=self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("""INSERT INTO telemetry (ts_server,ts_ms,flow_main,flow_z1,flow_z2,label,scenario_id,device_id,boot_id,seq)
              VALUES (?,?,?,?,?,?,?,?,?,?)""", (utc_now().isoformat(timespec='microseconds'), 15000, 0.9, 0.5, 0.4, 'normal', 'normal',
              'water-node-01', '0123456789abcdef', 5))
        stop_session('OK', db=self.db)
        with self.assertRaises(ValueError):
            export_verified_session_csv(db=self.db, session_id=sid)

    def test_out_of_band_value_is_counted(self):
        self.add_records()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute('UPDATE telemetry SET flow_z1=0.2 WHERE id=2')
        q = session_quality(self.db)
        self.assertEqual(q['below_range_readings'], 1)


if __name__ == '__main__':
    unittest.main()
