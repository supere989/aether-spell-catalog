import json, tempfile, unittest
from pathlib import Path
from unittest import mock
import reloader, paths

class ReloaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.led = Path(self.tmp.name)
        self.p = mock.patch.object(paths, 'path', lambda n: self.led); self.p.start()
    def tearDown(self): self.p.stop(); self.tmp.cleanup()
    def test_static_only_needs_no_restart(self):
        self.assertEqual(reloader.classify(['webui/static/app.js', 'webui/static/style.css']), 'static')
        self.assertEqual(reloader.classify(['webui/static/app.js', 'webui/simulation.py']), 'code')
    def test_failed_candidate_keeps_live(self):
        restarted = []
        row = reloader.attempt(['webui/simulation.py'], run_tests=lambda: (False, 'SyntaxError: invalid syntax'),
                               start_candidate=lambda: None, smoke=lambda: (True, ''), restart=lambda: restarted.append(1))
        self.assertEqual(restarted, []); self.assertEqual(row['result'], 'tests-failed')
        self.assertIn('SyntaxError', json.loads((self.led / 'reload.jsonl').read_text().splitlines()[-1])['error'])
    def test_failed_smoke_keeps_live(self):
        restarted = []
        row = reloader.attempt(['webui/server.py'], run_tests=lambda: (True, ''), start_candidate=lambda: None,
                               smoke=lambda: (False, 'GET / -> 500'), restart=lambda: restarted.append(1))
        self.assertEqual((restarted, row['result']), ([], 'smoke-failed'))
    def test_pass_restarts(self):
        restarted = []
        row = reloader.attempt(['webui/server.py'], run_tests=lambda: (True, ''), start_candidate=lambda: None,
                               smoke=lambda: (True, ''), restart=lambda: restarted.append(1))
        self.assertEqual((restarted, row['result']), ([1], 'reloaded'))
    def test_diff_digest_ledgered(self):
        reloader.attempt(['webui/static/app.js'], None, None, None, None, diffstat=lambda: ' 1 file changed, 2 insertions(+)')
        self.assertEqual(json.loads((self.led / 'reload.jsonl').read_text().splitlines()[-1])['diff'], ' 1 file changed, 2 insertions(+)')
    def test_smoke_scenario_is_accepted(self):
        import simulation
        self.assertIn('outcome', simulation.simulate(json.loads(json.dumps(reloader.SMOKE_SCENARIO))))

class ReloaderRobustnessTest(unittest.TestCase):
    """final review I2 (2026-10-15): the watcher never dies silently, never smokes a stale candidate, and sees edits made while down"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.led = Path(self.tmp.name)
        self.p = mock.patch.object(paths, 'path', lambda n: self.led); self.p.start()
    def tearDown(self): self.p.stop(); self.tmp.cleanup()
    def rows(self): return [json.loads(l) for l in (self.led / 'reload.jsonl').read_text().splitlines()]
    def test_unexpected_exception_is_ledgered_not_fatal(self):
        def boom(): raise OSError('disk full')
        row = reloader.safe_attempt(['webui/server.py'], run_tests=boom, start_candidate=lambda: None, smoke=lambda: (True, ''), restart=lambda: None)
        self.assertEqual(row['result'], 'error'); self.assertIn('disk full', self.rows()[-1]['error'])
    def test_candidate_that_exited_is_not_smoked(self):
        restarted, smoked = [], []
        cand = mock.Mock(); cand.poll.return_value = 1
        row = reloader.attempt(['webui/server.py'], run_tests=lambda: (True, ''), start_candidate=lambda: cand,
                               smoke=lambda: smoked.append(1) or (True, ''), restart=lambda: restarted.append(1))
        self.assertEqual((row['result'], smoked, restarted), ('candidate-exited', [], []))
    def test_candidate_is_killed_when_terminate_hangs(self):
        cand = mock.Mock(); cand.poll.return_value = None
        cand.wait.side_effect = [reloader.subprocess.TimeoutExpired('server', 10), 0]
        reloader.attempt(['webui/server.py'], run_tests=lambda: (True, ''), start_candidate=lambda: cand, smoke=lambda: (True, ''), restart=lambda: None)
        cand.terminate.assert_called_once(); cand.kill.assert_called_once()
    def test_config_toml_is_watched(self):
        root = self.led / 'repo'; (root / 'config').mkdir(parents=True); (root / 'config/paths.toml').write_text('x')
        self.assertIn('config/paths.toml', reloader.scan(root))
    def test_edits_made_while_down_are_noticed(self):
        reloader.save_seen({'webui/server.py': 1.0, 'webui/static/app.js': 2.0})
        self.assertEqual(reloader.changed_since(reloader.load_seen(), {'webui/server.py': 5.0, 'webui/static/app.js': 2.0}), ['webui/server.py'])
        self.assertEqual(reloader.changed_since(None, {'webui/server.py': 5.0}), [])


if __name__ == '__main__': unittest.main()
