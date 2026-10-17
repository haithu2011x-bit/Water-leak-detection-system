"""Windows-safe schema upgrade test in a temporary DB, never touches project data.

SQLite Connection.__exit__ commits/rolls back but DOES NOT close the file.
Explicit closing is essential for TemporaryDirectory cleanup on Windows.
"""
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import closing
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'backend' / 'collector.py'


class CollectorTest(unittest.TestCase):
    def test_migration_and_messages_preserve_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'backend').mkdir()
            (root / 'data').mkdir()
            target = root / 'backend' / 'collector.py'
            shutil.copy2(SRC, target)
            database = root / 'data' / 'water.db'
            with closing(sqlite3.connect(database)) as con, con:
                con.execute('''CREATE TABLE telemetry (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, ts_server TEXT,
                  ts_ms INTEGER, flow_main REAL, flow_z1 REAL, flow_z2 REAL,
                  pressure_mv REAL, label TEXT, scenario_id TEXT)''')
                con.execute('''INSERT INTO telemetry
                  (ts_server,ts_ms,flow_main,flow_z1,flow_z2,pressure_mv,label,scenario_id)
                  VALUES ('2026-10-15T00:00:00+00:00',9999,2.0,1.0,1.0,2000,'','')''')
            paho = types.ModuleType('paho')
            mqtt_pkg = types.ModuleType('paho.mqtt')
            mqtt_client = types.ModuleType('paho.mqtt.client')
            paho.mqtt = mqtt_pkg
            mqtt_pkg.client = mqtt_client
            old = {k: sys.modules.get(k) for k in ('paho', 'paho.mqtt', 'paho.mqtt.client')}
            sys.modules.update({'paho':paho, 'paho.mqtt':mqtt_pkg, 'paho.mqtt.client':mqtt_client})
            module = None
            try:
                spec = importlib.util.spec_from_file_location('collector_v2_test', target)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                packet = {'device_id': 'water-node-01', 'boot_id': '1234567890abcdef',
                          'seq': 3, 'ts_ms': 3000, 'flow_main': 2.0,
                          'flow_z1': 1.0, 'flow_z2': 1.0}
                msg = types.SimpleNamespace(payload=json.dumps(packet).encode())
                module.on_message(None, None, msg)
                packet['seq'] = 'invalid'
                module.on_message(None, None, types.SimpleNamespace(payload=json.dumps(packet).encode()))
            finally:
                if module is not None:
                    module.con.close()
                for key, original in old.items():
                    if original is None:
                        sys.modules.pop(key, None)
                    else:
                        sys.modules[key] = original
            with closing(sqlite3.connect(database)) as con, con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0], 2)
                self.assertEqual(con.execute('SELECT pressure_mv FROM telemetry WHERE id=1').fetchone()[0], 2000)
                self.assertEqual(con.execute('SELECT seq, boot_id, device_id, label FROM telemetry WHERE id=2').fetchone(),
                                 (3, '1234567890abcdef', 'water-node-01', ''))


if __name__ == '__main__':
    unittest.main()
