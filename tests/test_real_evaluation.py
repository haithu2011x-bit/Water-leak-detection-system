"""Holdout evaluator tests with deterministic fixtures; NO model training."""
import csv
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from ai.features import FEATURES
from ai.evaluate_real import evaluate

class FixedModel:
    def score_samples(self,frame):
        return [-0.8 for _ in range(len(frame))]

class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.dir=Path(self.t.name)
        self.meta=dict(features=FEATURES,threshold=0.5,experiment_ids=["train-0"])
    def create(self,name,session,label):
        path=self.dir/name
        start=datetime(2026,10,17,tzinfo=timezone.utc)
        columns=["id","ts_server","flow_main","flow_z1","flow_z2","label",
                 "scenario_id","experiment_id","source"]
        with path.open("w",newline="",encoding="utf-8") as file:
            out=csv.DictWriter(file,fieldnames=columns)
            out.writeheader()
            for i in range(30):
                out.writerow(dict(id=i+1,ts_server=(start+timedelta(seconds=i)).isoformat(),
                     flow_main=1.0,flow_z1=0.6,flow_z2=0.4,label=label,
                     scenario_id=("N1" if label=="normal" else "L1"),
                     experiment_id=session,source="real_operator_confirmed"))
        return path
    def test_real_normal_and_leak_holdout(self):
        normal=self.create("n.csv","holdout-normal","normal")
        leak=self.create("l.csv","holdout-leak","leak")
        report=evaluate(FixedModel(),self.meta,[normal,leak])
        self.assertEqual(len(report["holdout_session_ids"]),2)
        self.assertIn("false_positive_rate",report)
        self.assertEqual(report["confusion"]["fn"],0)
        self.assertEqual(report["confusion"]["tn"],0)
    def test_training_session_is_rejected(self):
        old=self.create("old.csv","train-0","normal")
        other=self.create("other.csv","holdout-leak","leak")
        with self.assertRaises(ValueError):
            evaluate(FixedModel(),self.meta,[old,other])
    def test_requires_both_classes(self):
        normal=self.create("n.csv","holdout-normal","normal")
        with self.assertRaises(ValueError):
            evaluate(FixedModel(),self.meta,[normal])

if __name__=="__main__":
    unittest.main()
