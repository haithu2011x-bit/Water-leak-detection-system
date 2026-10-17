"""Local launcher must not start fake data generators or AI implicitly."""
import unittest
from tools.run_local import commands

class LauncherContractTests(unittest.TestCase):
    def test_safe_default(self):
        specs=commands(python="python",port=8504)
        self.assertEqual([n for n,_ in specs],["MQTT Collector","Dashboard"])
        flat=" ".join(" ".join(parts) for _,parts in specs)
        self.assertNotIn("fake_sensor",flat)
        self.assertNotIn("train_iforest",flat)
        self.assertNotIn("realtime_detection.py",flat)
        self.assertIn("--server.address 127.0.0.1",flat)

    def test_optional_monitor(self):
        specs=commands(python="python",with_collector=False,with_monitor=True,port=8504)
        self.assertEqual([n for n,_ in specs],["Dashboard","MQTT quality monitor"])

    def test_port_guard(self):
        with self.assertRaises(ValueError):
            commands(port=80)

if __name__=="__main__":
    unittest.main()
