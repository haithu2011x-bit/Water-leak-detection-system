"""Read-only validation helpers for Project II ESP32 3-flow telemetry.

No database writes, no AI training. Format match is NOT physical provenance.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

FLOW_KEYS = ("flow_main", "flow_z1", "flow_z2")
UINT32_LIMIT = 2**32


@dataclass(frozen=True)
class PacketReport:
    kind: str  # format_esp32 | marked_simulation | invalid
    problems: tuple[str, ...]
    warnings: tuple[str, ...]
    ts_ms: int | None
    flows: tuple[float, float, float] | None
    device_id: str | None = None
    boot_id: str | None = None
    seq: int | None = None

    @property
    def ok(self) -> bool:
        return not self.problems


def inspect_packet(payload: bytes | str | dict[str, Any]) -> PacketReport:
    """Inspect packet. An ESP32-shaped packet is NOT authenticated as real data."""
    try:
        if isinstance(payload, bytes):
            if len(payload) > 8192:
                raise ValueError("JSON payload vuot 8192 byte")
            raw = payload.decode("utf-8", errors="strict")
            data = json.loads(raw)
        elif isinstance(payload, str):
            if len(payload.encode("utf-8")) > 8192:
                raise ValueError("JSON payload vuot 8192 byte")
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise ValueError("Payload khong phai JSON hoac dictionary")
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        return PacketReport("invalid", (f"JSON loi: {exc}",), (), None, None)

    if not isinstance(data, dict):
        return PacketReport("invalid", ("Root JSON phai la object",), (), None, None)

    problems: list[str] = []
    warnings: list[str] = []
    readings: list[float] = []
    for name in FLOW_KEYS:
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"{name}: phai la so")
            continue
        try:
            number = float(value)
        except (OverflowError, ValueError):
            problems.append(f"{name}: khong chuyen duoc thanh float")
            continue
        if not math.isfinite(number) or number < 0:
            problems.append(f"{name}: am/NaN/Infinity")
        else:
            readings.append(number)
            if number > 6.0:
                warnings.append(f"{name}: tren 6 L/min, ngoai dai tham khao YF-S401")
            elif 0.0 < number < 0.3:
                warnings.append(f"{name}: duoi 0.3 L/min, can kiem tra sai so tai luu luong thap")

    stamp = data.get("ts_ms")
    ts_ms: int | None = None
    if isinstance(stamp, bool) or not isinstance(stamp, int):
        problems.append("ts_ms: phai la so nguyen millis() cua ESP32")
    elif stamp < 0 or stamp >= UINT32_LIMIT:
        problems.append("ts_ms: ngoai dai uptime uint32 cua ESP32 (co the la epoch ms gia lap)")
    else:
        ts_ms = stamp

    is_marked_sim = bool(str(data.get("scenario", "")).strip()) or bool(str(data.get("label", "")).strip())
    if is_marked_sim:
        warnings.append("ban tin co scenario/label: khong xac nhan la du lieu that")

    if len(readings) == 3:
        main, z1, z2 = readings
        residual = main - z1 - z2
        if abs(residual) > max(0.15, 0.10 * max(main, 1.0)):
            warnings.append(f"chenh lech Main-Z1-Z2={residual:+.3f} L/min (chi la canh bao kiem tra)")

    # v2 diagnostic fields: optional for legacy packets, all required if any present.
    diagnostic_fields = ("device_id", "boot_id", "seq")
    diagnostic_present = [key in data for key in diagnostic_fields]
    device_id = boot_id = seq = None
    if any(diagnostic_present):
        if not all(diagnostic_present):
            problems.append("v2: can day du device_id, boot_id, seq")
        else:
            device_id, boot_id, seq = (data[key] for key in diagnostic_fields)
            if not isinstance(device_id, str) or not device_id or len(device_id) > 64:
                problems.append("device_id khong hop le")
            if not isinstance(boot_id, str) or len(boot_id) != 16 or any(ch not in "0123456789abcdefABCDEF" for ch in boot_id):
                problems.append("boot_id phai gom 16 ky tu hex")
            if type(seq) is not int or not 0 <= seq < UINT32_LIMIT:
                problems.append("seq phai la uint32")
    kind = "invalid" if problems else ("marked_simulation" if is_marked_sim else "format_esp32")
    flows = tuple(readings) if len(readings) == 3 else None
    return PacketReport(kind, tuple(problems), tuple(warnings), ts_ms, flows, device_id, boot_id, seq)


@dataclass
class StreamState:
    """Track timing and sample sequence quality for one MQTT node."""
    last_uptime: int | None = None
    last_receive_mono: float | None = None
    received: int = 0
    valid_shape: int = 0
    invalid: int = 0
    marked_simulation: int = 0
    long_gaps: int = 0
    reboots_or_rollovers: int = 0
    duplicate_uptime: int = 0
    last_seq: int | None = None
    last_boot_id: str | None = None
    last_device_id: str | None = None
    missing_samples: int = 0
    duplicate_seq: int = 0
    out_of_order_seq: int = 0
    boot_changes: int = 0

    def record(self, report: PacketReport, now_mono: float, gap_seconds: float = 2.5) -> tuple[str, ...]:
        details: list[str] = []
        self.received += 1
        if report.kind == "invalid":
            self.invalid += 1
        elif report.kind == "marked_simulation":
            self.marked_simulation += 1
        else:
            self.valid_shape += 1

        if self.last_receive_mono is not None:
            age = now_mono - self.last_receive_mono
            if age > gap_seconds:
                self.long_gaps += 1
                details.append(f"khoang cach nhan {age:.2f}s > {gap_seconds:.2f}s")
        self.last_receive_mono = now_mono
        if report.ts_ms is not None and report.kind != "invalid":
            boot_is_new = (report.boot_id is not None and self.last_boot_id is not None and report.boot_id != self.last_boot_id)
            if self.last_uptime is not None and not boot_is_new:
                if report.ts_ms == self.last_uptime:
                    self.duplicate_uptime += 1
                    details.append("ts_ms trung nhau")
                elif report.ts_ms < self.last_uptime:
                    self.reboots_or_rollovers += 1
                    details.append("ts_ms giam: co the ESP32 reset, tran millis, hoac tin dao thu tu")
            self.last_uptime = report.ts_ms

        if report.kind == "format_esp32" and report.seq is not None:
            # Diagnostic count, not proof of MQTT transport loss: the sender may
            # have been offline or its publish call may have failed.
            new_stream = self.last_boot_id != report.boot_id or self.last_device_id != report.device_id
            if new_stream:
                if self.last_boot_id is not None:
                    self.boot_changes += 1
                    details.append("boot_id thay doi: bat dau phien ESP32 moi")
                self.last_seq = report.seq
                self.last_boot_id = report.boot_id
                self.last_device_id = report.device_id
                self.last_uptime = report.ts_ms  # new boot's uptime base
            elif self.last_seq is not None:
                prior = self.last_seq
                current = report.seq
                if current == prior:
                    self.duplicate_seq += 1
                    details.append(f"seq trung: {current}")
                elif current > prior:
                    skipped = current - prior - 1
                    if skipped:
                        self.missing_samples += skipped
                        details.append(f"thieu {skipped} mau theo seq ({prior}->{current})")
                    self.last_seq = current
                elif prior >= UINT32_LIMIT - 1000 and current <= 1000:
                    skipped = (UINT32_LIMIT - prior + current) - 1
                    if skipped:
                        self.missing_samples += skipped
                        details.append(f"thieu {skipped} mau tai diem wrap seq")
                    self.last_seq = current
                else:
                    self.out_of_order_seq += 1
                    details.append(f"seq giam/dao thu tu ({prior}->{current})")
        return tuple(details)
