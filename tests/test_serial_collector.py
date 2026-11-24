"""No physical USB needed; all database checks use disposable temp SQLite."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.serial_collector import open_database, parse_line, save_packet


GOOD = {
    "device_id": "water-node-01", "boot_id": "0123456789abcdef",
    "seq": 42, "ts_ms": 14500, "flow_main": 2.0,
    "flow_z1": 1.2, "flow_z2": 0.8,
}


class USBSerialCollectorTests(unittest.TestCase):
    def test_valid_line_and_duplicate_are_unlabeled(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "water.db"
            with closing(open_database(db)) as con:
                packet, error = parse_line((json.dumps(GOOD) + "\n").encode())
                self.assertIsNone(error)
                self.assertTrue(save_packet(con, packet))
                self.assertFalse(save_packet(con, packet))
                self.assertEqual(con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT label,scenario_id,device_id,seq FROM telemetry").fetchone(),
                                 ("", "", "water-node-01", 42))

    def test_existing_pressure_column_and_historical_row_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "water.db"
            with closing(sqlite3.connect(db)) as con:
                con.execute("""CREATE TABLE telemetry (id INTEGER PRIMARY KEY,
                    ts_server TEXT,ts_ms INTEGER,flow_main REAL,flow_z1 REAL,
                    flow_z2 REAL,pressure_mv REAL,label TEXT,scenario_id TEXT)""")
                con.execute("""INSERT INTO telemetry (id,ts_server,pressure_mv)
                    VALUES (1,'previous',2000)""")
                con.commit()
            with closing(open_database(db)) as con:
                self.assertEqual(con.execute("SELECT pressure_mv FROM telemetry WHERE id=1").fetchone()[0], 2000)
                self.assertTrue(save_packet(con, GOOD))
                self.assertEqual(con.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0], 2)

    def test_ignore_serial_boot_and_reject_untrusted_shape(self):
        self.assertEqual(parse_line(b"USB SERIAL: boot\n"), (None, None))
        self.assertIsNotNone(parse_line(b"{invalid\n")[1])
        for change in ({"scenario": "leak_z1"}, {"seq": "wrong"},
                       {"device_id": "other"}, {"flow_z1": -1},
                       {"boot_id": None}):
            packet, error = parse_line(json.dumps({**GOOD, **change}))
            self.assertIsNone(packet)
            self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
