"""Tests for v2 sequence-based monitoring. Only in-memory data, no water.db writes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from telemetry_quality import StreamState, inspect_packet

BOOT_A = 'b0a1000000000001'
BOOT_B = 'b0b2000000000002'


def pkt(seq, boot=BOOT_A, uptime=None, *, scenario=None):
    d = {'device_id': 'water-node-01', 'boot_id': boot, 'seq': seq,
         'ts_ms': (1000 + 1000*seq) % (2**32) if uptime is None else uptime,
         'flow_main': 2.0, 'flow_z1': 1.0, 'flow_z2': 1.0}
    if scenario:
        d['scenario'] = scenario
    return inspect_packet(d)


class SequenceTests(unittest.TestCase):
    def test_legacy_packet_still_valid(self):
        report = inspect_packet({'ts_ms': 1000, 'flow_main': 0, 'flow_z1': 0, 'flow_z2': 0})
        self.assertEqual(report.kind, 'format_esp32')
        self.assertIsNone(report.seq)

    def test_new_firmware_packet_is_valid(self):
        report = pkt(0)
        self.assertTrue(report.ok)
        self.assertEqual(report.seq, 0)
        self.assertEqual(report.boot_id, BOOT_A)

    def test_partial_fields_rejected(self):
        report = inspect_packet({'ts_ms': 10, 'flow_main': 2, 'flow_z1': 1, 'flow_z2': 1, 'seq': 2})
        self.assertEqual(report.kind, 'invalid')

    def test_invalid_sequence_rejected(self):
        report = pkt(2**32)
        self.assertEqual(report.kind, 'invalid')
        report = pkt(True)
        self.assertEqual(report.kind, 'invalid')

    def test_gap_counts_sample_windows(self):
        s = StreamState()
        s.record(pkt(10, uptime=10_000), 1.0)
        flags = s.record(pkt(13, uptime=13_000), 4.0)
        self.assertEqual(s.missing_samples, 2)
        self.assertEqual(s.long_gaps, 1)
        self.assertTrue(any('thieu 2 mau' in f for f in flags))

    def test_duplicate_and_out_of_order_do_not_inflate_loss(self):
        s = StreamState()
        for seq in (10, 10, 9, 11):
            s.record(pkt(seq, uptime=1000+seq*1000), seq+1.0)
        self.assertEqual(s.duplicate_seq, 1)
        self.assertEqual(s.out_of_order_seq, 1)
        self.assertEqual(s.missing_samples, 0)

    def test_reboot_starts_new_sequence(self):
        s = StreamState()
        s.record(pkt(99, boot=BOOT_A, uptime=101000), 1.0)
        s.record(pkt(0, boot=BOOT_B, uptime=1000), 2.0)
        self.assertEqual(s.boot_changes, 1)
        self.assertEqual(s.missing_samples, 0)
        self.assertEqual(s.reboots_or_rollovers, 0)

    def test_uint32_wrap(self):
        s = StreamState()
        s.record(pkt(2**32-2, uptime=8000), 1.0)
        s.record(pkt(1, uptime=11000), 2.0)
        self.assertEqual(s.missing_samples, 2)
        self.assertEqual(s.out_of_order_seq, 0)

    def test_simulation_not_counted_as_real_stream(self):
        s = StreamState()
        s.record(pkt(1, scenario='normal'), 1.0)
        s.record(pkt(500, scenario='normal'), 2.0)
        self.assertEqual(s.missing_samples, 0)
        self.assertEqual(s.marked_simulation, 2)


if __name__ == '__main__':
    unittest.main()
