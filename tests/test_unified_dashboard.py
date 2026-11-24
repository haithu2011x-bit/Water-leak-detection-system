"""Tests for the read-only unified dashboard data service; no project DB writes."""
import csv
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tools.unified_dashboard_service import overview, recent_history, quality_log_snapshot, age_seconds

class UnifiedDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        self.db = self.root / 'data' / 'water.db'
        with closing(sqlite3.connect(self.db)) as con:
            con.executescript("""
                CREATE TABLE telemetry (id INTEGER PRIMARY KEY,ts_server TEXT NOT NULL,
                  ts_ms INTEGER,flow_main REAL,flow_z1 REAL,flow_z2 REAL,
                  pressure_mv REAL,label TEXT DEFAULT '',scenario_id TEXT DEFAULT '');
                CREATE TABLE experiment_sessions (id INTEGER PRIMARY KEY,end_utc TEXT);
                CREATE TABLE alerts (id INTEGER PRIMARY KEY,state TEXT);
            """)
            now=datetime.now(timezone.utc)
            con.executemany("""INSERT INTO telemetry
                (id,ts_server,ts_ms,flow_main,flow_z1,flow_z2,label,scenario_id)
                VALUES (?,?,?,?,?,?,?,?)""",[
                (1,(now-timedelta(minutes=3)).isoformat(),1700000000000,2.,1.,1.,'normal','normal'),
                (2,now.isoformat(),10000,0.,0.,0.,'','')])
            con.execute("INSERT INTO experiment_sessions VALUES(1,NULL)")
            con.execute("INSERT INTO experiment_sessions VALUES(2,'2026-10-14')")
            con.execute("INSERT INTO alerts VALUES(1,'open')")
            con.execute("INSERT INTO alerts VALUES(2,'closed')")
            con.commit()

    def test_read_only_overview(self):
        before=self.db.read_bytes()
        snap=overview(self.db)
        self.assertEqual((snap['total'],snap['tagged_history']), (2,1))
        self.assertTrue(snap['recent_row'])
        self.assertEqual(snap['sessions']['active'],1)
        self.assertEqual(snap['alerts']['open'],1)
        self.assertTrue(snap['latest_flows_valid'])
        self.assertEqual(before,self.db.read_bytes())

    def test_history_no_pressure_no_real_assumption(self):
        rows=recent_history(self.db,10)
        self.assertEqual(len(rows),2)
        self.assertNotIn('pressure_mv',rows[0])
        self.assertNotIn('source',rows[0])

    def test_old_labels_not_real(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("UPDATE telemetry SET label='leak' WHERE id=2")
            con.commit()
        self.assertTrue(overview(self.db)['latest_marked_legacy'])

    def test_missing_db_not_created(self):
        missing=self.root/'missing.db'
        with self.assertRaises(FileNotFoundError):
            overview(missing)
        self.assertFalse(missing.exists())

    def test_optional_quality_log(self):
        self.assertIsNone(quality_log_snapshot(self.root)['path'])
        folder=self.root/'data'/'quality'
        folder.mkdir()
        with (folder/'mqtt_quality_v2.csv').open('w',encoding='utf-8-sig',newline='') as fh:
            writer=csv.DictWriter(fh,['kind','received_utc','missing_samples_cumulative'])
            writer.writeheader()
            writer.writerow({'kind':'invalid','received_utc':'2026-10-15T00:00:00+00:00','missing_samples_cumulative':'3'})
        log=quality_log_snapshot(self.root)
        self.assertEqual(log['counts']['invalid'],1)

    def test_utc_datetime(self):
        now=datetime(2026,10,17,10,0,0,tzinfo=timezone.utc)
        self.assertEqual(age_seconds('2026-10-17T09:59:59+00:00',now),1.)
        self.assertIsNone(age_seconds('2026-10-17 10:00:00',now))

if __name__=='__main__':
    unittest.main()
