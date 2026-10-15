import unittest
from equipment import equipped
from class_mechanics import kit
from simulation import simulate
from test_simulation import config
class EquipmentTests(unittest.TestCase):
 def test_add_and_remove(self):
  slot=dict(class_id=12,stamina=150,intellect=150,health=6000,mana=4000,ap=500)
  before=kit(slot)
  slot['gear']={'chest':{'name':'Test','stats':{'stamina':10,'intellect':10,'strength':10,'sp':100}}}
  after=kit(slot)
  self.assertEqual(after['stats']['health'],6100);self.assertEqual(after['stats']['mana'],4150)
  self.assertEqual(after['stats']['ap'],510);self.assertEqual(after['stats']['sp'],600)
  slot['gear']={};self.assertEqual(kit(slot)['stats'],before['stats'])
 def test_weapon_and_shield(self):
  slot=dict(class_id=12,gear={'main_hand':{'name':'Sword','kind':'weapon','weapon_damage':300,'weapon_speed':3},'off_hand':{'name':'Shield','kind':'shield','stats':{'block':20,'block_value':80}}})
  k=kit(slot);self.assertEqual(k['stats']['weapon'],300);self.assertTrue(k['effective_defense']['shield_equipped'])
  slot['gear']['main_hand']['kind']='two_hand'
  with self.assertRaises(ValueError):kit(slot)
  del slot['gear']['off_hand'];self.assertFalse(kit(slot)['effective_defense']['shield_equipped'])
 def test_bad_gear(self):
  for gear in [[],{'bad':{}},{'head':{'stats':{'sp':float('nan')}}},{'head':{'stats':{'unknown':1}}},{'head':{'kind':'shield'}}]:
   with self.assertRaises(ValueError):kit(dict(class_id=12,gear=gear))
 def test_resource_controls(self):
  for cls in range(12,33):
   base=kit(dict(class_id=cls));self.assertIn(base['primary_resource'],base['active_resources'])
   name=base['primary_resource'];k=kit(dict(class_id=cls,resource_settings={name:{'initial':0,'regen':0}}))
   self.assertEqual(k['resources'][name]['initial'],0);self.assertEqual(k['resources'][name]['regen'],0)
  with self.assertRaises(ValueError):kit(dict(class_id=12,resource_settings={'energy':{'initial':101}}))
 def test_equipment_changes_simulation(self):
  c=config();c.update(enemy_health=10000000,incoming_dps=0)
  base=simulate(c)
  c['slots'][0]['gear']={'main_hand':{'name':'Strong weapon','kind':'weapon','weapon_damage':1000,'weapon_speed':2.5,'stats':{'ap':1000}}}
  result=simulate(c);self.assertGreater(result['members'][0]['damage'],base['members'][0]['damage'])
  self.assertEqual(result,simulate(c))
if __name__=='__main__':unittest.main()
