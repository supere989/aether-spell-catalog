import json, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
import server, status

class StatusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler); cls.srv.base_path = ''; cls.srv.public_origin = None
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start(); cls.url = f'http://127.0.0.1:{cls.srv.server_port}'
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close()
    def get(self, path, headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers or {}), timeout=10)
    def test_status_counts_requests(self):
        self.get('/'); s = json.load(self.get('/api/status'))
        self.assertGreaterEqual(s['counters'].get('route:/', 0), 1)
        for k in ('counters', 'engine', 'library', 'reload', 'started'): self.assertIn(k, s)
    def test_status_refused_when_proxied(self):
        with self.assertRaises(urllib.error.HTTPError) as e: self.get('/api/status', {'X-Forwarded-For': '1.2.3.4'})
        self.assertEqual(e.exception.code, 404)
    def test_item_model_rejects_bad_id(self):
        with self.assertRaises(urllib.error.HTTPError) as e: self.get('/api/item-model?id=../../etc/passwd')
        self.assertEqual(e.exception.code, 404)
    def test_prefixed_rewrites_asset_paths(self):
        self.assertEqual(server.prefixed(b'{"a":"/assets/x.png","m":"/models/1-0.json"}', '/simulator'),
                         b'{"a":"/simulator/assets/x.png","m":"/simulator/models/1-0.json"}')
    def test_engine_distribution(self):
        c = status.Counters()
        c.record_run({'slots': [{'class_id': 12}, {'class_id': 13}]},
                     {'events': [{'kind': 'cast', 'actor': 0, 'ability': 'Fire Blast'}, {'kind': 'cast', 'actor': 0, 'ability': 'Fire Blast'},
                                 {'kind': 'dodge', 'actor': 1}, {'kind': 'cast', 'actor': 1, 'ability': 'Heal'}]})
        e = c.snapshot()['engine']
        self.assertEqual(e['casts']['12']['Fire Blast'], 2); self.assertEqual(e['casts']['13']['Heal'], 1)
        self.assertEqual(e['outcomes']['dodge'], 1); self.assertEqual(e['runs'], 1)

class MirrorStatusTest(unittest.TestCase):
    """VM 194 reports its Ascension mirror (release, pin hash, last sync) through /api/status — final review I4"""
    def test_mirror_status(self):
        import tempfile, hashlib
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            m = Path(t); rel = m / 'ascension/releases/20261015-110111'; rel.mkdir(parents=True); (rel / 'pin.json').write_text('{"files": []}')
            (m / 'ascension/current').symlink_to('releases/20261015-110111')
            (m / 'ledger').mkdir(); (m / 'ledger/ascension.jsonl').write_text('{"result": "ok", "release": "20261015-110111"}\n')
            st = status.mirror_status(m)
            self.assertEqual(st['ascension']['current'], '20261015-110111')
            self.assertEqual(st['ascension']['pin_sha256'], hashlib.sha256(b'{"files": []}').hexdigest())
            self.assertEqual(st['ascension']['last']['result'], 'ok')
        self.assertEqual(status.mirror_status(Path('/nonexistent-mirror'))['ascension']['current'], None)


if __name__ == '__main__': unittest.main()
