"""Fail-closed checks for physical-device data and *real-data-approved* AI.

Nothing in this module trains a model, edits SQLite, or assumes MQTT
payloads authenticate a device. Operator declarations must be backed by
actual physical checks; they are not cryptographic authentication.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

DEVICE_ID = "water-node-01"
FLOW_KEYS = ("flow_main", "flow_z1", "flow_z2")
UINT32 = 2**32


def _utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def _load_json(file):
    try:
        obj = json.loads(Path(file).read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def approval_reasons(approval_file, model_file, meta_file):
    """Require independent real-data sign-off and exact model/meta hashes."""
    doc = _load_json(approval_file)
    reasons = []
    if doc is None:
        return ["Chua co file phe duyet mo hinh du lieu that hop le."]
    for key in ("approved", "real_calibrated_data", "independent_real_holdout_passed"):
        if doc.get(key) is not True:
            reasons.append(f"Chua duyet {key}=true.")
    for key in ("reviewed_by", "model_version", "evidence_reference"):
        if not isinstance(doc.get(key), str) or len(doc[key].strip()) < 3:
            reasons.append(f"Thieu {key}.")
    for key, path in (("model_sha256", model_file), ("meta_sha256", meta_file)):
        value = doc.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            reasons.append(f"{key} phai la ma SHA256.")
            continue
        if not Path(path).is_file():
            reasons.append(f"Thieu file: {path}")
        elif _digest(path).lower() != value.lower():
            reasons.append(f"{key} khong khop: model/meta da thay doi.")
    return reasons


def arming_reasons(arming_file, now=None):
    """Time-bounded operator authorization; local safeguard, not MQTT identity proof."""
    doc = _load_json(arming_file)
    if doc is None:
        return ["Chua co cau hinh kich hoat giam sat that."]
    reasons = []
    if doc.get("armed") is not True or doc.get("physical_esp32_verified") is not True:
        reasons.append("Chua bat arming va xac nhan ESP32 vat ly.")
    if doc.get("device_id") != DEVICE_ID:
        reasons.append("Sai device_id arming.")
    if not isinstance(doc.get("operator"), str) or len(doc["operator"].strip()) < 2:
        reasons.append("Thieu nguoi xac nhan.")
    now = now or datetime.now(timezone.utc)
    start, end = _utc(doc.get("verified_at_utc")), _utc(doc.get("expires_at_utc"))
    if start is None or end is None or start > now or now >= end or (end - start).total_seconds() > 86400:
        reasons.append("Phien arming khong hop le, qua han hoac dai hon 24 gio.")
    return reasons


def sample_reasons(rows, now=None, minimum=10):
    """Validate a contiguous v2 ESP32-shaped window; does NOT prove sender identity."""
    now = now or datetime.now(timezone.utc)
    if len(rows) < minimum:
        return ["Can it nhat 10 mau moi lien tiep."]
    rows = list(rows)[-minimum:]
    reasons = []
    boot = rows[0].get("boot_id")
    if not isinstance(boot, str) or len(boot) != 16 or any(c not in "0123456789abcdefABCDEF" for c in boot):
        reasons.append("Thieu boot_id 16 ky tu hexa.")
    previous = None
    for i, row in enumerate(rows):
        if row.get("device_id") != DEVICE_ID or row.get("boot_id") != boot:
            reasons.append("Thay doi device_id/boot_id trong cua so.")
        if row.get("label") or row.get("scenario_id"):
            reasons.append("Mau co nhan gia lap/lich su, khong duoc suy luan.")
        seq, uptime, idx = row.get("seq"), row.get("ts_ms"), row.get("id")
        if type(seq) is not int or not 0 <= seq < UINT32:
            reasons.append("seq khong hop le.")
        if type(uptime) is not int or not 0 <= uptime < UINT32:
            reasons.append("ts_ms khong phai uptime ESP32.")
        if type(idx) is not int or idx < 1:
            reasons.append("id ban ghi khong hop le.")
        t = _utc(row.get("ts_server"))
        if t is None:
            reasons.append("ts_server sai dinh dang UTC.")
        for key in FLOW_KEYS:
            value = row.get(key)
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 6.0:
                reasons.append(f"{key} ngoai dai 0..6 L/min.")
            elif 0 < value < 0.3:
                reasons.append(f"{key} duoi dai dinh muc YF-S401.")
        if previous:
            prev_row, prev_t = previous
            if type(seq) is int and type(prev_row.get("seq")) is int and seq != (prev_row["seq"] + 1) % UINT32:
                reasons.append("seq dut quang/trung/dao thu tu.")
            if type(idx) is int and type(prev_row.get("id")) is int and idx != prev_row["id"] + 1:
                reasons.append("id ban ghi khong lien tuc.")
            if type(uptime) is int and type(prev_row.get("ts_ms")) is int:
                delta = (uptime - prev_row["ts_ms"]) % UINT32
                if not 500 <= delta <= 2500:
                    reasons.append("Thoi gian uptime khong lien tuc.")
            if t and prev_t:
                seconds = (t-prev_t).total_seconds()
                if not 0.5 <= seconds <= 2.5:
                    reasons.append("Khoang thoi gian server khong lien tuc.")
        previous = (row, t)
    last = _utc(rows[-1].get("ts_server"))
    if last is None or not -3 <= (now - last).total_seconds() <= 6:
        reasons.append("Mau cuoi qua cu hoac dong ho sai.")
    return list(dict.fromkeys(reasons))


def model_meta_reasons(meta, expected_features):
    """Check schema; model approval must be checked separately."""
    if not isinstance(meta, dict):
        return ["Metadata mo hinh khong hop le."]
    problems = []
    if meta.get("features") != list(expected_features):
        problems.append("Danh sach feature khong khop.")
    threshold = meta.get("threshold")
    if type(threshold) not in (int, float) or not math.isfinite(threshold):
        problems.append("Nguong AI khong hop le.")
    if not isinstance(meta.get("baseline"), dict):
        problems.append("Thieu baseline duoc kiem chung.")
    return problems
