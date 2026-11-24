"""Offline-safe MQTT diagnostic. Uses dedicated topic; never publishes telemetry."""
import argparse
import threading
import uuid
import paho.mqtt.client as mqtt


def main():
    parser = argparse.ArgumentParser(description='Check local Mosquitto without writing sensor data')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=1883)
    args = parser.parse_args()
    topic = 'building/water/diagnostics/selftest/' + uuid.uuid4().hex
    secret = uuid.uuid4().hex
    connected = threading.Event()
    echoed = threading.Event()
    failures = []

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            failures.append('Broker rejected connection: ' + str(reason_code))
        else:
            client.subscribe(topic, qos=1)
        connected.set()

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        client.publish(topic, secret, qos=1, retain=False)

    def on_message(client, userdata, message):
        if message.topic == topic and message.payload.decode('utf-8', errors='replace') == secret:
            echoed.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        client.connect(args.host, args.port, 5)
        client.loop_start()
        if not connected.wait(timeout=5):
            raise RuntimeError('Timeout connecting to MQTT broker')
        if failures:
            raise RuntimeError('; '.join(failures))
        if not echoed.wait(timeout=5):
            raise RuntimeError('Timeout subscribing/publishing to diagnostics topic')
        print('PASS: broker connected; diagnostic MQTT publish/subscribe works')
        print('Topic used:', topic)
        print('No telemetry was sent. Database remains unchanged.')
    except (OSError, RuntimeError) as exc:
        raise SystemExit('FAIL: ' + str(exc))
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == '__main__':
    main()
