import importlib
import os
from pathlib import Path
import tempfile
import unittest

class EmotionSyncTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.previous_dir = os.environ.get('MURMUR_DATA_DIR')
        os.environ['MURMUR_DATA_DIR'] = self.folder.name
        import murmur
        self.engine = importlib.reload(murmur)

    def tearDown(self):
        self.folder.cleanup()
        if self.previous_dir is None:
            os.environ.pop('MURMUR_DATA_DIR', None)
        else:
            os.environ['MURMUR_DATA_DIR'] = self.previous_dir

    def test_chat_update_reaches_state_and_history_once_across_restart(self):
        e = self.engine
        payload = {'event_id': 'reply-1', 'initial_drives': {'attachment': .9}, 'changes': {'attachment': .03, 'mischief': .1, 'fatigue': .05}}
        result = e.apply_lumi_update(payload)
        self.assertEqual(result['state']['drives']['attachment']['v'], .93)
        self.assertEqual(result['state']['drives']['fatigue']['v'], .17)
        e.load_state()
        duplicate = e.apply_lumi_update(payload)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['state']['drives']['attachment']['v'], .93)
        e.apply_lumi_update({'initial_drives': {'attachment': .4}, 'online': True})
        self.assertAlmostEqual(e.D['attachment']['v'], .93)
        self.assertEqual(e._offline_ticks, 0)
        rows = [__import__('json').loads(line) for line in e.HISTORY.read_text().splitlines()]
        self.assertEqual(rows[-1]['drives']['attachment'], .93)
        self.assertGreater(rows[-1]['drives']['mischief'], .2)

    def test_invalid_updates_are_atomic_and_bounded(self):
        e = self.engine
        with self.assertRaises(ValueError):
            e.apply_lumi_update({'changes': {'mischief': .1, 'invalid': .1}})
        self.assertEqual(e.D['mischief']['v'], .2)
        result = e.apply_lumi_update({'changes': {'anger': 10, 'fatigue': -10}})
        self.assertEqual(result['state']['drives']['anger']['v'], .28)
        self.assertEqual(result['state']['drives']['fatigue']['v'], 0)

if __name__ == '__main__':
    unittest.main()
