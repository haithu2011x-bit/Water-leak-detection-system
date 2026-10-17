import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from telemetry_quality import inspect_packet, StreamState
from audit_sqlite_quality import check_rows


class TestPacket(unittest.TestCase):
    def test_valid_firmware_shape(self):
        r = inspect_packet(b'{"ts_ms":123456,"flow_main":2.2,"flow_z1":1.2,"flow_z2":1.0}')
        self.assertTrue(r.ok)
        self.assertEqual(r.kind, "format_esp32")
        self.assertEqual(r.ts_ms, 123456)

    def test_simulation_label(self):
        r = inspect_packet({"ts_ms":200, "flow_main":2.2, "flow_z1":1.2, "flow_z2":1.0, "scenario":"normal"})
        self.assertEqual(r.kind, "marked_simulation")

    def test_epoch_not_uptime(self):
        r = inspect_packet({"ts_ms":1770000000000,"flow_main":1,"flow_z1":1,"flow_z2":0})
        self.assertFalse(r.ok)
        self.assertEqual(r.kind, "invalid")

    def test_invalid_json(self):
        self.assertFalse(inspect_packet(b'{INVALID').ok)

    def test_nan_reject(self):
        self.assertFalse(inspect_packet({"ts_ms":1,"flow_main":float("nan"), "flow_z1":0,"flow_z2":0}).ok)

    def test_zero_allowed_and_below_range_warned(self):
        ok = inspect_packet({"ts_ms":1,"flow_main":0,"flow_z1":0,"flow_z2":0})
        self.assertTrue(ok.ok)
        low = inspect_packet({"ts_ms":2,"flow_main":0.2,"flow_z1":0.2,"flow_z2":0})
        self.assertTrue(low.ok)
        self.assertTrue(any("0.3" in message for message in low.warnings))

    def test_stream_gaps_and_reboot(self):
        state = StreamState()
        def row(t):
            return inspect_packet({"ts_ms":t,"flow_main":1,"flow_z1":1,"flow_z2":0})
        state.record(row(100), 0.0)
        flags = state.record(row(1000), 3.0)
        self.assertEqual(state.long_gaps, 1)
        self.assertTrue(flags)
        state.record(row(12), 4.0)
        self.assertEqual(state.reboots_or_rollovers, 1)


class TestAudit(unittest.TestCase):
    def test_read_only_and_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "water.db"
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("""CREATE TABLE telemetry(id INTEGER PRIMARY KEY,ts_server TEXT,ts_ms INTEGER,
                  flow_main REAL,flow_z1 REAL,flow_z2 REAL,label TEXT,scenario_id TEXT)""")
                con.executemany("INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?)", [
                    (1, "2026-10-15T00:00:00+00:00", 1000, 1.0, 0.5, 0.5,"", ""),
                    (2, "2026-10-15T00:00:01+00:00", 2000, 1.1, 0.5, 0.6,"normal", "normal"),
                    (3, "2026-10-15T00:00:06+00:00", 1770000000000, 1.2, 0.5, 0.7,"", ""),
                ])
            result = check_rows(db)
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["counts"].get("format_esp32"), 1)
            self.assertEqual(result["counts"].get("marked_simulation"), 1)
            self.assertEqual(result["counts"].get("invalid"), 1)
            self.assertEqual(result["server_gaps"], 1)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
