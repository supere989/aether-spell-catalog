import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock
import build_library, paths

class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name); self.lib = d / 'lib'; self.led = d / 'ledger'
        self.p = mock.patch.object(paths, 'path', lambda n: {'library': self.lib, 'ledger': self.led}[n]); self.p.start()
    def tearDown(self): self.p.stop(); self.tmp.cleanup()
    def test_texture_written_and_missing_ledgered(self):
        ok = lambda ident: (self.lib / 'assets' / (ident + '.png')).write_bytes(b'png') or True
        def bad(ident): raise ValueError('Client asset could not be extracted')
        r = build_library.run_jobs([('texture', 'a' * 32, None), ('texture', 'b' * 32, None)], workers=1,
                                   texture=lambda i: ok(i) if i.startswith('a') else bad(i), item=None)
        self.assertEqual((r['textures'], r['missing']), (1, 1))
        row = json.loads((self.led / 'missing-assets.jsonl').read_text().splitlines()[0])
        self.assertEqual((row['kind'], row['id']), ('texture', 'b' * 32))
    def test_skips_existing_outputs(self):
        (self.lib / 'assets').mkdir(parents=True); (self.lib / 'assets' / ('c' * 32 + '.png')).write_bytes(b'x')
        calls = []
        build_library.run_jobs([('texture', 'c' * 32, None)], workers=1, texture=calls.append, item=None)
        self.assertEqual(calls, [])
    def test_generation_bumps(self):
        build_library.write_generation({'textures': 1, 'item_models': 0, 'models': 0, 'missing': 0}, 1)
        build_library.write_generation({'textures': 2, 'item_models': 0, 'models': 0, 'missing': 0}, 2)
        g = json.loads((self.lib / 'generation.json').read_text()); self.assertEqual((g['generation'], g['textures']), (2, 2))
    def test_visuals_prefixed(self):
        src = self.lib.parent / 'visuals.json'; src.write_text('{"x":"/assets/' + 'd' * 32 + '.png"}')
        build_library.write_visuals(src); self.assertIn('/simulator/assets/', (self.lib / 'visuals.json').read_text())

    def test_item_model_texture_urls_prefixed(self):
        # served statically by the VPS under /simulator: unprefixed /assets/ URLs 404 publicly (final review C1, 2026-10-15)
        import sys, types
        fake = types.SimpleNamespace(export=lambda ident, skin: {'groups': [{'texture': '/assets/' + 'e' * 32 + '.png'}, {'texture': None}]})
        with mock.patch.dict(sys.modules, {'export_item_mesh': fake}):
            build_library.make_item('f' * 32, 'skin')
        text = (self.lib / 'item-models' / ('f' * 32 + '.json')).read_text()
        self.assertIn('"/simulator/assets/' + 'e' * 32 + '.png"', text); self.assertNotIn('"/assets/', text)
    def test_visuals_carry_generation(self):
        src = self.lib.parent / 'visuals.json'; src.write_text('{"x":"/assets/' + 'd' * 32 + '.png"}')
        build_library.write_visuals(src, 7)
        data = json.loads((self.lib / 'visuals.json').read_text())
        self.assertEqual(data['generation'], 7); self.assertTrue(data['x'].startswith('/simulator/assets/'))
    def test_next_generation(self):
        self.assertEqual(build_library.next_generation(), 1)
        build_library.write_generation({'textures': 0, 'item_models': 0, 'models': 0, 'missing': 0}, 5)
        self.assertEqual(build_library.next_generation(), 6)

if __name__ == '__main__': unittest.main()
