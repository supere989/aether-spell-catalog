import unittest
from simulation import auto_outcome, defend, defense_settings, simulate
from test_simulation import config

class DefenseTests(unittest.TestCase):
 def test_attack_table(self):
  d=defense_settings(dict(dodge=20,parry=20,block=30,shield_equipped=True,block_value=60))
  for roll,field,left in [(0,'dodges',0),(20,'parries',0),(40,'blocks',40),(69.9,'blocks',40),(70,None,100)]:
   taken,shield,r=defend(100,d,0,roll)
   self.assertEqual(taken,left)
   if field:self.assertEqual(r[field],1)
   self.assertEqual(sum(r[k] for k in ('dodges','parries','blocks')),int(field is not None))
 def test_shield_and_facing(self):
  for settings in [dict(block=100,block_value=100),dict(dodge=100,parry=100,block=100,shield_equipped=True,facing_attacker=False)]:
   self.assertEqual(defend(100,defense_settings(settings),0,0)[0],100)
 def test_absorb_after_block_and_depletion(self):
  d=defense_settings(dict(block=100,shield_equipped=True,block_value=30))
  damage,shield,r=defend(100,d,100,0)
  self.assertEqual((damage,shield,r['blocked'],r['absorbed']),(0,30,30,70))
  self.assertEqual(defend(100,d,shield,0)[:2],(40,0))
  self.assertEqual(defend(100,d,0,None)[0],100)
 def test_full_block(self):
  damage,shield,r=defend(100,defense_settings(dict(block=100,shield_equipped=True,block_value=200)),50,0)
  self.assertEqual((damage,shield,r['blocked']),(0,50,100))
 def test_integration_conservation_repeatability(self):
  c=config();c.update(melee_percent=80,enemy_swing=2,seed=42,enemy_health=10000000,duration=19.5)
  for slot in c['slots']:slot.update(dodge=20,parry=15,block=30,block_value=80,shield_equipped=True,absorb_shield=100)
  r=simulate(c);self.assertEqual(r,simulate(c))
  for m in r['members']:
   self.assertAlmostEqual(m['incoming'],sum(m[k] for k in ('taken','avoided','blocked','absorbed','overkill')))
   self.assertLessEqual(m['absorbed'],100+1e-9)
  self.assertAlmostEqual(sum(m['incoming'] for m in r['members']),350*r['elapsed'])
  self.assertTrue(any(e['kind'] in ('dodge','parry','block') for e in r['events']))
 def test_miss_precedes_avoidance_and_ignores_facing(self):
  d=defense_settings(dict(miss=10,dodge=20,parry=20,block=30,shield_equipped=True,block_value=60))
  for roll,field in [(0,'misses'),(9.99,'misses'),(10,'dodges'),(30,'parries'),(50,'blocks')]:
   damage,shield,r=defend(100,d,100,roll);self.assertEqual(r[field],1)
  d['facing_attacker']=False
  damage,shield,r=defend(100,d,50,0);self.assertEqual((damage,shield,r['misses']),(0,50,1))
  self.assertEqual(defend(100,d,0,None)[0],100)
 def test_glancing_boundaries(self):
  self.assertEqual(auto_outcome(100,60,63,'pve',5,0),(0,'miss',100))
  self.assertEqual(auto_outcome(100,60,63,'pve',5,5),(70,'glancing',30))
  self.assertEqual(auto_outcome(100,60,63,'pve',5,29.99)[1],'glancing')
  self.assertEqual(auto_outcome(100,60,63,'pve',5,30)[1],'hit')
  for level,mode in [(60,'pve'),(59,'pve'),(63,'pvp')]:self.assertEqual(auto_outcome(100,60,level,mode,0,0),(100,'hit',0))
  self.assertEqual(auto_outcome(100,60,83,'pve',0,40)[1],'hit')
 def test_glancing_and_miss_integration(self):
  c=config();c.update(duration=60,incoming_dps=0,enemy_health=10000000,enemy_level=63)
  for slot in c['slots']:slot.update(class_id=12,role='damage',level=60)
  r=simulate(c);self.assertGreater(sum(m['glancing'] for m in r['members']),0)
  self.assertTrue(any(e['ability']=='Auto Attack (glancing)' for e in r['events']))
  for slot in c['slots']:slot['auto_miss']=100
  r=simulate(c);self.assertGreater(sum(m['auto_misses'] for m in r['members']),0)
  self.assertFalse(any(e['kind']=='damage' and e['spell_id']==6603 for e in r['events']))
  self.assertTrue(any(e['kind']=='damage' and e['spell_id']!=6603 for e in r['events']))
 def test_invalid(self):
  for change in [dict(dodge=101),dict(parry=float('nan')),dict(shield_equipped='yes'),dict(absorb_shield=-1)]:
   with self.assertRaises(ValueError):defense_settings(change)
  for change in [dict(seed=.5),dict(enemy_swing=.3),dict(melee_percent=101)]:
   c=config();c.update(change)
   with self.assertRaises(ValueError):simulate(c)
if __name__=='__main__':unittest.main()
