"""Optional liveness watchdog for a physically commissioned ESP32.

Not AI, not evidence of leakage. Disabled unless a valid operator arming file
is present. Never starts with the normal launcher automatically.
"""
from __future__ import annotations
import argparse
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.detection_guard import DEVICE_ID,arming_reasons,_utc
from tools.realtime_detection import DB,ARMING,read_latest


def offline_decision(row, now=None, timeout_seconds=20):
    """Return a stable liveness event if a previously received v2 row is stale."""
    from tools.alert_service import AlertDecision
    now=now or datetime.now(timezone.utc)
    if timeout_seconds < 10:
        raise ValueError("timeout must be >=10 seconds")
    if not row or row.get("device_id")!=DEVICE_ID or row.get("label") or row.get("scenario_id"):
        return None
    boot=row.get("boot_id")
    seq=row.get("seq")
    t=_utc(row.get("ts_server"))
    if (not isinstance(boot,str) or len(boot)!=16 or
        type(seq) is not int or not 0<=seq<2**32 or t is None):
        return None
    age=(now-t).total_seconds()
    if age < timeout_seconds:
        return None
    return AlertDecision(
        event_id=f"offline:{DEVICE_ID}:{boot}:{seq}",
        device_id=DEVICE_ID,source="system",category="telemetry_offline",zone="unknown",
        severity="warning",reasons=(f"Khong nhan duoc mau telemetry moi tu {age:.0f} giay.",
            "Can kiem tra nguon ESP32, Wi-Fi, broker, Collector; khong suy ra ro ri."),
        provenance="operator_confirmed")


def check(now=None):
    now=now or datetime.now(timezone.utc)
    arming=arming_reasons(ARMING,now)
    if arming:
        return arming,None
    rows,errors=read_latest(DB)
    if errors:
        return errors,None
    if not rows:
        return ["Chua nhan duoc telemetry cua ESP32."],None
    return [],offline_decision(rows[-1],now)


def run():
    parser=argparse.ArgumentParser(description="Post-commissioning MQTT liveness watchdog")
    parser.add_argument("--mode",choices=("check","watch"),default="check")
    parser.add_argument("--interval",type=float,default=5)
    args=parser.parse_args()
    if not 1<=args.interval<=60: parser.error("interval 1..60")
    if args.mode=="check":
        errors,decision=check()
        if errors: print("NOT ARMED:", " | ".join(errors))
        elif decision: print("TELEMETRY STALE:",decision.reasons[0])
        else: print("Device last-known telemetry is recent; no alert created.")
        return
    from tools.alert_service import publish
    print("Watchdog armed only by valid local operator authorization.")
    try:
        while True:
            errors,decision=check()
            if not errors and decision:
                print("OFFLINE:",publish(decision,db=DB))
            elif errors:
                print("DISABLED:", " | ".join(errors[:2]))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped watchdog.")


if __name__=="__main__":
    run()
