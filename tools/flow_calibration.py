"""Calibrate 3 flow sensors from REAL manual trials; never publishes MQTT or changes DB.

Compatible with Python >=3.10.  Report needs 3 calibration runs + 1 independent
verification run per sensor. Do not treat placeholder/example data as measurements.
"""
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev

SENSORS = ("MAIN", "Z1", "Z2")
PHASES = ("CAL", "CHECK")
PATHS = {"Z1_ONLY": ("MAIN", "Z1"), "Z2_ONLY": ("MAIN", "Z2")}
COLUMNS = (
    "run_id", "phase", "flow_path", "sensor_id", "volume_ml", "pulses_start",
    "pulses_end", "duration_sec", "notes"
)


@dataclass(frozen=True)
class Trial:
    line: int
    run_id: str
    phase: str
    flow_path: str
    sensor_id: str
    volume_ml: float
    pulses: int
    duration_sec: float

    @property
    def litres(self) -> float:
        return self.volume_ml / 1000.0

    @property
    def pulses_per_litre(self) -> float:
        return self.pulses / self.litres

    @property
    def flow_lpm(self) -> float:
        return self.litres * 60.0 / self.duration_sec


def _read_positive_float(raw: str, field: str, line: int) -> float:
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Dong {line}: {field} khong phai so hop le: {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Dong {line}: {field} phai la so duong, huu han")
    return value


def _read_nonnegative_int(raw: str, field: str, line: int) -> int:
    if not raw.isdigit():
        raise ValueError(f"Dong {line}: {field} phai la so nguyen >= 0")
    return int(raw)


def load_trials(path: Path) -> tuple[list[Trial], int]:
    if not path.is_file():
        raise ValueError(f"Khong tim thay file: {path}")
    completed: list[Trial] = []
    blanks = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValueError(f"CSV phai co cot: {', '.join(COLUMNS)}")
        seen_keys = set()
        for line, record in enumerate(reader, start=2):
            if all(not (record.get(field) or "").strip() for field in COLUMNS):
                continue
            required = ["run_id", "phase", "flow_path", "sensor_id", "volume_ml", "pulses_start", "pulses_end", "duration_sec"]
            # The distributed CSV is intentionally blank in the numeric columns.
            numeric = (record.get("volume_ml") or "").strip()
            pstart = (record.get("pulses_start") or "").strip()
            pend = (record.get("pulses_end") or "").strip()
            duration = (record.get("duration_sec") or "").strip()
            if not (numeric or pstart or pend or duration):
                blanks += 1
                continue
            if any(not (record.get(field) or "").strip() for field in required):
                raise ValueError(f"Dong {line}: mot phep do dang nhap do; can dien du 8 cot bat buoc")
            run_id = record["run_id"].strip()
            phase = record["phase"].strip().upper()
            flow_path = record["flow_path"].strip().upper()
            sensor_id = record["sensor_id"].strip().upper()
            if phase not in PHASES:
                raise ValueError(f"Dong {line}: phase chi nhan CAL / CHECK")
            if flow_path not in PATHS or sensor_id not in PATHS[flow_path]:
                raise ValueError(f"Dong {line}: cam bien {sensor_id} khong phu hop duong nuoc {flow_path}")
            key = (run_id, phase, sensor_id)
            if key in seen_keys:
                raise ValueError(f"Dong {line}: trung run_id + phase + sensor_id: {key}")
            seen_keys.add(key)
            volume = _read_positive_float(numeric, "volume_ml", line)
            start = _read_nonnegative_int(pstart, "pulses_start", line)
            end = _read_nonnegative_int(pend, "pulses_end", line)
            if end <= start:
                raise ValueError(f"Dong {line}: pulses_end phai lon hon pulses_start")
            duration_val = _read_positive_float(duration, "duration_sec", line)
            completed.append(Trial(line, run_id, phase, flow_path, sensor_id, volume,
                                   end - start, duration_val))
    return completed, blanks


def compute_report(trials: list[Trial]) -> tuple[dict, list[str]]:
    summary = {}
    warnings = []
    for trial in trials:
        if not 0.3 <= trial.flow_lpm <= 6:
            warnings.append(
                f"Dong {trial.line}: {trial.sensor_id} ~{trial.flow_lpm:.3f} L/min "
                "ngoai dai 0.3-6; khong nen dung de hieu chuan/chung minh do chinh xac"
            )
    for sensor in SENSORS:
        cal = [t for t in trials if t.sensor_id == sensor and t.phase == "CAL"]
        check = [t for t in trials if t.sensor_id == sensor and t.phase == "CHECK"]
        if len(cal) < 3:
            raise ValueError(f"{sensor}: can toi thieu 3 lan CAL hoan thanh (hien co {len(cal)})")
        if not check:
            raise ValueError(f"{sensor}: can >=1 lan CHECK doc lap (khong dung de tinh he so)")
        # A calibration coefficient from total pulses / total physically measured litres.
        coefficient = sum(t.pulses for t in cal) / sum(t.litres for t in cal)
        coefficients_per_run = [t.pulses_per_litre for t in cal]
        cv_pct = (pstdev(coefficients_per_run) / mean(coefficients_per_run) * 100) if len(cal) > 1 else 0
        checks = []
        for t in check:
            estimated_l = t.pulses / coefficient
            err = (estimated_l / t.litres - 1) * 100
            checks.append({"run_id": t.run_id, "measured_ml": t.volume_ml,
                           "estimated_ml": estimated_l * 1000, "error_pct": err})
            if abs(err) > 5:
                warnings.append(f"{sensor}, CHECK {t.run_id}: sai so {err:+.2f}% >5% (moc can xem xet, khong phai tieu chuan cam bien)")
        if cv_pct > 5:
            warnings.append(f"{sensor}: bien thien he so giua cac lan CAL = {cv_pct:.2f}% >5%, can xem lai dong chay va phep do")
        summary[sensor] = {"pulses_per_litre": coefficient, "cal_trials": len(cal),
                           "check_trials": len(check), "cal_cv_pct": cv_pct, "checks": checks}
    return summary, warnings


def render(summary: dict, warnings: list[str], total_rows: int, blanks: int) -> str:
    lines = ["PROJECT II | HIEU CHUAN 3 FLOW YF-S401 | CHI SO LIEU DO THAT",
             f"So dong hoan chinh: {total_rows}; dong mau chua nhap: {blanks}",
             "He so tinh tu tong xung / tong the tich cua lan CAL, KHONG dung lan CHECK de fit.", ""]
    for sensor in SENSORS:
        s = summary[sensor]
        lines.append(f"{sensor}: PULSES_PER_LITER = {s['pulses_per_litre']:.3f}; "
                     f"CAL={s['cal_trials']}, CHECK={s['check_trials']}, CV_CAL={s['cal_cv_pct']:.2f}%")
        for item in s["checks"]:
            lines.append(f"  CHECK {item['run_id']}: {item['measured_ml']:.1f} mL do that; "
                         f"{item['estimated_ml']:.1f} mL tu xung; sai so {item['error_pct']:+.2f}%")
    lines += ["", "Gia tri dan vao firmware (sau khi xem xet sai so):",
              f"constexpr float PULSES_PER_LITER_MAIN = {summary['MAIN']['pulses_per_litre']:.3f}f;",
              f"constexpr float PULSES_PER_LITER_Z1   = {summary['Z1']['pulses_per_litre']:.3f}f;",
              f"constexpr float PULSES_PER_LITER_Z2   = {summary['Z2']['pulses_per_litre']:.3f}f;"]
    if warnings:
        lines += ["", "CANH BAO / MUC CAN XEM LAI:"] + ["- " + warning for warning in warnings]
    lines += ["", "Luu y: Cac gia tri tren chi phan anh cac phep do da nhap; can xac nhan nguon so lieu."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tinh he so xung/lit tu phep do that, khong can MQTT/AI")
    parser.add_argument("mode", choices=("check", "report"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="TXT bao cao; chi dung voi mode report")
    args = parser.parse_args(argv)
    try:
        trials, blanks = load_trials(args.input)
        print(f"CSV hop le | so dong nhap du: {len(trials)} | so dong de trong: {blanks}")
        if args.mode == "check":
            print("Da kiem tra dinh dang; CHUA tinh he so khi khong co du phep do that.")
            return 0
        if not trials:
            raise ValueError("Chua co so do that; khong duoc tu tao he so xung/lit")
        summary, warnings = compute_report(trials)
        report = render(summary, warnings, len(trials), blanks)
        print(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print(f"Da ghi bao cao: {args.output}")
        return 0
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"LOI: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
