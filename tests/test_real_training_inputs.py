"""CSV reader tests only; do not train a model or generate training dataset."""
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai.train_real import load_verified_session, prepare_distinct_sessions

class RealTrainingInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def write(self, name, experiment_id=1, source="real_operator_confirmed", label="normal", count=30):
        path=self.base/name
        start=datetime(2026,10,17,8,0,0,tzinfo=timezone.utc)
        with path.open("w",newline="",encoding="utf-8") as file:
            writer=csv.DictWriter(file,fieldnames=["id","ts_server","flow_main","flow_z1",
                            "flow_z2","source","label","scenario_id","experiment_id"])
            writer.writeheader()
            for i in range(count):
                writer.writerow(dict(id=i+1,ts_server=(start+timedelta(seconds=i)).isoformat(),
                    flow_main=1.0,flow_z1=0.6,flow_z2=0.4,source=source,label=label,
                    scenario_id="N1",experiment_id=experiment_id))
        return path

    def test_valid_operator_confirmed_csv(self):
        path=self.write("a.csv")
        data,features,session=load_verified_session(path)
        self.assertEqual(session,"1")
        self.assertEqual(len(data),30)
        self.assertGreaterEqual(len(features),20)

    def test_refuse_fake_source(self):
        path=self.write("fake.csv",source="simulation")
        with self.assertRaises(ValueError):
            load_verified_session(path)

    def test_refuse_leak_in_normal_training(self):
        path=self.write("leak.csv",label="leak")
        with self.assertRaises(ValueError):
            load_verified_session(path)

    def test_no_leakage_by_experiment_id(self):
        a=self.write("train.csv",experiment_id=5)
        b=self.write("valid.csv",experiment_id=5)
        with self.assertRaises(ValueError):
            prepare_distinct_sessions([a],[b])

    def test_disjoint_sessions_allowed(self):
        a=self.write("train.csv",experiment_id=5)
        b=self.write("valid.csv",experiment_id=6)
        tr,va,_,ids=prepare_distinct_sessions([a],[b])
        self.assertEqual(len(ids),2)
        self.assertEqual(len(tr),len(va))

    def test_low_range_rejected(self):
        path=self.write("x.csv")
        lines=path.read_text().splitlines()
        # sixth column is flow_z2? Header: id, ts_server, main, z1, z2, ...
        row=lines[2].split(",")
        row[4]="0.2"
        lines[2]=",".join(row)
        path.write_text("\n".join(lines)+"\n")
        with self.assertRaises(ValueError):
            load_verified_session(path)

if __name__=="__main__":
    unittest.main()
