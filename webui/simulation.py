"""Shared-party simulation of source-backed CoA baseline ability mechanics."""
import math,random,json
from equipment import equipped
from class_mechanics import kit
CLASSES=['Barbarian','Witch Doctor','Felsworn','Witch Hunter','Stormbringer','Knight of Xoroth','Guardian','Templar','Bloodmage','Ranger','Chronomancer','Necromancer','Pyromancer','Cultist','Starcaller','Sun Cleric','Tinker','Venomancer','Reaper','Primalist','Runemaster']
SIZES=(5,10,15,25,40);DT=.25
MELEE={12,14,15,17,18,19,30,31,32}
def bounded(value,name,lo,hi):
 if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError(f'{name} must be {lo}..{hi}')
 return value

def defense_settings(slot):
 d={k:bounded(slot.get(k,0),k,0,100) for k in ('miss','auto_miss','dodge','parry','block')}
 for k in ('shield_equipped','facing_attacker'):
  d[k]=slot.get(k,k=='facing_attacker')
  if not isinstance(d[k],bool):raise ValueError(k+' must be boolean')
 for k in ('block_value','absorb_shield'):d[k]=bounded(slot.get(k,0),k,0,1000000)
 return d

def defend(amount,defense,shield,roll=None):
 """One-roll frontal melee table; input chances are final effective percentages."""
 out=dict(misses=0,dodges=0,parries=0,blocks=0,avoided=0.,blocked=0.,absorbed=0.)
 if roll is not None and roll<defense['miss']:
  out['misses']=1;out['avoided']=amount;amount=0
 elif roll is not None and defense['facing_attacker']:
  roll-=defense['miss']
  if roll<defense['dodge']:out['dodges']=1;out['avoided']=amount;amount=0
  elif roll<defense['dodge']+defense['parry']:out['parries']=1;out['avoided']=amount;amount=0
  elif defense['shield_equipped'] and roll<defense['dodge']+defense['parry']+defense['block']:
   out['blocks']=1;out['blocked']=min(amount,defense['block_value']);amount-=out['blocked']
 out['absorbed']=min(shield,amount)
 return amount-out['absorbed'],shield-out['absorbed'],out

def auto_outcome(amount,level,enemy_level,mode,miss,roll):
 # WotLK baseline: capped weapon skill=level*5, enemy defense=enemy_level*5.
 if roll<miss:return 0.,'miss',amount
 diff=enemy_level-level
 chance=min(40,10+5*diff) if mode=='pve' and diff>0 else 0
 if roll<miss+chance:
  value=amount*(1-.1*min(diff,3))
  return value,'glancing',amount-value
 return amount,'hit',0.

def simulate(config):
 slots=config.get('slots',[]);n=config.get('size',len(slots))
 if n not in SIZES or len(slots)!=n:raise ValueError('Choose 5, 10, 15, 25 or 40 slots')
 duration=bounded(config.get('duration',60),'duration',5,1200)
 if duration%.5:raise ValueError('Duration must align to 0.5s')
 bossmax=bounded(config.get('enemy_health',50000),'enemy health',100,10000000)
 incoming=bounded(config.get('incoming_dps',350),'incoming DPS',0,100000)
 mitigation=bounded(config.get('mitigation',0),'mitigation',0,.95)
 melee_fraction=bounded(config.get('melee_percent',0),'melee percent',0,100)/100
 swing_interval=bounded(config.get('enemy_swing',2),'enemy swing',.25,10)
 if swing_interval%DT:raise ValueError('Enemy swing must align to 0.25s')
 seed=bounded(config.get('seed',1),'seed',0,4294967295)
 if int(seed)!=seed:raise ValueError('Seed must be an integer')
 rng=random.Random(seed);attack_rng=random.Random(int(seed)^0xA37E)
 enemy_level=bounded(config.get('enemy_level',60),'enemy level',1,83)
 if int(enemy_level)!=enemy_level:raise ValueError('Enemy level must be an integer')
 mode=config.get('mode','pve')
 if mode not in ('pve','pvp'):raise ValueError('Invalid mode')
 for s in slots:
  if not isinstance(s,dict) or s.get('role') not in ('tank','healer','damage'):raise ValueError('Invalid slot role')
 defenses=[defense_settings(equipped(s)[0]) for s in slots]
 cache={};kits=[]
 for s in slots:
  key=json.dumps(s,sort_keys=True,allow_nan=False)
  if key not in cache:cache[key]=kit(s)
  kits.append(cache[key])
 states=[]
 for k in kits:
  resources={r:v['initial'] for r,v in k['resources'].items()}
  weighted={r:sum(a['cost'] for a in k['abilities'] if a['resource']==r) for r in resources}
  primary=k['primary_resource']
  states.append({'health':k['stats']['health'],'resources':resources,'custom':{r:0 for r in k['custom_resources']},'primary':primary,'dead':False,'busy':0,'cast_until':0,'cooldowns':{},'categories':{},'charges':{},'periods':{},'next_swing':0})
 shields=[d['absorb_shield'] for d in defenses];melee_pending=[0.]*n
 totals=[dict(damage=0.,healing=0.,overheal=0.,taken=0.,casts=0,misses=0,auto_misses=0,glancing=0,glancing_loss=0.,auto_miss_loss=0.,dodges=0,parries=0,blocks=0,avoided=0.,blocked=0.,absorbed=0.,incoming=0.,overkill=0.) for _ in slots]
 boss=bossmax;events=[];frames=[];pending=[];elapsed=0
 def tick(seconds):return math.ceil(seconds/DT-1e-9)
 def log(t,i,kind,amount=0,target=None,ability=None,spell_id=None):
  events.append(dict(time=round(t*DT,2),actor=i,kind=kind,amount=round(amount,2),target=target,ability=ability,spell_id=spell_id))
 def change_custom(i,rid,amount):
  st=states[i];k=kits[i]
  if rid not in st['custom']:return
  total=max(0,st['custom'][rid]+amount)
  if k['class_id']==24 and rid=='807389':
   st['custom'][rid]=total%100
   if '807533' in st['custom']:st['custom']['807533']=min(5,st['custom']['807533']+int(total//100))
  else:st['custom'][rid]=min(k['custom_resources'][rid]['cap'],total)
 def resource_rules(i,a,event):
  for r in a['gains']:
   if r['event']==event:change_custom(i,r['resource'],r['amount'])
 def rage(i,damage,attacker=False):
  st=states[i]
  if st['primary']!='rage':return
  s=kits[i]['stats'];lv=s['level'];conversion=.0091107836*lv**2+3.225598133*lv+4.2652911+max(0,lv-70)*13.27
  gain=damage/conversion*2.5
  if attacker:
   dealt=damage/conversion*7.5;gain=min((dealt+s['weapon_speed']*3.5)/2,dealt*2)
  st['resources']['rage']=min(1000,st['resources']['rage']+int(gain*10))
 def effect_amount(effect,target,i):
  value=effect['value']
  if effect.get('percent'):
   cap=kits[target]['stats']['health'] if effect['kind']=='heal' else kits[i]['resources'].get(effect.get('resource'),{}).get('cap',0)
   value*=cap/100
  return value
 def deliver(t,i,a,e,target):
  nonlocal boss
  st=states[i];kind=e['kind'];value=effect_amount(e,target if target is not None else i,i)
  if kind=='damage':
   value=min(boss,max(0,value*(1-mitigation)));boss-=value;totals[i]['damage']+=value
   if value:log(t,i,'damage',value,'enemy',a['name'],e['spell_id'])
   return value
  if kind=='heal':
   dest=i if e['self'] else target
   if dest is None or states[dest]['dead']:return 0
   effective=min(value,kits[dest]['stats']['health']-states[dest]['health']);states[dest]['health']+=effective
   totals[i]['healing']+=effective;totals[i]['overheal']+=value-effective
   log(t,i,'heal',effective,dest,a['name'],e['spell_id'])
  if kind=='gain':
   r=e['resource']
   if r in st['resources']:
    gain=min(value,kits[i]['resources'][r]['cap']-st['resources'][r]);st['resources'][r]+=gain
    log(t,i,'resource',gain,i,a['name'],e['spell_id'])
  return 0
 def resolve(t):
  nonlocal pending
  due=[e for e in pending if e[0]==t];pending=[e for e in pending if e[0]!=t]
  for _,i,a,target,kind,extra in due:
   st=states[i]
   if st['dead'] or boss<=0:continue
   if kind=='periodic':
    effect,generation=extra
    if st['periods'].get((a['id'],effect['spell_id'],effect['effect']))!=generation:continue
    damage=deliver(t,i,a,effect,target)
    if damage:resource_rules(i,a,'PeriodicDamageTick')
    continue
   damage=0
   for e in a['effects']:
    if e['periodic']:
     key=(a['id'],e['spell_id'],e['effect']);gen=st['periods'].get(key,0)+1;st['periods'][key]=gen
     for j in range(1,e['ticks']+1):pending.append((t+tick(e['period']*j),i,a,target,'periodic',(e,gen)))
    else:damage+=deliver(t,i,a,e,target)
   resource_rules(i,a,'Cast')
   if any(e['kind']=='damage' for e in a['effects']):
    for ev in ('FirstSuccessfulHostileTarget','EachSuccessfulHostileTarget'):resource_rules(i,a,ev)
   if damage:
    for ev in ('FirstSuccessfulDamagingHit','EachSuccessfulDamagingHit'):resource_rules(i,a,ev)
 def frame(t):
  frames.append({'time':round(t*DT,2),'enemy_health':round(boss,2),'members':[{'health':round(st['health'],2),'max_health':kits[i]['stats']['health'],'resource':round(st['resources'][st['primary']],2),'resource_cap':kits[i]['resources'][st['primary']]['cap'],'resource_name':st['primary'],'resource_display_scale':kits[i]['resources'][st['primary']]['display_scale'],'resources':{r:round(v,2) for r,v in st['resources'].items()},'custom_resources':{kits[i]['custom_resources'][r]['name']:round(v,2) for r,v in st['custom'].items()},'absorb_remaining':round(shields[i],2),'dead':st['dead'],'casting':next((a['name'] for end,j,a,target,kind,extra in pending if j==i and kind=='cast'),None),**{k:round(v,2) for k,v in totals[i].items()}} for i,st in enumerate(states)]})
 frame(0)
 for t in range(tick(duration)):
  if boss<=0 or all(st['dead'] for st in states):break
  reserved=[0.]*n
  for end,i,a,target,kind,extra in pending:
   if kind=='cast' and target is not None and not states[i]['dead']:
    reserved[target]+=sum(effect_amount(e,target,i) for e in a['effects'] if e['kind']=='heal' and not e['periodic'])
  for i,(st,k,slot) in enumerate(zip(states,kits,slots)):
   if st['dead']:continue
   if slot['role']!='healer' and k['class_id'] in MELEE and t>=st['next_swing'] and t>=st['cast_until']:
    base=(k['stats']['weapon']+k['stats']['ap']/14*k['stats']['weapon_speed'])*(1-mitigation)
    damage,outcome,lost=auto_outcome(base,k['stats']['level'],enemy_level,mode,defenses[i]['auto_miss'],attack_rng.random()*100)
    if outcome=='miss':totals[i]['auto_misses']+=1;totals[i]['auto_miss_loss']+=lost;log(t,i,'miss',target='enemy',ability='Auto Attack',spell_id=6603)
    if outcome=='glancing':totals[i]['glancing']+=1;totals[i]['glancing_loss']+=lost
    damage=min(boss,damage);boss-=damage;totals[i]['damage']+=damage
    if damage:
     rage(i,damage,True);log(t,i,'damage',damage,'enemy','Auto Attack (glancing)' if outcome=='glancing' else 'Auto Attack',6603)
    st['next_swing']=t+tick(k['stats']['weapon_speed'])
   if t<st['busy'] or boss<=0:continue
   choices=[]
   for a in k['abilities']:
    cost=a['cost'];r=a['resource']
    if t<st['cooldowns'].get(a['id'],0) or t<st['categories'].get(a['category'],0):continue
    if t+tick(a['cast'])>tick(duration):continue
    if cost>=(st['health'] if r=='health' else float('inf')) or cost>st['resources'].get(r,float('inf')):continue
    if a['required_custom'] and not st['custom'].get(a['required_custom']):continue
    if any(st['custom'].get(v['resource'],0)<v['amount'] for v in a['costs']):continue
    if a['charges']:
     used=[end for end in st['charges'].get(a['id'],[]) if end>t];st['charges'][a['id']]=used
     if len(used)>=a['charges']:continue
    target=None;value=0
    damage=sum(e['value']*(e['ticks'] if e['periodic'] else 1) for e in a['effects'] if e['kind']=='damage')
    healing=[e for e in a['effects'] if e['kind']=='heal']
    if healing:
     target=max((j for j,sj in enumerate(states) if not sj['dead']),key=lambda j:max(0,kits[j]['stats']['health']-states[j]['health']-reserved[j]))
     for e in healing:
      dest=i if e['self'] else target;value+=min(max(0,kits[dest]['stats']['health']-states[dest]['health']-reserved[dest]),effect_amount(e,dest,i)*(e['ticks'] if e['periodic'] else 1))
     if slot['role']=='healer':value*=3
    if slot['role']!='healer' or value==0:value+=damage
    for e in a['effects']:
     if e['kind']=='gain' and e['resource'] in st['resources']:
      cap=k['resources'][e['resource']]['cap'];value+=min(cap-st['resources'][e['resource']],e['value'])*2
    # Avoid clipping active periodic applications just to inflate estimated utility.
    if any(j==i and spell['id']==a['id'] and kind=='periodic' for _,j,spell,_,kind,_ in pending):continue
    score=value/max(.25,a['cast'],a['gcd'])/(1+cost/max(1,k['resources'].get(r,{'cap':k['stats']['health']})['cap']))
    if score>0:choices.append((score,a,target))
   if not choices:continue
   _,a,target=max(choices,key=lambda x:x[0]);r=a['resource']
   if r=='health':st['health']-=a['cost']
   else:st['resources'][r]-=a['cost']
   for v in a['costs']:
    if v['consumption']!='None':st['custom'][v['resource']]=0 if v['consumption']=='All' else st['custom'][v['resource']]-v['amount']
   finish=t+tick(a['cast']);st['busy']=t+max(1,tick(max(a['cast'],a['gcd'])));st['cast_until']=finish
   st['cooldowns'][a['id']]=finish+tick(a['cooldown'])
   if a['category_cooldown']:st['categories'][a['category']]=finish+tick(a['category_cooldown'])
   if a['charges']:
    used=st['charges'].setdefault(a['id'],[]);used.append(max([finish]+used)+tick(a['charge_recovery']))
   pending.append((finish,i,a,target,'cast',None));totals[i]['casts']+=1
   if target is not None:reserved[target]+=sum(effect_amount(e,target,i) for e in a['effects'] if e['kind']=='heal' and not e['self'])
   log(t,i,'cast',target=target,ability=a['name'],spell_id=a['id'])
  resolve(t)
  if boss<=0:elapsed=t*DT;frame(t);break
  living=[i for i,s in enumerate(states) if not s['dead']];tanks=[i for i in living if slots[i]['role']=='tank']
  for i in living:
   st=states[i];share=1/len(living) if mode=='pvp' or not tanks else .3/len(living)+(.7/len(tanks) if i in tanks else 0)
   # Input is post-armor pressure, before avoidance/block/absorption.
   pressure=incoming*DT*share
   melee_pending[i]+=pressure*melee_fraction
   packets=[(pressure*(1-melee_fraction),None)]
   if (t+1)%tick(swing_interval)==0 or t+1==tick(duration):
    if melee_pending[i]:packets.append((melee_pending[i],rng.random()*100))
    melee_pending[i]=0
   for raw,roll in packets:
    if not raw:continue
    amount,shields[i],defended=defend(raw,defenses[i],shields[i],roll)
    totals[i]['incoming']+=raw
    for field,value in defended.items():totals[i][field]+=value
    for field,kind in [('misses','miss'),('dodges','dodge'),('parries','parry'),('blocks','block')]:
     if defended[field]:log(t+1,i,kind,defended['blocked'] if kind=='block' else raw,i,'Incoming melee')
    if defended['absorbed']:log(t+1,i,'absorb',defended['absorbed'],i,'Absorb shield')
    actual=min(st['health'],amount);totals[i]['overkill']+=amount-actual
    st['health']-=actual;totals[i]['taken']+=actual;rage(i,actual)
   if st['health']<=0:st['dead']=True;log(t+1,i,'death')
   else:
    for r,definition in kits[i]['resources'].items():st['resources'][r]=min(definition['cap'],st['resources'][r]+definition['regen']*DT)
  resolve(t+1);elapsed=(t+1)*DT
  if (t+1)%2==0 or boss<=0 or all(st['dead'] for st in states):frame(t+1)
 outcome='victory' if boss<=0 else 'wipe' if all(st['dead'] for st in states) else 'time limit';divisor=max(DT,elapsed)
 return {'outcome':outcome,'elapsed':elapsed,'damage':sum(r['damage'] for r in totals),'healing':sum(r['healing'] for r in totals),'dps':sum(r['damage'] for r in totals)/divisor,'hps':sum(r['healing'] for r in totals)/divisor,'survivors':sum(not s['dead'] for s in states),'frames':frames,'events':events,'members':[{'slot':i,'class_name':CLASSES[s['class_id']-12],'role':s['role'],**totals[i],'dps':totals[i]['damage']/divisor,'hps':totals[i]['healing']/divisor,'coverage':{'modeled_abilities':len(kits[i]['abilities']),'excluded':kits[i]['excluded'],'abilities':[{'id':a['id'],'name':a['name'],'warnings':a['warnings']} for a in kits[i]['abilities']]}} for i,s in enumerate(slots)],'model':'CoA source-backed baseline: real ranks, effects, coefficients, costs, charges and selected resource contracts. Conditional scripts/talents incomplete; not native-engine parity. WotLK glancing uses capped level-based weapon/defense skill; melee auto misses use scenario chances. Spell misses and ClassicPlus tables are not modeled. Defense uses final scenario chances, frontal one-roll melee, flat shield block and finite initial absorbs; no armor/expertise derivation, parry haste, critical blocks or defensive ability procs. PvP is scripted pressure. Timing quantized upward to 250ms.'}
