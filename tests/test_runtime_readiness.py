"""No-model / no-hardware readiness integration tests; uses temporary SQLite."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tools.realtime_detection import status

class SafeReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"measurements.db"
        self.now=datetime.now(timezone.utc)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("""CREATE TABLE telemetry(
                id INTEGER PRIMARY KEY,ts_server TEXT,ts_ms INTEGER,
                flow_main REAL,flow_z1 REAL,flow_z2 REAL,label TEXT,scenario_id TEXT,
                device_id TEXT,boot_id TEXT,seq INTEGER)""")
            for i in range(10):
                con.execute("INSERT INTO telemetry VALUES(?,?,?,?,?,?,?,?,?,?,?)",(
                    i+1,(self.now-timedelta(seconds=9-i)).isoformat(),1000*i,
                    1.0,0.6,0.4,'','','water-node-01','0123456789abcdef',i))
            con.commit()

    def readiness(self):
        return status(db=self.db,model=self.root/'missing.joblib',
                      meta_file=self.root/'missing_meta.json',
                      approval=self.root/'approval.json',
                      arming=self.root/'arming.json',now=self.now)

    def test_no_approval_never_creates_alert_or_model(self):
        before=self.db.read_bytes()
        reasons,meta,rows=self.readiness()
        self.assertTrue(reasons)
        self.assertEqual(len(rows),10)
        self.assertEqual(before,self.db.read_bytes())
        with closing(sqlite3.connect(self.db)) as con:
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("alerts",tables)
        self.assertFalse((self.root/'missing.joblib').exists())

    def test_legacy_label_prevents_real_inference(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("UPDATE telemetry SET scenario_id='leak_z1' WHERE id=9")
            con.commit()
        reasons,_,_=self.readiness()
        self.assertIn("nhan", " ".join(reasons).lower())

if __name__=="__main__":
    unittest.main()
