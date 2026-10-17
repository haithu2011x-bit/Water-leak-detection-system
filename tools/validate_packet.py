"""Validate ESP32 MQTT v2 JSON without sending MQTT or writing SQLite."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from tools.telemetry_quality import inspect_packet


def validate(packet):
    report=inspect_packet(packet)
    errors=list(report.problems)
    warnings=list(report.warnings)
    if report.device_id is not None and report.device_id != "water-node-01":
        errors.append("unknown device_id: expected water-node-01")
    if report.kind=="marked_simulation":
        warnings.append("scenario/label is NOT an authenticated real measurement")
    return errors,warnings


def main():
    p=argparse.ArgumentParser()
    input_group=p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file",type=Path)
    input_group.add_argument("--json",type=str)
    args=p.parse_args()
    try:
        data=json.loads(args.file.read_text(encoding="utf-8") if args.file else args.json)
    except (OSError,json.JSONDecodeError) as exc:
        raise SystemExit("Cannot read JSON: "+str(exc))
    errors,warnings=validate(data)
    for msg in errors: print("ERROR:",msg)
    for msg in warnings: print("WARN:",msg)
    if errors:
        raise SystemExit(1)
    print("PASS: MQTT packet schema valid (this does NOT authenticate hardware).")


if __name__=="__main__":
    main()
