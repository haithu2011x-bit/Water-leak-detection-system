import json
import random
import sys
import time

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "building/water/node1/telemetry"
VALID_SCENARIOS = ("normal", "leak_z1", "leak_z2", "leak_main")

scenario = sys.argv[1].lower() if len(sys.argv) > 1 else "normal"
if scenario not in VALID_SCENARIOS:
    raise SystemExit("Choose scenario: " + ", ".join(VALID_SCENARIOS))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(BROKER, PORT, 60)
client.loop_start()
print("Fake sensor (simulation only):", scenario)
print("Publishing MQTT once per second. Ctrl+C to stop.")
try:
    while True:
        z1 = max(0.0, random.normalvariate(1.20, 0.05))
        z2 = max(0.0, random.normalvariate(1.00, 0.05))
        unmetered_leak = 0.0
        if scenario == "leak_z1":
            z1 += max(0.0, random.normalvariate(0.55, 0.03))
        elif scenario == "leak_z2":
            z2 += max(0.0, random.normalvariate(0.55, 0.03))
        elif scenario == "leak_main":
            # Leak between main meter and the two branch meters.
            unmetered_leak = max(0.0, random.normalvariate(0.60, 0.03))

        main = max(0.0, z1 + z2 + unmetered_leak + random.normalvariate(0, 0.03))
        payload = {
            "ts_ms": int(time.time() * 1000),
            "flow_main": round(main, 3),
            "flow_z1": round(z1, 3),
            "flow_z2": round(z2, 3),
            "scenario": scenario,
        }
        message = json.dumps(payload)
        client.publish(TOPIC, message)
        print(message)
        time.sleep(1)
except KeyboardInterrupt:
    print("\nFake sensor stopped.")
finally:
    client.loop_stop()
    client.disconnect()
