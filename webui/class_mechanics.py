"""Source-backed baseline CoA mechanics adapter; unsupported hooks are explicit."""
from equipment import equipped,number
from gear_catalog import resolve_equipment
from functools import lru_cache
from contextlib import closing
import json,math,sqlite3
from pathlib import Path
BASE=Path(__file__).resolve().parent
SOURCE=json.loads((BASE/'mechanics-source.json').read_text())
POWER={0:'mana',1:'rage',2:'focus',3:'energy',6:'runic',4294967294:'health'}
CONTRACTS={'Felsworn':14,'Xoroth':17,'Templar':19,'Necromancer':23,'Pyromancer':24,'Cultist':25,'Starcaller':26,'SunCleric':27,'Tinker':28,'Venomancer':29}
DEFAULTS={'level':60,'ap':500,'rap':500,'sp':500,'healing':500,'stamina':150,'intellect':150,'strength':150,'agility':150,'spirit':150,'mana':4000,'base_mana':1500,'health':6000,'weapon':180,'weapon_speed':2.5,'normalized_speed':2.4,'regen':10,'power':1,'cost_multiplier':1,'initial_rage':0,'initial_runic':0}
def connection():return sqlite3.connect((BASE.parent/'catalog.sqlite').as_uri()+'?mode=ro',uri=True)
@lru_cache(maxsize=4096)
def record(i):
 with closing(connection()) as c:r=c.execute('select logic_json from abilities where id=?',(i,)).fetchone()
 return json.loads(r[0]) if r else None
@lru_cache(maxsize=4096)
def ref(table,i):
 with closing(connection()) as c:r=c.execute('select data_json from reference_records where table_name=? and id=?',(table,i)).fetchone()
 return json.loads(r[0]) if r else {}
with closing(connection()) as c:
 BONUS={r['entry']:r for (j,) in c.execute("select row_json from sql_rows where table_name='spell_bonus_data'") for r in [json.loads(j)]}
 RANKS={r['spell_id']:r['first_spell_id'] for (j,) in c.execute("select row_json from sql_rows where table_name='spell_ranks'") for r in [json.loads(j)]}
 CHARGES={r['Spell']:r['Category'] for (j,) in c.execute("select data_json from reference_records where table_name='SpellCharges'") for r in [json.loads(j)]}
ZERO=set(SOURCE['stock_zero'])
for cls,root,spell,level in SOURCE['progression']:RANKS[spell]=root

def stats(slot):
 d={k:slot.get(k,v) for k,v in DEFAULTS.items()}
 for k,v in d.items():
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('Invalid stat '+k)
 if not isinstance(d['level'],int) or not 1<=d['level']<=80:raise ValueError('Level must be 1..80')
 if not .1<=d['power']<=5 or not .25<=d['cost_multiplier']<=2:raise ValueError('Invalid tuning multiplier')
 if not 0<d['weapon_speed']<=10 or not 0<d['normalized_speed']<=10:raise ValueError('Weapon speed must be 0..10')
 if not 1<=d['health']<=1000000 or not 1<=d['mana']<=1000000 or any(v>1000000 for v in d.values()):raise ValueError('Stats exceed bounds')
 if d['initial_rage']>1000 or d['initial_runic']>1000 or d['regen']>10000:raise ValueError('Resource values exceed bounds')
 return d

def base_value(raw,index,s):
 lv=min(s['level'],raw['MaxLevel']) if raw['MaxLevel'] else s['level']
 lv=max(lv,raw['BaseLevel']);delta=lv-max(raw['BaseLevel'],raw['SpellLevel'])
 die=raw[f'EffectDieSides[{index}]']
 return raw[f'EffectBasePoints[{index}]']+int(delta*raw[f'EffectRealPointsPerLevel[{index}]'])+(0 if die==0 else (1+die)/2)

def scaled_value(d,index,s,cls,periodic=False,healing=False):
 r=d['raw_fields'];v=base_value(r,index,s);i=d['id'];notes=[]
 row=SOURCE['coefficients'].get(f'{i}:{index}')
 if row and CONTRACTS[row['class_contract']]==cls:
  if row.get('curve'):v*=.0267291844060354+.0048541098014737*s['level']+.0001859597762293*s['level']**2
  for k in ('sp','ap','rap','healing','stamina','intellect','strength','agility','spirit','mana'):
   stat='healing' if k=='sp' and row.get('heal') else k
   v+=row.get(k,0)*s[stat]
  notes.append(row['source'])
 b=BONUS.get(i) or BONUS.get(RANKS.get(i))
 if b:
  coeff=b['dot_bonus' if periodic else 'direct_bonus'];ap=b['ap_dot_bonus' if periodic else 'ap_bonus']
  v+=int(max(0,ap)*s['rap' if r['DmgClass']==3 else 'ap'])
  notes.append('SQL spell_bonus_data')
 else:coeff=0 if i in ZERO or not r['DmgClass'] else r[f'EffectBonusMultiplier[{index}]'];notes.append('DBC coefficient / stock-zero contract')
 sl,ml=r['SpellLevel'],r['MaxLevel']
 penalty=1 if sl<=0 or sl>=ml else min(1,(sl+6)/s['level'])*(1-max(0,20-sl)*.0375)
 if cls==32 and RANKS.get(i,i)==707141:penalty=1
 v+=int(s['healing' if healing else 'sp']*coeff*penalty)
 return max(0,v)*s['power'],notes

def effect_graph(i,s,cls,seen=()):
 if i in seen or len(seen)>=8:return [],['recursive/deep trigger chain']
 d=record(i)
 if not d:return [],[f'missing spell {i}']
 r=d['raw_fields'];effects=[];warnings=[];weapon_flat=0;weapon_pct=1;weapon=False;normalized=False
 for ix in range(3):
  e=r[f'Effect[{ix}]'];aura=r[f'EffectApplyAuraName[{ix}]'];target=r[f'EffectImplicitTargetA[{ix}]'];trigger=r[f'EffectTriggerSpell[{ix}]']
  if not e:continue
  if e in (17,31,58,121):
   weapon=True;normalized|=e==121
   if e==31:weapon_pct*=base_value(r,ix,s)/100
   else:weapon_flat+=base_value(r,ix,s)
   continue
  kind=None;period=0;count=1;delay=0;resource=None;percent=False
  if e==2:kind='damage'
  elif e==10:kind='heal'
  elif e in (30,137):kind='gain';resource=POWER.get(r[f'EffectMiscValue[{ix}]']);percent=e==137
  elif e==136:kind='heal';percent=True
  elif e==6 and aura in (3,8,24):
   kind={3:'damage',8:'heal',24:'gain'}[aura]
   resource=POWER.get(r[f'EffectMiscValue[{ix}]']) if aura==24 else None
   period=r[f'EffectAmplitude[{ix}]']/1000
   dur=ref('SpellDuration',r['DurationIndex']).get('Duration',0)/1000
   if period<=0 or dur<=0 or dur>1200:warnings.append(f'unsupported duration/period {i}:{ix}');continue
   count=min(1000,int(dur/period));delay=period
  elif e==64:
   child,w=effect_graph(trigger,s,cls,seen+(i,));effects+=child;warnings+=w;continue
  else:
   labels=d['effects'][ix].get('labels',{}).get(f'Effect[{ix}]',[str(e)])
   warnings.append(f'{i}:{ix} '+','.join(labels)+(f' aura {aura}' if aura else ''));continue
  if kind=='gain' and resource is None:warnings.append(f'unknown gain resource {i}:{ix}');continue
  if kind=='gain' or percent:value=max(0,base_value(r,ix,s));sources=['DBC base value']
  else:value,sources=scaled_value(d,ix,s,cls,bool(period),kind=='heal')
  effects.append({'kind':kind,'value':value,'percent':percent,'resource':resource,'period':period,'ticks':count,'delay':delay,'self':target==1,'spell_id':i,'effect':ix,'sources':sources,'periodic':bool(period)})
 if weapon:
  amount=(s['weapon']+s['ap']/14*(s['normalized_speed'] if normalized else s['weapon_speed'])+weapon_flat)*weapon_pct*s['power']
  effects.append({'kind':'damage','value':max(0,amount),'period':0,'ticks':1,'delay':0,'self':False,'spell_id':i,'effect':'weapon','sources':['DBC weapon flat/percent; weapon input + AP/14 * speed'],'periodic':False})
 return effects,sorted(set(warnings))

def kit(slot):
 _,_,equipment_sets,equipment_warnings=resolve_equipment(slot)
 slot,gear_bonus=equipped(slot)
 cls=slot['class_id'];s=stats(slot)
 if cls not in range(12,33):raise ValueError('Invalid class')
 with closing(connection()) as c:declared=c.execute("select spell_id,level from acquisitions where class_id=? and source='declared_class_spell'",(cls,)).fetchall()
 picks={i:i for i,lv in declared if lv<=s['level']}
 for cl,root,spell,lv in sorted(SOURCE['progression'],key=lambda row:row[3]):
  if cl==cls and root in picks and lv<=s['level']:picks[root]=spell
 abilities=[];excluded=[]
 caps={'mana':s['mana'],'energy':100,'focus':100,'rage':1000,'runic':1000}
 resources={k:{'cap':v,'initial':(s['initial_rage'] if k=='rage' else s['initial_runic'] if k=='runic' else v),'regen':s['regen'] if k in ('mana','energy','focus') else 0} for k,v in caps.items()}
 custom={}
 for cl,i,maximum,name in SOURCE['resource_displays']:
  if cl==cls:
   d=record(i);cap=maximum or (d['raw_fields']['StackAmount'] if d else 0)
   if cls==24 and i==807533:cap=5
   custom[str(i)]={'name':name,'cap':max(0,cap),'initial':0}
 for root,i in picks.items():
  d=record(i)
  if not d:excluded.append({'id':i,'name':str(i),'reason':'missing detailed record'});continue
  r=d['raw_fields'];reason=None
  if r['Attributes']&64:reason='passive/buff state not yet applied'
  elif r['AttributesEx']&68:reason='channeled execution not modeled'
  elif r['AttributesEx']&2:reason='drain-all cost needs stateful contract'
  elif r['RuneCostID']:reason='rune-slot recharge not modeled'
  elif any(r.get(k,0) for k in ('Stances','StancesHigh','CasterAuraState','TargetAuraSpell','TargetAuraState','TargetCreatureType','RequiresSpellFocus')):reason='form/aura/target prerequisite not modeled'
  elif any(r.get(f'Reagent[{n}]',0)>0 for n in range(8)):reason='requires reagent inventory'
  elif r['PowerType'] not in POWER:reason='unsupported power type'
  elif r['CasterAuraSpell'] and str(r['CasterAuraSpell']) not in custom:reason='required caster aura not modeled'
  elif r['ManaPerSecond'] or r['ManaPerSecondPerLevel']:reason='continuous drain not modeled'
  if reason:excluded.append({'id':i,'name':d['name'],'reason':reason});continue
  effects,warnings=effect_graph(i,s,cls)
  if not effects:excluded.append({'id':i,'name':d['name'],'reason':'; '.join(warnings) or 'no executable throughput effect'});continue
  costbase=s['base_mana'] if r['PowerType']==0 else s['health'] if POWER[r['PowerType']]=='health' else caps[POWER[r['PowerType']]]
  cost=int((r['ManaCost']+int(costbase*r['ManaCostPercentage']/100))*s['cost_multiplier'])
  charge=ref('SpellChargesCategory',CHARGES.get(i,0))
  gains=[];costs=[]
  for row in SOURCE['resource_gains']:
   cl,lo,hi,rid,amount,mutation,*rest=row
   if cl!=cls or not lo<=i<=hi:continue
   defaults=['Cast',0,0,100]
   defaults[:len(rest)]=rest
   event,required,forbidden,chance=defaults
   if mutation!='AuraStacks' or required or chance!=100 or event not in ('Cast','FirstSuccessfulHostileTarget','EachSuccessfulHostileTarget','FirstSuccessfulDamagingHit','EachSuccessfulDamagingHit','PeriodicDamageTick'):
    warnings.append('conditional/custom resource gain pending');continue
   if str(rid) in custom and custom[str(rid)]['cap']>0:gains.append({'resource':str(rid),'amount':amount,'event':event})
  for row in SOURCE['resource_costs']:
   cl,lo,hi,rid,amount,consumption,*rest=row
   if cl==cls and lo<=i<=hi:
    if str(rid) not in custom:custom[str(rid)]={'name':f'Resource {rid} (cap unresolved)','cap':0,'initial':0}
    costs.append({'resource':str(rid),'amount':amount,'consumption':consumption})
  abilities.append({'id':i,'root':root,'name':d['name'],'cost':cost,'resource':POWER[r['PowerType']],'cast':max(0,ref('SpellCastTimes',r['CastingTimeIndex']).get('CastTime',0)/1000),'gcd':r['StartRecoveryTime']/1000,'cooldown':max(r['RecoveryTime']/1000,s['weapon_speed'] if i in (75,2764,3018,5019) else 0),'category':r['Category'],'category_cooldown':r['CategoryRecoveryTime']/1000,'charges':charge.get('MaxCharges',0),'charge_recovery':charge.get('RecoveryTime',0)/1000,'effects':effects,'warnings':warnings,'gains':gains,'costs':costs,'required_custom':str(r['CasterAuraSpell']) if r['CasterAuraSpell'] else None,'power_type':r['PowerType']})
 used={a['resource'] for a in abilities if a['cost']>0 and a['resource'] in resources}
 used.update(e['resource'] for a in abilities for e in a['effects'] if e['kind']=='gain' and e['resource'] in resources)
 if not used:used={'mana'}
 overrides=slot.get('resource_settings',{})
 if not isinstance(overrides,dict) or set(overrides)-set(resources):raise ValueError('Invalid resource controls')
 for name,values in overrides.items():
  if not isinstance(values,dict) or set(values)-{'initial','regen'}:raise ValueError('Invalid resource settings')
  for field,value in values.items():
   number(value,name+' '+field,hi=resources[name]['cap'] if field=='initial' else 10000)
   if name in used:resources[name][field]=value
 for name,definition in resources.items():definition['display_scale']=10 if name in ('rage','runic') else 1
 primary=max(sorted(used),key=lambda r:sum(a['cost'] for a in abilities if a['resource']==r))
 return {'equipment_sets':equipment_sets,'equipment_warnings':equipment_warnings,'equipment_bonus':gear_bonus,'effective_defense':{key:slot.get(key,False if key=='shield_equipped' else 0) for key in ('dodge','parry','block','block_value','shield_equipped')},'active_resources':sorted(used),'primary_resource':primary,'class_id':cls,'stats':s,'abilities':abilities,'excluded':excluded,'resources':resources,'custom_resources':custom,'coverage':'source-backed baseline; talents, conditional hooks and native combat qualification incomplete'}
