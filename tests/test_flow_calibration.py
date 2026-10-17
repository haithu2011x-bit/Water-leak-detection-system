"""Unit tests use synthetic numbers only to verify arithmetic; no sensor claims, no DB."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from flow_calibration import COLUMNS, Trial, load_trials, compute_report, render  # noqa: E402


def demo_trials():
    # Algebra test only: exact 600 pulses per litre for all three sensors.
    rows = []
    for i in range(1, 4):
        for sensor, path in (("MAIN", "Z1_ONLY"), ("Z1", "Z1_ONLY"),
                             ("Z2", "Z2_ONLY")):
            rows.append(Trial(i, f"CAL{i}", "CAL", path, sensor, 1000.0, 600, 60.0))
    for sensor, path in (("MAIN", "Z1_ONLY"), ("Z1", "Z1_ONLY"),
                         ("Z2", "Z2_ONLY")):
        rows.append(Trial(10, "CHECK1", "CHECK", path, sensor, 500.0, 300, 30.0))
    return rows


class CalibrationTests(unittest.TestCase):
    def test_coefficients_and_holdout_checks(self):
        summary, warnings = compute_report(demo_trials())
        self.assertEqual(warnings, [])
        self.assertEqual(set(summary), {"MAIN", "Z1", "Z2"})
        for sensor in summary:
            self.assertAlmostEqual(summary[sensor]["pulses_per_litre"], 600)
            self.assertEqual(summary[sensor]["cal_trials"], 3)
            self.assertEqual(summary[sensor]["check_trials"], 1)
            self.assertAlmostEqual(summary[sensor]["checks"][0]["error_pct"], 0)
        self.assertIn("PULSES_PER_LITER_MAIN = 600.000f", render(summary, warnings, 12, 0))

    def test_requires_three_cal_runs_for_each_sensor(self):
        with self.assertRaisesRegex(ValueError, "MAIN.*3 lan CAL"):
            compute_report([r for r in demo_trials() if not (r.sensor_id == "MAIN" and r.run_id == "CAL1")])

    def test_requires_independent_check(self):
        with self.assertRaisesRegex(ValueError, "CHECK doc lap"):
            compute_report([r for r in demo_trials() if not (r.sensor_id == "Z2" and r.phase == "CHECK")])

    def test_out_of_range_warn(self):
        rows = demo_trials()
        rows[0] = Trial(2, "CAL1", "CAL", "Z1_ONLY", "MAIN", 1000, 600, 250.0)
        _, warnings = compute_report(rows)
        self.assertTrue(any("ngoai dai" in w for w in warnings))

    def test_valid_empty_template(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / "blank.csv"
            with f.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=COLUMNS)
                w.writeheader()
                w.writerow({"run_id": "CAL01", "phase": "CAL", "flow_path": "Z1_ONLY", "sensor_id": "MAIN"})
            complete, blank = load_trials(f)
            self.assertEqual(complete, [])
            self.assertEqual(blank, 1)

    def test_read_positive_delta(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / "data.csv"
            with f.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=COLUMNS)
                w.writeheader()
                w.writerow({"run_id": "T01", "phase": "CAL", "flow_path": "Z1_ONLY",
                            "sensor_id": "Z1", "volume_ml": "500", "pulses_start": "123",
                            "pulses_end": "423", "duration_sec": "30"})
            rows, _ = load_trials(f)
            self.assertEqual(rows[0].pulses, 300)
            self.assertAlmostEqual(rows[0].flow_lpm, 1)
            self.assertAlmostEqual(rows[0].pulses_per_litre, 600)

    def test_partial_entry_is_error(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / "bad.csv"
            with f.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=COLUMNS)
                w.writeheader()
                w.writerow({"run_id": "T01", "phase": "CAL", "flow_path": "Z1_ONLY",
                            "sensor_id": "Z1", "volume_ml": "500"})
            with self.assertRaisesRegex(ValueError, "mot phep do dang nhap do"):
                load_trials(f)

    def test_disallow_path_sensor_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / "bad.csv"
            with f.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=COLUMNS)
                w.writeheader()
                w.writerow({"run_id": "T01", "phase": "CAL", "flow_path": "Z1_ONLY",
                            "sensor_id": "Z2", "volume_ml": "500", "pulses_start": "0",
                            "pulses_end": "300", "duration_sec": "30"})
            with self.assertRaisesRegex(ValueError, "khong phu hop"):
                load_trials(f)

    def test_duplicate_run_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder) / "bad.csv"
            row = {"run_id": "T01", "phase": "CAL", "flow_path": "Z1_ONLY", "sensor_id": "Z1",
                   "volume_ml": "500", "pulses_start": "0", "pulses_end": "300", "duration_sec": "30"}
            with f.open("w", newline="", encoding="utf-8") as h:
                w = csv.DictWriter(h, fieldnames=COLUMNS)
                w.writeheader()
                w.writerow(row)
                w.writerow(row)
            with self.assertRaisesRegex(ValueError, "trung run_id"):
                load_trials(f)


if __name__ == "__main__":
    unittest.main()
