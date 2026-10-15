import copy
import unittest
from evaluate import evaluate, prepare, State, start, apply_events

def ability(identity='bolt', **kwargs):
    return dict(id=identity,reviewed=True,evidence='synthetic test fixture',damage=100,gcd=1,**kwargs)

def profile(**kwargs):
    return dict(mode='dps',duration=6,step=.5,beam_width=24,resources={'mana':{'cap':100,'initial':100,'regen':0}},abilities=[ability()],**kwargs)

class EvaluatorTests(unittest.TestCase):
    def test_resource_conservation(self):
        p=profile(); p['abilities']=[ability(resource='mana',cost=30)]
        r=evaluate(p)
        self.assertEqual(len(r['rotation']),3)
        self.assertEqual(r['damage'],300)
        self.assertEqual(r['resources_remaining']['mana'],10)
        self.assertTrue(all(x['resource_after_cost']['mana']>=0 for x in r['rotation']))
    def test_regeneration_unlocks_casts(self):
        p=profile(); p['resources']['mana']={'cap':20,'initial':0,'regen':10};p['abilities']=[ability(resource='mana',cost=20)]
        r=evaluate(p)
        self.assertEqual([x['time'] for x in r['rotation']],[2,4])
        self.assertEqual(r['damage'],200)
    def test_completion_and_cooldown(self):
        p=profile();p['abilities']=[ability(cast=2,cooldown=2)]
        r=evaluate(p)
        self.assertEqual([x['time'] for x in r['rotation']],[0,4])
        self.assertEqual(r['damage'],200)
    def test_healing_is_bounded_by_damage(self):
        p=profile(incoming_dps=20);p['mode']='hps';p['abilities']=[{'id':'heal','reviewed':True,'evidence':'fixture','healing':100,'gcd':1}]
        r=evaluate(p)
        self.assertLessEqual(r['effective_healing'],120)
        self.assertGreater(r['effective_healing'],0)
        p['incoming_dps']=0
        self.assertEqual(evaluate(p)['effective_healing'],0)
    def test_modifier_recalculates_cost(self):
        p=profile();p['abilities']=[ability(resource='mana',cost=40)]
        before=evaluate(p)
        p['modifiers']=[dict(id='cost-rune',ability_ids=['bolt'],field='cost',operation='multiply',value=.5,reviewed=True,evidence='fixture')]
        after=evaluate(p)
        self.assertEqual(before['damage'],200);self.assertEqual(after['damage'],500)
    def test_rejects_unknown_and_unreviewed(self):
        p=profile();p['abilities'][0]['reviewed']=False
        with self.assertRaises(ValueError): evaluate(p)
        p=profile();p['abilities'][0]['absorb']=100
        with self.assertRaises(ValueError): evaluate(p)
        p=profile();p['modifiers']=[dict(id='x',ability_ids=['absent'],field='cost',operation='add',value=-5,reviewed=True,evidence='fixture')]
        with self.assertRaises(ValueError): evaluate(p)
    def test_movement_range_and_threat(self):
        p=profile(moving_windows=[[0,6]]);p['abilities']=[ability(cast=1)]
        self.assertEqual(evaluate(p)['damage'],0)
        p=profile(distance=50)
        self.assertEqual(evaluate(p)['damage'],0)
        p=profile(threat_safe=False)
        self.assertEqual(evaluate(p)['damage'],0)
    def test_pvp_control_dr_and_survival(self):
        p=profile(incoming_dps=100,health=200);p['mode']='pvp'
        p['abilities']=[ability(control_duration=2,control_category='stun')]
        r=evaluate(p)
        self.assertLessEqual(r['pvp']['control_seconds'],3.5)
        self.assertGreater(r['pvp']['survival_seconds'],2)
        self.assertLessEqual(r['pvp']['survival_seconds'],6)
    def test_periodic_refresh_invalidates_old_ticks(self):
        p=profile();p['abilities']=[ability(periodic_damage=10,period=1,ticks=3)]
        p=prepare(p);a=p['abilities'][0];aa={'bolt':a}
        s=State({'mana':100},10000)
        start(s,a,0,p);apply_events(s,0,p,aa)
        start(s,a,1,p);apply_events(s,1,p,aa)
        apply_events(s,2,p,aa) # previous generation's first tick: no damage
        self.assertEqual(s.damage,200)
        apply_events(s,3,p,aa)
        self.assertEqual(s.damage,210)
    def test_no_free_resource_or_incomplete_damage(self):
        p=profile();p['duration']=1;p['abilities']=[ability(cast=2)]
        self.assertEqual(evaluate(p)['damage'],0)
        p=profile();p['abilities']=[ability(resource='mana',gain=20)];p['resources']['mana']['initial']=95
        self.assertEqual(evaluate(p)['resources_remaining']['mana'],100)
    def test_grid_and_negative_effects_rejected(self):
        p=profile();p['abilities'][0]['cast']=.3
        with self.assertRaises(ValueError): evaluate(p)
        p=profile();p['abilities'][0]['damage']=-1
        with self.assertRaises(ValueError): evaluate(p)
    def test_search_selects_more_efficient_rotation(self):
        p=profile();p['abilities']=[ability('expensive',resource='mana',cost=100),ability('efficient',resource='mana',cost=20)]
        r=evaluate(p)
        self.assertEqual(r['damage'],500)
        self.assertTrue(all(x['ability']=='efficient' for x in r['rotation']))
    def test_silence_blocks_magic_but_not_physical(self):
        p=profile(silenced_windows=[[0,6]])
        p['abilities']=[ability('magic',school='arcane'),ability('physical',school='physical')]
        r=evaluate(p)
        self.assertEqual(r['damage'],600)
        self.assertTrue(all(x['ability']=='physical' for x in r['rotation']))
    def test_damage_stops_at_death(self):
        p=profile(incoming_dps=100,health=50)
        r=evaluate(p)
        self.assertEqual(r['damage'],100)
        self.assertEqual(r['health_remaining'],0)
        self.assertEqual(len(r['rotation']),1)

if __name__=='__main__': unittest.main(verbosity=2)
