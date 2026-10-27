"""Launcher does not start fake data or AI; supports optional USB Serial."""
import unittest
from tools.run_local import commands


class LauncherContractTests(unittest.TestCase):
    def test_safe_mqtt_default_is_unchanged(self):
        specs = commands(python="python", port=8504)
        self.assertEqual([n for n, _ in specs], ["MQTT Collector", "Dashboard"])
        flat = " ".join(" ".join(parts) for _, parts in specs)
        for forbidden in ("fake_sensor", "train_iforest", "realtime_detection.py"):
            self.assertNotIn(forbidden, flat)
        self.assertIn("--server.address 127.0.0.1", flat)

    def test_optional_mqtt_monitor(self):
        specs = commands(python="python", with_collector=False, with_monitor=True, port=8504)
        self.assertEqual([n for n, _ in specs], ["Dashboard", "MQTT quality monitor"])

    def test_usb_serial_option(self):
        specs = commands(python="python", transport="serial", serial_port="COM5", port=8504)
        self.assertEqual([n for n, _ in specs], ["USB Serial Collector", "Dashboard"])
        self.assertEqual(specs[0][1][-4:], ["--port", "COM5", "--baud", "115200"])
        self.assertNotIn("collector.py", " ".join(specs[0][1]).replace("serial_collector.py", ""))

    def test_guards(self):
        with self.assertRaises(ValueError):
            commands(port=80)
        with self.assertRaises(ValueError):
            commands(transport="serial")
        with self.assertRaises(ValueError):
            commands(transport="serial", serial_port="COM5", with_monitor=True)


if __name__ == "__main__":
    unittest.main()
