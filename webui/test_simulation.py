import unittest
from simulation import simulate,CLASSES

def config(n=5):
    return {'size':n,'duration':20,'enemy_health':50000,'incoming_dps':350,'slots':[{'class_id':12+i%21,'role':'tank' if i==0 else 'healer' if i%5==1 else 'damage','power':1,'cost_multiplier':1,'regen':5} for i in range(n)]}
class GroupTests(unittest.TestCase):
    def test_all_sizes_and_conservation(self):
        for n in (5,10,15,25,40):
            r=simulate(config(n));self.assertEqual(len(r['members']),n)
            self.assertTrue(all(0<=m['resource']<=m['resource_cap'] and 0<=m['health']<=m['max_health'] for f in r['frames'] for m in f['members']))
            self.assertAlmostEqual(50000-r['frames'][-1]['enemy_health'],r['damage'],places=2)
            self.assertAlmostEqual(sum(e['amount'] for e in r['events'] if e['kind']=='heal'),r['healing'],delta=.005*len(r['events']))
    def test_all_classes(self):
        seen=set()
        for offset in (0,5,10,15,20):
            c=config()
            for i,s in enumerate(c['slots']):s['class_id']=12+(offset+i)%21;seen.add(s['class_id'])
            self.assertTrue(simulate(c)['frames'])
        self.assertEqual(len(seen),21)
    def test_healing_and_wipe(self):
        r=simulate(config());self.assertGreater(r['healing'],0)
        c=config();c['incoming_dps']=100000
        self.assertEqual(simulate(c)['outcome'],'wipe')
    def test_victory_and_zero_pressure(self):
        c=config();c['incoming_dps']=0;c['enemy_health']=100
        r=simulate(c);self.assertEqual(r['outcome'],'victory');self.assertEqual(r['healing'],0)
        self.assertEqual(r['damage'],100)
    def test_rejection(self):
        c=config();c['size']=6
        with self.assertRaises(ValueError):simulate(c)
        c=config();c['slots'][0]['class_id']=9
        with self.assertRaises(ValueError):simulate(c)
        c=config();c['slots'][0]['regen']=float('nan')
        with self.assertRaises(ValueError):simulate(c)
    def test_deterministic_and_pvp(self):
        c=config();c['mode']='pvp';self.assertEqual(simulate(c),simulate(c))
if __name__=='__main__':unittest.main()
