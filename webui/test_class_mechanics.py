import unittest
from class_mechanics import kit,record,scaled_value,stats,SOURCE
from simulation import simulate
from test_simulation import config
class RealMechanicsTests(unittest.TestCase):
 def test_all_class_kits_are_catalog_spells(self):
  for cl in range(12,33):
   k=kit({'class_id':cl})
   self.assertTrue(k['abilities'])
   for a in k['abilities']:
    self.assertIsNotNone(record(a['id']))
    self.assertNotIn(a['name'],('Quick heal','Heavy attack','Recover'))
 def test_rank_selection(self):
  low=kit({'class_id':12,'level':1});high=kit({'class_id':12,'level':60})
  self.assertIn(801576,[a['id'] for a in low['abilities']])
  a=next(a for a in high['abilities'] if a['root']==801576)
  self.assertNotEqual(a['id'],801576)
 def test_ancestral_strike_ap(self):
  a=record(801576);lo=stats({'level':1,'ap':0,'sp':0});hi={**lo,'ap':1000}
  l,_=scaled_value(a,0,lo,12);h,_=scaled_value(a,0,hi,12)
  self.assertAlmostEqual(h-l,400,places=4)
 def test_flarebolt_source_coefficient(self):
  a=record(800790);lo=stats({'level':1,'sp':0});hi={**lo,'sp':1000}
  l,_=scaled_value(a,0,lo,24);h,_=scaled_value(a,0,hi,24)
  self.assertAlmostEqual(h-l,571,places=4)
 def test_sunflare_source_coefficient(self):
  a=record(800231);lo=stats({'level':1,'sp':0});hi={**lo,'sp':1000}
  l,_=scaled_value(a,0,lo,27);h,_=scaled_value(a,0,hi,27)
  self.assertAlmostEqual(h-l,250,places=4)
 def test_pyromancer_heat_and_embers(self):
  c=config();c.update(duration=60,enemy_health=10000000,incoming_dps=0)
  for s in c['slots']:s.update(class_id=24,role='damage',level=1)
  r=simulate(c)
  self.assertTrue(any(f['members'][0]['custom_resources'].get('Ember',0)>0 for f in r['frames']))
  self.assertTrue(all(f['members'][0]['custom_resources'].get('Heat',0)<100 for f in r['frames']))
 def test_twenty_minutes_and_boundaries(self):
  c=config(40);c.update(duration=1200,enemy_health=10000000,incoming_dps=0)
  # Keep the enemy alive through the entire window with low stat inputs.
  for s in c['slots']:s.update(level=1,power=.1,ap=0,sp=0,weapon=1,rap=0)
  r=simulate(c)
  self.assertEqual(r['elapsed'],1200)
  self.assertEqual(r['frames'][-1]['time'],1200)
  self.assertTrue(any(e['time']>1190 for e in r['events']))
  c['duration']=1200.5
  with self.assertRaises(ValueError):simulate(c)
 def test_costs_never_overdraw(self):
  c=config(25);c.update(duration=90,enemy_health=10000000)
  r=simulate(c)
  for f in r['frames']:
   for m in f['members']:
    self.assertTrue(all(v>=0 for v in m['resources'].values()))
    self.assertTrue(all(v>=0 for v in m['custom_resources'].values()))
if __name__=='__main__':unittest.main()
