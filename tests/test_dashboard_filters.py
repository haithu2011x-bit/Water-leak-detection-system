"""Dashboard filter regressions; no SQLite, Streamlit server or device required."""
import unittest
from datetime import date

import numpy as np
import pandas as pd

from dashboard.data_filters import (
    filter_quality_log, filter_telemetry_dates, prepare_telemetry_history,
)


class HistoryTests(unittest.TestCase):
    def test_invalid_and_nonfinite_measurements_are_excluded(self):
        rows = pd.DataFrame([
            (1, "2026-11-09T12:00:00+00:00", "2", "1", "1"),
            (2, "2026-11-10T12:00:00+00:00", 0, 0, 0),
            (3, "bad timestamp", 2, 1, 1),
            (4, "2026-11-10T12:00:00+00:00", -1, 0, 0),
            (5, "2026-11-10T12:00:00+00:00", np.inf, 0, 0),
            (6, "2026-11-10T12:00:00+00:00", "invalid", 0, 0),
        ], columns=["id", "ts_server", "flow_main", "flow_z1", "flow_z2"])
        clean = prepare_telemetry_history(rows)
        self.assertEqual(clean["id"].tolist(), [1, 2])
        self.assertEqual(clean["residual"].tolist(), [0, 0])
        self.assertEqual(str(clean["ts_server"].dt.tz), "UTC")
        self.assertEqual(rows.loc[0, "flow_main"], "2")  # input unchanged

    def test_utc_date_filter_changes_latest_visible_sample(self):
        rows = pd.DataFrame([
            (1, "2026-11-09T23:59:00+00:00", 1, 1, 0),
            (2, "2026-11-10T00:01:00+00:00", 5, 3, 2),
        ], columns=["id", "ts_server", "flow_main", "flow_z1", "flow_z2"])
        clean = prepare_telemetry_history(rows)
        selected = filter_telemetry_dates(clean, (date(2026, 11, 9), date(2026, 11, 9)))
        self.assertEqual(selected["id"].tolist(), [1])
        self.assertEqual(float(selected.iloc[-1]["flow_main"]), 1.0)
        self.assertTrue(filter_telemetry_dates(clean, (date(2026, 11, 11), date(2026, 11, 11))).empty)

    def test_incomplete_date_selection_keeps_data(self):
        rows = pd.DataFrame([
            (1, "2026-11-09T00:00:00+00:00", 1, 1, 0)
        ], columns=["id", "ts_server", "flow_main", "flow_z1", "flow_z2"])
        clean = prepare_telemetry_history(rows)
        self.assertEqual(len(filter_telemetry_dates(clean, (date(2026, 11, 9),))), 1)
        self.assertEqual(len(filter_telemetry_dates(clean, None)), 1)


class QualityLogTests(unittest.TestCase):
    def setUp(self):
        self.logs = pd.DataFrame([
            {"kind": "invalid", "problems": "Field [flow_z1] missing"},
            {"kind": "format_esp32", "problems": "Flow_z1 measured"},
            {"kind": "marked_simulation", "problems": "test event"},
        ])

    def test_literal_search_supports_regex_metacharacters(self):
        self.assertEqual(filter_quality_log(
            self.logs, ["invalid", "format_esp32"], "["
        )["kind"].tolist(), ["invalid"])
        self.assertEqual(filter_quality_log(
            self.logs, ["invalid", "format_esp32"], "FLOW_Z1"
        )["kind"].tolist(), ["invalid", "format_esp32"])
        self.assertTrue(filter_quality_log(self.logs, ["invalid"], "missing)").empty)

    def test_kind_filter_and_empty_query(self):
        self.assertEqual(filter_quality_log(
            self.logs, ["marked_simulation"], " "
        )["kind"].tolist(), ["marked_simulation"])
        self.assertTrue(filter_quality_log(self.logs, [], "").empty)

    def test_legacy_log_without_kind(self):
        self.assertEqual(len(filter_quality_log(
            pd.DataFrame([{"message": "[legacy]"}]), ["unknown"], "[legacy]"
        )), 1)


if __name__ == "__main__":
    unittest.main()
