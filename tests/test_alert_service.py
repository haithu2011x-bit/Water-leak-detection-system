import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.alert_service import (AlertDecision, get_actions, get_summary, init_db,
                                 list_alerts, publish, transition)

BASE = datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)


class AlertServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "data" / "water.db"

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, event_id="evt-1", **overrides):
        data = dict(event_id=event_id, device_id="water-node-01", source="ai",
                    category="leak_suspected", zone="zone2", severity="warning",
                    reasons=("Z2 above baseline",), score=0.61, provenance="unverified")
        data.update(overrides)
        return AlertDecision(**data)

    def test_init_preserves_legacy_telemetry(self):
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE telemetry(id INTEGER PRIMARY KEY, flow_main REAL, pressure_mv REAL)")
            con.execute("INSERT INTO telemetry VALUES (1, 2.4, 1810)")
            con.commit()
        init_db(self.db)
        init_db(self.db)
        with closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("SELECT * FROM telemetry").fetchall(), [(1, 2.4, 1810.0)])
            self.assertEqual(len(con.execute("SELECT name FROM sqlite_master WHERE name IN ('alerts','alert_actions','alert_observations')").fetchall()), 3)

    def test_empty_engine_does_not_create_fake_alerts(self):
        init_db(self.db)
        self.assertEqual(get_summary(self.db), {"open": 0, "acknowledged": 0, "closed": 0, "total": 0})
        self.assertEqual(list_alerts(self.db), [])

    def test_publish_idempotent(self):
        first = publish(self.event(), self.db, now=BASE)
        retry = publish(self.event(), self.db, now=BASE + timedelta(seconds=1))
        self.assertEqual(first, {"status": "created", "alert_id": 1})
        self.assertEqual(retry, {"status": "duplicate_event", "alert_id": 1})
        self.assertEqual(list_alerts(self.db)[0]["observations"], 1)

    def test_merge_same_group_escalates_but_does_not_reopen(self):
        publish(self.event("e1"), self.db, now=BASE)
        transition(1, "acknowledge", "operator", db=self.db, now=BASE + timedelta(seconds=2))
        res = publish(self.event("e2", severity="critical", reasons=("Several consecutive anomalies",)),
                      self.db, now=BASE + timedelta(seconds=3))
        self.assertEqual(res["status"], "merged")
        a = list_alerts(self.db)[0]
        self.assertEqual((a["observations"], a["severity"], a["state"]), (2, "critical", "acknowledged"))

    def test_close_requires_note_and_records_audit(self):
        publish(self.event(), self.db, now=BASE)
        with self.assertRaisesRegex(ValueError, "resolution note"):
            transition(1, "close", "operator", db=self.db)
        transition(1, "acknowledge", "operator", note="Checking", db=self.db)
        closed = transition(1, "close", "operator", "Inspected branch and reset manual valve", db=self.db, now=BASE)
        self.assertEqual(closed["state"], "closed")
        self.assertEqual([a["action"] for a in get_actions(1, self.db)], ["opened", "acknowledge", "close"])
        with self.assertRaisesRegex(ValueError, "already closed"):
            transition(1, "close", "operator", "Again", db=self.db)

    def test_cooldown_suppresses_then_creates_new_incident(self):
        publish(self.event("e1"), self.db, now=BASE)
        transition(1, "close", "operator", "Checked", db=self.db, now=BASE + timedelta(seconds=10))
        r = publish(self.event("e2"), self.db, now=BASE + timedelta(seconds=15), cooldown_seconds=60)
        self.assertEqual(r["status"], "suppressed_cooldown")
        self.assertEqual(publish(self.event("e2"), self.db, now=BASE + timedelta(seconds=20))["status"], "duplicate_event")
        self.assertEqual(get_summary(self.db)["total"], 1)
        self.assertEqual(publish(self.event("e3"), self.db, now=BASE + timedelta(seconds=71))["status"], "created")
        self.assertEqual(get_summary(self.db)["total"], 2)

    def test_other_zone_device_and_source_are_separate(self):
        publish(self.event("e1"), self.db)
        publish(self.event("e2", zone="zone1"), self.db)
        publish(self.event("e3", device_id="water-node-02"), self.db)
        publish(self.event("e4", source="hybrid"), self.db)
        self.assertEqual(get_summary(self.db)["open"], 4)

    def test_invalid_payload_cannot_mutate_db(self):
        import math
        for value in (
            self.event("x1", provenance="simulation"),
            self.event("x2", score=float("nan")),
            self.event("x3", reasons=()),
            self.event("x4", zone="zone9"),
            self.event("x5", severity="extreme"),
        ):
            with self.assertRaises(ValueError):
                publish(value, self.db)
        self.assertEqual(get_summary(self.db)["total"], 0)

    def test_no_cross_event_duplicate(self):
        publish(self.event("same"), self.db, now=BASE)
        # Reused ID for another zone is duplicate, not a new alert.
        r = publish(self.event("same", zone="zone1"), self.db, now=BASE)
        self.assertEqual(r["status"], "duplicate_event")
        self.assertEqual(get_summary(self.db)["total"], 1)

    def test_invalid_transitions_and_unknown_id(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            transition(99, "acknowledge", "operator", db=self.db)
        publish(self.event(), self.db)
        transition(1, "acknowledge", "operator", db=self.db)
        with self.assertRaisesRegex(ValueError, "Only open"):
            transition(1, "acknowledge", "operator", db=self.db)
        self.assertEqual(get_summary(self.db)["acknowledged"], 1)

    def test_independent_db_files(self):
        other = Path(self.tmp.name) / "other.sqlite3"
        publish(self.event("e1"), self.db)
        self.assertEqual(get_summary(other)["total"], 0)
        self.assertEqual(get_summary(self.db)["total"], 1)

    def test_list_filters_states(self):
        publish(self.event("e1"), self.db)
        publish(self.event("e2", zone="zone1"), self.db)
        transition(1, "close", "operator", "Resolved", db=self.db)
        self.assertEqual(len(list_alerts(self.db, state="closed")), 1)
        self.assertEqual(len(list_alerts(self.db, state="open")), 1)


if __name__ == "__main__":
    unittest.main()
