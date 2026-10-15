import unittest,json,math
from pathlib import Path
from server import item_models,visuals
from asset_io import manifest
B=Path(__file__).parent
class ItemModelTests(unittest.TestCase):
 def test_allowlisted_model_pairs(self):
  models=item_models();self.assertGreater(len(models),100)
  files=manifest()['files']
  for model,skin in models.items():
   self.assertTrue(files[model]['path'].lower().endswith('.m2'));self.assertTrue(files[skin]['path'].lower().endswith('.skin'))
  self.assertNotIn('../../server.py',models)
 def test_converted_item_geometry(self):
  files=list((B/'assets/item-models-v2').glob('*.json'));self.assertGreaterEqual(len(files),4) # The paired weapons can share one mesh.
  for f in files:
   d=json.loads(f.read_text());n=len(d['positions'])//3
   self.assertTrue(all(math.isfinite(x) for x in d['positions']));self.assertTrue(all(0<=i<n for i in d['indices']))
   self.assertTrue(all(0<=g['start']<=g['start']+g['count']<=len(d['indices']) for g in d['groups']))
 def test_character_mounts(self):
  for p in visuals()['profiles']:
   d=json.loads((B/'assets/models'/Path(p['model']).name).read_text())
   for mount in ('0','1','2','5','6','11'):self.assertEqual(len(d['attachments'][mount]),3)
