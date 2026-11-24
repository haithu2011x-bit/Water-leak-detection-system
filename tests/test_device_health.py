"""Offline watchdog contract tests; no MQTT/SQLite activity."""
import unittest
from datetime import datetime,timedelta,timezone
from tools.device_health import offline_decision

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,17,tzinfo=timezone.utc)
    def row(self,seconds_ago=30):
        return dict(device_id="water-node-01",boot_id="0123456789abcdef",seq=200,
                    label="",scenario_id="",
                    ts_server=(self.now-timedelta(seconds=seconds_ago)).isoformat())
    def test_stale_creates_idempotent_offline_event(self):
        a=offline_decision(self.row(),now=self.now)
        b=offline_decision(self.row(),now=self.now)
        self.assertIsNotNone(a)
        self.assertEqual(a.event_id,b.event_id)
        self.assertEqual(a.category,"telemetry_offline")
        self.assertEqual(a.source,"system")
        self.assertNotEqual(a.category,"leak_suspected")
    def test_recent_has_no_offline_alert(self):
        self.assertIsNone(offline_decision(self.row(5),now=self.now))
    def test_legacy_or_fake_not_attributed_to_physical_device(self):
        r=self.row()
        r["label"]="normal"
        self.assertIsNone(offline_decision(r,now=self.now))
        r=self.row()
        r.pop("boot_id")
        self.assertIsNone(offline_decision(r,now=self.now))
    def test_minimum_timeout(self):
        with self.assertRaises(ValueError):
            offline_decision(self.row(),now=self.now,timeout_seconds=3)

if __name__=="__main__":
    unittest.main()
