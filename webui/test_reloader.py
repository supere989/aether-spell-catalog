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

if __name__ == '__main__': unittest.main()
