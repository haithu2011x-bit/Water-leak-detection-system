"""Read-only real-time detection until all explicit physical/model gates pass.

NEVER starts model training and NEVER uses fake_sensor.py. By default this
program only reports readiness. Alert writes require --watch, a currently valid
operator arming file and independently approved REAL model artifacts.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.detection_guard import (DEVICE_ID, approval_reasons, arming_reasons,
                                   model_meta_reasons, sample_reasons)

DB = ROOT / "data" / "water.db"
MODEL = ROOT / "ai" / "iforest.joblib"
META = ROOT / "ai" / "iforest_meta.json"
APPROVAL = ROOT / "config" / "model_approval.json"
ARMING = ROOT / "config" / "runtime_arming.json"

ROWS_SQL = """SELECT id,ts_server,ts_ms,flow_main,flow_z1,flow_z2,
              COALESCE(label,'') AS label, COALESCE(scenario_id,'') AS scenario_id,
              device_id,boot_id,seq
              FROM telemetry ORDER BY id DESC LIMIT 60"""


def read_latest(db=DB):
    """Read-only: missing tables and old schema become explicit NOT READY."""
    if not Path(db).is_file():
        return [], ["Chua co water.db tren may."]
    try:
        path = Path(db).resolve()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as con:
            con.row_factory = sqlite3.Row
            columns = {r[1] for r in con.execute("PRAGMA table_info(telemetry)")}
            required = {"id","ts_server","ts_ms","flow_main","flow_z1","flow_z2",
                        "label","scenario_id","device_id","boot_id","seq"}
            if required - columns:
                return [], ["Telemetry chua du cot MQTT v2: " + ",".join(sorted(required-columns))]
            return list(reversed([dict(x) for x in con.execute(ROWS_SQL)])), []
    except sqlite3.Error as exc:
        return [], ["Khong the doc telemetry: " + str(exc)]


def artifacts_ready(approval=APPROVAL, model=MODEL, meta_file=META, arming=ARMING, now=None):
    reasons = approval_reasons(approval, model, meta_file)
    reasons.extend(arming_reasons(arming, now=now))
    meta = None
    if not reasons:
        try:
            meta = json.loads(Path(meta_file).read_text(encoding="utf-8"))
            from ai.features import FEATURES
            reasons.extend(model_meta_reasons(meta, FEATURES))
        except (OSError, ValueError, TypeError) as exc:
            reasons.append("Khong doc duoc metadata: " + str(exc))
    return reasons, meta


def candidate_zone(feature_row, meta):
    """Only a tentative zone; single-flow residual can miss downstream leaks."""
    baseline = meta.get("baseline", {})
    try:
        res_baseline = baseline["residual"]
        res = float(feature_row["balance_residual"])
        if res - float(res_baseline["median"]) > max(0.2, 4*float(res_baseline["std"])):
            return "main", "Mat can bang so voi baseline"
        z1, z2 = baseline["z1"], baseline["z2"]
        d1 = float(feature_row["z1_mean_10"]) - float(z1["median"])
        d2 = float(feature_row["z2_mean_10"]) - float(z2["median"])
        hi1 = d1 > max(0.2, 4*float(z1["std"]))
        hi2 = d2 > max(0.2, 4*float(z2["std"]))
        if hi1 and not hi2:
            return "zone1", "Zone 1 tang so voi baseline"
        if hi2 and not hi1:
            return "zone2", "Zone 2 tang so voi baseline"
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return "unknown", "Luu luong khong du de xac dinh vi tri"


def decide(model, meta, rows, model_version, consecutive_anomalies=0, now=None):
    """Return (decision or None, new streak). Pure except local ML scoring."""
    from ai.features import FEATURES, make_features
    from tools.alert_service import AlertDecision

    problems = sample_reasons(rows[-10:], now=now)
    if problems:
        raise ValueError("Nguon du lieu khong du dieu kien: " + " | ".join(problems))
    if model_meta_reasons(meta, FEATURES):
        raise ValueError("Metadata/model chua duoc phe duyet day du.")
    import pandas as pd
    data = make_features(pd.DataFrame(rows))
    if data.empty or int(data.iloc[-1]["id"]) != int(rows[-1]["id"]):
        raise ValueError("Chua co 10 mau lien tuc de tinh feature.")
    row = data.iloc[-1]
    score = -float(model.score_samples(row[FEATURES].to_frame().T)[0])
    if not math.isfinite(score):
        raise ValueError("AI tra ve diem khong huu han.")
    abnormal = score > float(meta["threshold"])
    streak = consecutive_anomalies + 1 if abnormal else 0
    if streak < 3:
        return None, streak
    zone, reason = candidate_zone(row, meta)
    newest = rows[-1]
    return AlertDecision(
        event_id=f"{newest['device_id']}:{newest['boot_id']}:{newest['seq']}:{model_version}",
        device_id=DEVICE_ID, source="ai", category="leak_suspected",
        zone=zone, severity="warning",
        reasons=(f"3+ mau AI bat thuong lien tiep; score={score:.5f}; threshold={float(meta['threshold']):.5f}",
                 f"Vi tri NGHI NGO: {reason}. Can kiem tra thuc dia."),
        score=score, provenance="operator_confirmed",
    ), streak


def status(db=DB, model=MODEL, meta_file=META, approval=APPROVAL, arming=ARMING, now=None):
    now = now or datetime.now(timezone.utc)
    issues, meta = artifacts_ready(approval, model, meta_file, arming, now)
    rows, errors = read_latest(db)
    issues.extend(errors)
    if not errors:
        issues.extend(sample_reasons(rows[-10:], now=now))
    return list(dict.fromkeys(issues)), meta, rows


def watch(args):
    from tools.alert_service import publish
    import joblib
    model = None
    last_id = None
    streak = 0
    last_boot = None
    print("Runtime safety mode: all gates checked on each poll; Ctrl+C to stop.")
    try:
        while True:
            problems, meta, rows = status(now=datetime.now(timezone.utc))
            if problems:
                model, streak, last_boot = None, 0, None
                print("NOT READY: " + " | ".join(problems[:3]))
            elif rows:
                current = rows[-1]
                if last_id is None:
                    last_id = current["id"]  # never replay historic values on startup
                    print("LIVE window armed; waiting for a NEW sample.")
                elif current["id"] != last_id:
                    last_id = current["id"]
                    if last_boot != current["boot_id"]:
                        streak = 0
                        last_boot = current["boot_id"]
                    try:
                        if model is None:
                            model = joblib.load(MODEL)  # approval hash already checked
                        decision, streak = decide(model, meta, rows, json.loads(
                            APPROVAL.read_text(encoding="utf-8"))["model_version"], streak)
                        if decision is not None:
                            result = publish(decision, db=DB)
                            print("ALERT:", result, decision.zone)
                        else:
                            print("Validated sample:", current["id"], "anomaly streak:", streak)
                    except (ValueError, TypeError, KeyError, OSError) as exc:
                        streak = 0
                        print("SAFE SKIP:", exc)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped monitoring.")


def main():
    parser = argparse.ArgumentParser(description="Fail-closed Project II AI detector")
    parser.add_argument("--mode", choices=("check","watch"), default="check")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if not 0.5 <= args.interval <= 60:
        parser.error("interval must be 0.5..60s")
    if args.mode == "check":
        reasons, _, _ = status()
        if reasons:
            print("NOT READY (expected before physical experiments):")
            for issue in reasons:
                print(" -", issue)
        else:
            print("Gates PASS; model is operator-approved, but this is not hardware authentication.")
        return
    watch(args)


if __name__ == "__main__":
    main()
