# MQTT v2 — ESP32 with three YF-S401 flow sensors

This document replaces the obsolete v1 contract. Also see [CHUAN_DU_LIEU_V2.md](CHUAN_DU_LIEU_V2.md).

Hardware: ESP32-WROOM-32D, Main / Zone 1 / Zone 2 YF-S401, **no pressure sensor**. Nominal flow range 0.3–6 L/min. Readings 0 < flow < 0.3 are below rated range and cannot be treated as reliable flow measurements.

MQTT topic: `building/water/node1/telemetry`, ~1 sample/second, QoS 0. Laptop Mosquitto usually listens on TCP 1883 in a trusted LAN. ESP32 uses the **laptop LAN IP**, not localhost. Do not expose the broker on the Internet without authentication/network protections.

Example `Docs/mqtt_packet_example.json`:

~~~json
{
  "device_id":"water-node-01",
  "boot_id":"0123456789abcdef",
  "seq":12,
  "ts_ms":152350,
  "flow_main":1.2,
  "flow_z1":0.7,
  "flow_z2":0.5
}
~~~

- `flow_*`: finite L/min >= 0; zero is allowed. Positive values below 0.3 or above 6 are outside the manufacturer's stated nominal measurement range.
- `ts_ms`: ESP32 `millis()` uptime as uint32; NOT Unix epoch.
- `device_id`: logical node ID; `boot_id`: 16 hex characters changed on reboot; `seq`: uint32 incremented for each sample window, even while MQTT is disconnected.
- Physical ESP32 firmware does NOT send `label`, `scenario`, or `pressure_mv`.

The Collector accepts legacy packets without any of the three v2 fields for historical compatibility. If ANY v2 field is present, all three must be valid. Formatted payloads and diagnostic device IDs are NOT source authentication.

## Offline-only validation (does not publish or store)

~~~powershell
.\.venv\Scripts\python.exe tools\validate_packet.py --file Docs\mqtt_packet_example.json
~~~

Expected PASS means only schema valid, NOT physical measurement or sender verified.

## SQLite and experiments

`telemetry` contains server UTC timestamp, uptime, three flows, optional legacy label/scenario, device/boot/seq. A historical `pressure_mv` column, if present, remains untouched but unused. `experiment_sessions` records operator-confirmed REAL session windows separately. Never relabel historical simulated telemetry as real by editing database rows.

MQTT diagnostics are saved in `data/quality/mqtt_quality_v2.csv`. A jump in sequence means sampled windows were not observed by the subscriber, NOT proof of transport-only MQTT loss.

## Physical and inference limitation

The residual `Main - Zone1 - Zone2` alone does not identify leaks downstream of branch meters: legitimate usage and downstream leaks can increase Main and Zone readings similarly. Zone outputs are suspected zones, NOT verified precise locations without controlled experiments.
