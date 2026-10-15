"""Shared-party, fixed-step illustrative combat simulation."""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'planner'))
from evaluate import prepare, State, legal, start
CLASSES = ['Barbarian','Witch Doctor','Felsworn','Witch Hunter','Stormbringer','Knight of Xoroth','Guardian','Templar','Bloodmage','Ranger','Chronomancer','Necromancer','Pyromancer','Cultist','Starcaller','Sun Cleric','Tinker','Venomancer','Reaper','Primalist','Runemaster']
SIZES=(5,10,15,25,40)
MELEE={12,14,15,17,18,19,30,31,32}

def bounded(value,name,lo,hi):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi: raise ValueError(f'{name} must be {lo}..{hi}')
    return value

def profile(slot,duration):
    cls=slot.get('class_id'); role=slot.get('role')
    if cls not in range(12,33) or role not in ('tank','healer','damage'): raise ValueError('Invalid class/role')
    power=bounded(slot.get('power',1),'power',.1,5)
    efficiency=bounded(slot.get('cost_multiplier',1),'cost multiplier',.25,2)
    regen=bounded(slot.get('regen',5),'regeneration',0,30)
    def a(i,**kw): return dict(id=i,name=i,reviewed=True,evidence='Synthetic role template; not native CoA abilities',resource='mana',school='physical' if cls in MELEE else 'arcane',**kw)
    if role=='healer':
        abilities=[a('Quick heal',cost=12,healing=190*power,cast=1,gcd=1.5),a('Greater heal',cost=30,healing=470*power,cast=2,gcd=1.5)]
    else:
        abilities=[a('Strike' if cls in MELEE else 'Bolt',cost=12,damage=(100 if role=='tank' else 170)*power,cast=0 if cls in MELEE else 1.5,gcd=1.5),a('Heavy attack',cost=30,damage=(210 if role=='tank' else 390)*power,cast=1.5,gcd=1.5,cooldown=6)]
    abilities.append(a('Recover',gain=35,cast=2,gcd=1.5,cooldown=8))
    p={'mode':'dps','duration':min(duration,180),'step':.5,'beam_width':12,'resources':{'mana':{'initial':120,'cap':120,'regen':regen}},'health':4000 if role=='tank' else 2200,'abilities':abilities,
       'modifiers':[dict(id='experimental-cost-adjustment',ability_ids=[x['id'] for x in abilities if x.get('cost')],field='cost',operation='multiply',value=efficiency,reviewed=True,evidence='User-selected synthetic tuning input; not a live rune')]}
    prepared=prepare(p)
    prepared["duration"]=duration
    return prepared

def simulate(config):
    slots=config.get('slots',[]); size=config.get('size',len(slots))
    if size not in SIZES or len(slots)!=size: raise ValueError('Choose exactly 5, 10, 15, 25 or 40 slots')
    duration=bounded(config.get('duration',60),'duration',5,1200)
    if duration%0.5: raise ValueError('Duration must align to 0.5s')
    boss_max=bounded(config.get('enemy_health',50000),'enemy health',100,10000000)
    pressure=bounded(config.get('incoming_dps',350),'incoming DPS',0,100000)
    mode=config.get('mode','pve')
    if mode not in ('pve','pvp'): raise ValueError('Invalid mode')
    ps=[profile(s,duration) for s in slots]
    states=[State({'mana':120},p['health']) for p in ps]
    totals=[{'damage':0.,'healing':0.,'overheal':0.,'taken':0.,'casts':0} for _ in slots]
    pending=[]; events=[]; frames=[]; boss=boss_max; duration_run=0
    def log(t,actor,kind,amount=0,target=None,ability=None):
        events.append({'time':t,'actor':actor,'kind':kind,'amount':round(amount,2),'target':target,'ability':ability})
    def resolve(t):
        nonlocal boss,pending
        due=[e for e in pending if e[0]==t];pending=[e for e in pending if e[0]!=t]
        for _,i,a,target in due:
            s=states[i]
            if s.dead: continue
            if a['damage']:
                value=min(boss,a['damage']);boss-=value;totals[i]['damage']+=value
                log(t*.5,i,'damage',value,'enemy',a['id'])
            if a['healing'] and target is not None and not states[target].dead:
                value=min(a['healing'],ps[target]['health']-states[target].health)
                states[target].health+=value;totals[i]['healing']+=value;totals[i]['overheal']+=a['healing']-value
                log(t*.5,i,'heal',value,target,a['id'])
            if a['gain']:
                gain=min(a['gain'],120-s.resources['mana']);s.resources['mana']+=gain
                log(t*.5,i,'resource',gain,i,a['id'])
    def frame(t):
        frames.append({'time':t,'enemy_health':round(boss,2),'members':[{'health':round(s.health,2),'max_health':ps[i]['health'],'resource':round(s.resources['mana'],2),'dead':s.dead,'casting':next((a['id'] for end,j,a,target in pending if j==i),None),**{k:round(v,2) for k,v in totals[i].items()}} for i,s in enumerate(states)]})
    frame(0)
    for t in range(round(duration/.5)):
        if boss<=0 or all(s.dead for s in states): break
        reserved=[0.]*len(slots)
        for end,i,a,target in pending:
            if target is not None and not states[i].dead: reserved[target]+=a['healing']
        for i,(s,p,slot) in enumerate(zip(states,ps,slots)):
            if s.dead: continue
            options=[]
            for a in p['abilities']:
                if not legal(s,a,t,p): continue
                target=None
                occupancy=max(a['cast'],a['gcd'],.5)
                if a['healing']:
                    deficits=[(max(0,ps[j]['health']-other.health-reserved[j]),j) for j,other in enumerate(states) if not other.dead]
                    missing,target=max(deficits,default=(0,None))
                    score=min(missing,a['healing'])/occupancy/(1+a['cost']/60)
                elif a['gain']:
                    score=(120-s.resources['mana'])*2 if s.resources['mana']<35 else 0
                else: score=min(boss,a['damage'])/occupancy/(1+a['cost']/60)
                if score>0: options.append((score,a,target))
            if not options: continue
            _,a,target=max(options,key=lambda x:x[0])
            start(s,a,t,p);s.events=[] # shared-party resolver owns these events
            pending.append((t+round(a['cast']/.5),i,a,target))
            totals[i]['casts']+=1
            if target is not None: reserved[target]+=a['healing']
            log(t*.5,i,'cast',target=target,ability=a['id'])
        resolve(t)
        if boss<=0:
            duration_run=t*.5;frame(duration_run);break
        living=[i for i,s in enumerate(states) if not s.dead]
        tanks=[i for i in living if slots[i]['role']=='tank']
        # PvE: tank pool absorbs 70%; remaining pressure hits all living members.
        # PvP preset: scripted evenly distributed pressure, not intelligent enemies.
        for i in living:
            s=states[i]
            share=1/len(living) if mode=='pvp' or not tanks else .3/len(living)+(.7/len(tanks) if i in tanks else 0)
            amount=min(s.health,pressure*.5*share*(.65 if slots[i]['role']=='tank' else 1))
            s.health-=amount;totals[i]['taken']+=amount
            if s.health<=0:
                s.dead=True;log((t+1)*.5,i,'death')
            else:s.resources['mana']=min(120,s.resources['mana']+pregen(ps[i])*.5)
        resolve(t+1)
        duration_run=(t+1)*.5;frame(duration_run)
    outcome='victory' if boss<=0 else 'wipe' if all(s.dead for s in states) else 'time limit'
    divisor=max(.5,duration_run)
    return {'outcome':outcome,'elapsed':duration_run,'damage':sum(r['damage'] for r in totals),'healing':sum(r['healing'] for r in totals),'dps':sum(r['damage'] for r in totals)/divisor,'hps':sum(r['healing'] for r in totals)/divisor,'survivors':sum(not s.dead for s in states),'frames':frames,'events':events,'members':[{'slot':i,'class_name':CLASSES[s['class_id']-12],'role':s['role'],**totals[i],'dps':totals[i]['damage']/divisor,'hps':totals[i]['healing']/divisor} for i,s in enumerate(slots)],'model':'Synthetic role templates; shared-health combat with greedy action selection. Not measured class balance. PvP uses scripted pressure, not opposing player AI.'}

def pregen(p): return p['resources']['mana']['regen']
