import unittest
from gear_catalog import catalog,search_sets,set_detail,resolve_equipment
from class_mechanics import kit
from simulation import simulate
from test_simulation import config

class GearCatalogTests(unittest.TestCase):
 def test_enumeration_and_pagination(self):
  data=catalog();self.assertEqual(data['report']['definitions'],2348)
  self.assertEqual(data['report']['class_specialized_sets'],0)
  self.assertTrue(all(len(i['allowed_classes']) in (0,21) for i in data['items'].values()))
  a=search_sets();b=search_sets(offset=100)
  self.assertEqual(len(a['sets']),100);self.assertFalse({s['id'] for s in a['sets']}&{s['id'] for s in b['sets']})
  self.assertTrue(all(s['has_modeled_stats'] for s in search_sets(stats_only=True)['sets']))
 def example(self):
  d=set_detail(41);gear={}
  for i in sorted(d['items'],key=lambda i:i['id']):
   if i['equippable'] and i['required_level']<=80 and i['slot'] not in gear:gear[i['slot']]={'catalog_id':i['id']}
  self.assertEqual(set(gear),{'main_hand','off_hand'})
  return dict(class_id=12,level=80,gear=gear)
 def test_threshold_and_removal(self):
  s=self.example();_,bonus,sets,_=resolve_equipment(s)
  self.assertEqual(bonus,{'ap':50,'rap':50});self.assertEqual(sets[0]['pieces'],2)
  k=kit(s);self.assertEqual(k['equipment_sets'][0]['bonuses'][0]['modeled'],True)
  s['gear'].pop('off_hand');self.assertEqual(resolve_equipment(s)[1],{})
 def test_canonical_stats_ignore_tampering(self):
  s=self.example();base=kit(s)
  s['gear']['main_hand']['stats']={'ap':999999};s['gear']['main_hand']['name']='fake'
  self.assertEqual(kit(s)['stats'],base['stats'])
 def test_restrictions_and_identity(self):
  s=self.example();piece=s['gear']['main_hand']
  with self.assertRaises(ValueError):kit(dict(class_id=12,gear={'head':piece}))
  with self.assertRaises(ValueError):kit(dict(class_id=12,level=1,gear=s['gear']))
  with self.assertRaises(ValueError):kit(dict(class_id=12,gear={'head':{'catalog_id':-1}}))
  with self.assertRaises(ValueError):kit(dict(class_id=12,gear={'head':{'catalog_id':True}}))
 def test_simulated_set_and_json_roundtrip(self):
  import json
  c=config();c['slots'][0].update(self.example());c['enemy_health']=1000000
  r=simulate(json.loads(json.dumps(c)));self.assertGreater(r['damage'],0)
 def test_unmodeled_bonus_does_not_add_stats(self):
  # Every executable bonus has explicit numeric stats and no hidden execution path.
  for definition in catalog()['sets']:
   for bonus in definition['bonuses']:
    if bonus['modeled']:self.assertTrue(bonus['stats'])
    else:self.assertFalse(bonus['stats'])
if __name__=='__main__':unittest.main()

class ItemPickerTests(unittest.TestCase):
 def test_slot_level_and_paging(self):
  from gear_catalog import search_items
  a=search_items('head',12,60);b=search_items('head',12,60,offset=40)
  self.assertTrue(a['items']);self.assertFalse({i['id'] for i in a['items']}&{i['id'] for i in b['items']})
  for i in a['items']:
   self.assertEqual(i['slot'],'head');self.assertLessEqual(i['required_level'],60);self.assertIn(12,i['allowed_classes'])
  i=a['items'][0];self.assertEqual(search_items('head',12,60,str(i['id']))['items'][0]['id'],i['id'])
 def test_secondary_slots_and_invalid_input(self):
  from gear_catalog import search_items
  for a,b in [('finger1','finger2'),('trinket1','trinket2')]:self.assertEqual(search_items(a,12,80),search_items(b,12,80))
  with self.assertRaises(ValueError):search_items('invalid',12,60)
  with self.assertRaises(ValueError):search_items('head',1,60)
