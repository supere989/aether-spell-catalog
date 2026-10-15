import json,math,unittest
from pathlib import Path
from asset_io import extract,png
B=Path(__file__).parent
class VisualTests(unittest.TestCase):
 def test_all_meshes_have_valid_geometry(self):
  v=json.loads((B/'assets/visuals.json').read_text());self.assertEqual(len(v['profiles']),20)
  for p in v['profiles']:
   d=json.loads((B/'assets/models'/Path(p['model']).name).read_text());n=len(d['positions'])//3
   self.assertEqual(len(d['normals']),n*3);self.assertEqual(len(d['uv']),n*2)
   self.assertTrue(all(math.isfinite(x) for x in d['positions']))
   self.assertTrue(all(0<=i<n for i in d['indices']))
   self.assertTrue(all(0<=g['start']<=g['start']+g['count']<=len(d['indices']) for g in d['groups']))
 def test_unknown_assets_cannot_escape_cache(self):
  for name in ['../../server.py','/etc/passwd','0'*32]:
   with self.assertRaises(ValueError):extract(name)
   with self.assertRaises(ValueError):png(name)
 def test_no_unproven_class_set_claims(self):
  d=json.loads((B/'gear-catalog.json').read_text())
  for s in d['sets']:
   linked=set(c for bonus in s['bonuses'] for c in bonus['linked_classes'])
   self.assertEqual(set(s['linked_classes']),linked)
