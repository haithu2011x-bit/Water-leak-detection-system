"""Kiem tra JSON giao tiep MQTT theo cam bien flow-only, KHONG publish hay luu data."""
import argparse
import json
import math
from pathlib import Path

FLOW_KEYS = ('flow_main', 'flow_z1', 'flow_z2')


def validate(packet):
    errors, warnings = [], []
    if not isinstance(packet, dict):
        return ['JSON phai la object'], []
    if 'pressure_mv' in packet:
        warnings.append('pressure_mv khong con duoc su dung; bo khoi firmware')
    if 'ts_ms' not in packet:
        errors.append('Thieu ts_ms (uptime cua ESP32, milliseconds)')
    elif type(packet['ts_ms']) is not int or packet['ts_ms'] < 0:
        errors.append('ts_ms phai la so nguyen >=0')
    for key in FLOW_KEYS:
        if key not in packet:
            errors.append(f'Thieu {key}')
            continue
        try:
            if isinstance(packet[key], bool):
                raise ValueError('boolean')
            val = float(packet[key])
            if not math.isfinite(val) or val < 0:
                raise ValueError('khong hop le')
        except (TypeError, ValueError):
            errors.append(f'{key} phai la so thuc huu han >=0')
            continue
        if 0 < val < 0.3:
            warnings.append(f'{key}={val:.3f}: nho hon dai do da xac nhan 0.3-6 L/phut')
        if val > 6:
            warnings.append(f'{key}={val:.3f}: lon hon dai do da xac nhan 0.3-6 L/phut')
    if all(k in packet for k in FLOW_KEYS) and not errors:
        main, z1, z2 = map(float, (packet[k] for k in FLOW_KEYS))
        if z1 + z2 > main + 0.30:
            warnings.append('Tong 2 nhanh lon hon dong tong qua 0.30 L/phut; kiem tra dong bo/ hieu chuan')
    return errors, warnings


def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', type=Path)
    group.add_argument('--json', type=str)
    args = p.parse_args()
    try:
        packet = json.loads(args.file.read_text(encoding='utf-8') if args.file else args.json)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f'Khong doc duoc JSON: {exc}')
    errors, warnings = validate(packet)
    for s in errors: print('ERROR:', s)
    for s in warnings: print('WARN:', s)
    if errors:
        raise SystemExit(1)
    print('PASS: du 3 flow va ts_ms; khong can cam bien ap suat')


if __name__ == '__main__':
    main()
