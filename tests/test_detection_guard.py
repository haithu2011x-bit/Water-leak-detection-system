"""Safe AI gates: synthetic rows are UNIT FIXTURES only, not training data."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.detection_guard import approval_reasons, arming_reasons, sample_reasons
from tools.realtime_detection import decide, candidate_zone

class ToyScore:
    def __init__(self, negative_score=-0.95):
        self.value = negative_score
    def score_samples(self, frame):
        return [self.value] * len(frame)

def fixture(now=None):
    now = now or datetime.now(timezone.utc)
    rows=[]
    for i in range(10):
        rows.append(dict(id=i+1, ts_server=(now-timedelta(seconds=9-i)).isoformat(),
                         ts_ms=100000+1000*i, flow_main=1.0,flow_z1=0.6,flow_z2=0.4,
                         device_id='water-node-01',boot_id='0123456789abcdef',seq=i,
                         label='',scenario_id=''))
    return rows

class DetectionGateTests(unittest.TestCase):
    def test_ten_good_v2_samples(self):
        self.assertEqual(sample_reasons(fixture()), [])

    def test_fake_labeled_or_incomplete_rejected(self):
        rows=fixture()
        rows[-1]['scenario_id']='leak_z1'
        self.assertTrue(sample_reasons(rows))
        rows=fixture()
        rows[-1]['seq']+=3
        self.assertTrue(sample_reasons(rows))
        rows=fixture()
        rows[5]['device_id']='untrusted'
        self.assertTrue(sample_reasons(rows))

    def test_flow_below_spec_rejected(self):
        rows=fixture()
        rows[6]['flow_z1']=0.2
        self.assertIn('flow_z1', ' '.join(sample_reasons(rows)))

    def test_expired_arming_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'arming.json'
            now=datetime.now(timezone.utc)
            p.write_text(json.dumps(dict(armed=True,physical_esp32_verified=True,
                device_id='water-node-01',operator='tester',
                verified_at_utc=(now-timedelta(hours=27)).isoformat(),
                expires_at_utc=(now-timedelta(hours=25)).isoformat())),encoding='utf-8')
            self.assertTrue(arming_reasons(p,now))

    def test_missing_real_model_approval_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            self.assertTrue(approval_reasons(p/'none',p/'x.joblib',p/'x.json'))

    def test_model_hash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            model=p/'m.bin'
            meta=p/'meta.json'
            model.write_bytes(b'approved')
            meta.write_text('{}', encoding='utf-8')
            conf=p/'approval.json'
            conf.write_text(json.dumps(dict(approved=True, real_calibrated_data=True,
                independent_real_holdout_passed=True, reviewed_by='operator',
                model_version='real-v1', evidence_reference='test/log/001',
                model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                meta_sha256=hashlib.sha256(meta.read_bytes()).hexdigest())))
            self.assertEqual(approval_reasons(conf,model,meta),[])
            model.write_bytes(b'tampered')
            self.assertTrue(approval_reasons(conf,model,meta))

    def test_three_consecutive_anomalies_required(self):
        from ai.features import FEATURES
        meta=dict(features=FEATURES,threshold=0.55,baseline={
            'residual':{'median':0,'std':0.01},
            'z1':{'median':0.6,'std':0.01},
            'z2':{'median':0.4,'std':0.01}})
        now=datetime.now(timezone.utc)
        rows=fixture(now)
        decision,streak=decide(ToyScore(),meta,rows,'real-v1',0,now=now)
        self.assertIsNone(decision)
        self.assertEqual(streak,1)
        decision,streak=decide(ToyScore(),meta,rows,'real-v1',streak,now=now)
        self.assertIsNone(decision)
        decision,streak=decide(ToyScore(),meta,rows,'real-v1',streak,now=now)
        self.assertEqual(decision.category,'leak_suspected')
        self.assertEqual(decision.provenance,'operator_confirmed')
        self.assertEqual(streak,3)
        self.assertIn('real-v1',decision.event_id)

    def test_cannot_claim_location_without_baseline(self):
        zone,_=candidate_zone({'balance_residual':0,'z1_mean_10':0.6,'z2_mean_10':0.4}, {})
        self.assertEqual(zone,'unknown')

if __name__=='__main__':
    unittest.main()
