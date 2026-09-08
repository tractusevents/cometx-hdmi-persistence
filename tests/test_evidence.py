import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from correlate import analyze


class PublishedEvidence(unittest.TestCase):
    def result(self,name):
        base=ROOT/'evidence/2026-09-08'
        return analyze(base/'windows'/f'{name}.jsonl',base/'registers'/f'{name}.json')

    def test_inactive_source_disappears_then_recovers(self):
        result=self.result('inactive-b-hpa')
        self.assertEqual(result['samples'],100)
        self.assertEqual([r['active_gdi_monitors'] for r in result['state_observations']],[1,0,1])
        self.assertTrue(result['state_observations'][2]['utc'].startswith('2026-09-08T16:00:23.'))
        self.assertTrue(result['covers_all_recorded_phases'])

    def test_paused_selector_has_no_sampled_loss(self):
        result=self.result('direct-paused')
        self.assertEqual(result['samples'],240)
        self.assertEqual(result['active_counts'],[1])
        self.assertEqual(len(result['state_observations']),1)
        self.assertEqual(result['changed_true_samples'],[])
        self.assertTrue(result['covers_all_recorded_phases'])

    def test_resumed_mcu_has_no_sampled_loss(self):
        result=self.result('direct-resumed')
        self.assertEqual(result['samples'],98)
        self.assertEqual(result['active_counts'],[1])
        self.assertEqual(len(result['state_observations']),1)
        self.assertEqual(result['changed_true_samples'],[result['first_sample']])
        self.assertTrue(result['covers_all_recorded_phases'])
        self.assertEqual(result['gaps_over_1_1_seconds'],[])


class IncompleteInput(unittest.TestCase):
    def run_log(self,lines):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'log.jsonl').write_text('\n'.join(lines),encoding='utf-8')
            (root/'trial.json').write_text(json.dumps({'stdout':'START_UTC=2026-09-08T16:00:00Z\n','exit_status':0}),encoding='utf-8')
            return analyze(root/'log.jsonl',root/'trial.json')

    def record(self,second):
        return json.dumps({'utc':f'2026-09-08T16:00:{second:02}Z','active_gdi_monitors':1,'changed':False})

    def test_truncated_last_line_is_reported(self):
        result=self.run_log([self.record(0),self.record(1),'{"utc":'])
        self.assertEqual(result['samples'],2)
        self.assertEqual(result['ignored_incomplete_terminal_lines'],[3])

    def test_missing_interval_cannot_be_silently_ignored(self):
        with self.assertRaisesRegex(ValueError,'non-terminal'):
            self.run_log([self.record(0),'{broken}',self.record(2)])

    def test_nonincreasing_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'strictly increase'):
            self.run_log([self.record(2),self.record(1)])


if __name__=='__main__':
    unittest.main()
