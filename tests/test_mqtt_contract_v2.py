"""MQTT v2 contract examples stay aligned with shared validator."""
import json
import unittest
from pathlib import Path
from tools.validate_packet import validate

ROOT=Path(__file__).resolve().parents[1]

class MQTTContractTests(unittest.TestCase):
    def packet(self):
        return json.loads((ROOT/"Docs"/"mqtt_packet_example.json").read_text(encoding="utf-8"))
    def test_example_v2_passes(self):
        errors,warnings=validate(self.packet())
        self.assertFalse(errors,errors)
    def test_partial_metadata_rejected(self):
        p=self.packet()
        del p["boot_id"]
        errors,_=validate(p)
        self.assertTrue(errors)
    def test_epoch_timestamp_rejected(self):
        p=self.packet()
        p["ts_ms"]=1700000000000
        errors,_=validate(p)
        self.assertTrue(errors)
    def test_unknown_id_rejected(self):
        p=self.packet()
        p["device_id"]="rogue-node"
        errors,_=validate(p)
        self.assertTrue(errors)
    def test_pressure_not_required(self):
        p=self.packet()
        self.assertNotIn("pressure_mv",p)
        self.assertEqual(validate(p)[0],[])

if __name__=="__main__":
    unittest.main()
