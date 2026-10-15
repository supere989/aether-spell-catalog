"""Enumerate sets from captured DBC and local item templates without inventing class sets."""
import json,hashlib,sqlite3,sys
from pathlib import Path
import paths
from collections import Counter
B=Path(__file__).resolve().parent
source=json.loads((B/'gear-source.json').read_text())
sys.path.insert(0,str(paths.path('coa_src')/'apps/coa-dbc'))
from inspect_dbc import DataSet
ds=DataSet(str(paths.path('dbc')));table,schema,index,origin=ds.load('Spell')
cols={f.name:f for f in schema.columns}
def val(row,name):
 if name not in cols:return 0
 v,err=ds.value(table,row,cols[name]);return v
statmap={0:'mana',1:'health',3:'agility',4:'strength',5:'intellect',6:'spirit',7:'stamina',38:'ap',39:'rap',41:'healing',42:'sp',45:'sp',48:'block_value'}
slotmap={1:'head',2:'neck',3:'shoulders',4:'shirt',5:'chest',6:'waist',7:'legs',8:'feet',9:'wrists',10:'hands',11:'finger1',12:'trinket1',13:'main_hand',14:'off_hand',15:'ranged',16:'back',17:'main_hand',19:'tabard',20:'chest',21:'main_hand',22:'off_hand',23:'off_hand',25:'ranged',26:'ranged',28:'ranged'}
items={};groups={s['id']:[] for s in source['sets']}
for raw in source['items']:
 r={k:(v if k=='name' else float(v) if k.startswith('dmg_') else int(v)) for k,v in raw.items()};sid=r['itemset']
 if sid not in groups:continue
 bonuses={};warnings=[]
 for i in range(1,11):
  kind,value=r[f'stat_type{i}'],r[f'stat_value{i}']
  if not value:continue
  if kind in statmap and value>=0:
   keys=['ap','rap'] if kind==38 else ['sp','healing'] if kind==45 else [statmap[kind]]
   for key in keys:bonuses[key]=bonuses.get(key,0)+value
  else:warnings.append(f'Unmodeled stat type {kind}: {value}')
 if r['block']>0:bonuses['block_value']=bonuses.get('block_value',0)+r['block']
 if r['armor']:warnings.append(f"Armor {r['armor']} is not modeled (incoming DPS is post armor)")
 spells=[r[f'spellid_{i}'] for i in range(1,6) if r[f'spellid_{i}']>0]
 if spells:warnings.append('Item spell effects not modeled: '+', '.join(map(str,spells)))
 for key in ('ScalingStatDistribution','ScalingStatValue','RandomProperty','RandomSuffix'):
  if r[key]:warnings.append(f'{key} {r[key]} not modeled')
 place=slotmap.get(r['InventoryType']);kind='two_hand' if r['InventoryType']==17 else 'shield' if r['InventoryType']==14 else 'weapon' if r['class']==2 else 'armor'
 allowed=[c for c in range(12,33) if r['AllowableClass']&(1<<(c-1))]
 item=dict(id=r['entry'],set_id=sid,name=r['name'],slot=place,kind=kind,stats=bonuses,required_level=r['RequiredLevel'],item_level=r['ItemLevel'],quality=r['Quality'],allowed_classes=allowed,class_mask=r['AllowableClass'],warnings=warnings)
 if kind in ('weapon','two_hand'):
  item['weapon_damage']=(r['dmg_min1']+r['dmg_max1'])/2;item['weapon_speed']=r['delay']/1000
  if r['dmg_type1'] or r['dmg_min2'] or r['dmg_max2']:warnings.append('Additional damage school/component not modeled')
 item['equippable']=bool(place and allowed and (kind not in ('weapon','two_hand') or .1<=item['weapon_speed']<=10))
 items[str(item['id'])]=item;groups[sid].append(item['id'])
sets=[]
for src in source['sets']:
 s=dict(src);s['declared_items']=s.pop('items');s['items']=groups[s['id']];members=[items[str(i)] for i in s['items']]
 s['declared_items_missing']=[i for i in s['declared_items'] if str(i) not in items or items[str(i)]['set_id']!=s['id']]
 s['class_scope']='shared CoA' if any(len(i['allowed_classes'])==21 for i in members) else 'legacy restricted' if members else 'no item records'
 s['has_modeled_stats']=any(i['stats'] or i.get('weapon_damage') for i in members)
 s['usable_pieces']=sum(i['equippable'] for i in members)
 for bonus in s['bonuses']:
  row=index.get(bonus['spell_id']);bonus['name']=str(val(row,'SpellName[enUS]')) if row is not None else 'Missing spell record';bonus['description']=str(val(row,'Description[enUS]')) if row is not None else ''
  bonus['modeled']=False;bonus['stats']={};bonus['reason']='Conditional or unsupported set bonus; not included in simulation output'
  if row is not None and not s['required_skill']:
   safe=not any(val(row,key) for key in ('procFlags','ProcFlags','CasterAuraSpell','CasterAuraState','TargetAuraSpell','TargetAuraState','Stances','StancesHigh','ProcCharges','CasterAuraStateNot','TargetAuraStateNot','ExcludeCasterAuraSpell','ExcludeTargetAuraSpell','EquippedItemSubClassMask','EquippedItemInventoryTypeMask'))
   safe=safe and val(row,'DurationIndex')==21 and val(row,'EquippedItemClass') in (-1,4294967295)
   stats={};seen=False
   for j in range(3):
    effect=val(row,f'Effect[{j}]')
    if not effect:continue
    seen=True;aura=val(row,f'EffectApplyAuraName[{j}]');misc=val(row,f'EffectMiscValue[{j}]');die=val(row,f'EffectDieSides[{j}]');amount=val(row,f'EffectBasePoints[{j}]')+(1 if die==1 else 0)
    if val(row,f'EffectImplicitTargetA[{j}]')!=1 or val(row,f'EffectImplicitTargetB[{j}]')!=0 or effect!=6 or die not in (0,1) or amount<0 or val(row,f'EffectTriggerSpell[{j}]') or val(row,f'EffectRealPointsPerLevel[{j}]') or val(row,f'EffectAmplitude[{j}]'):safe=False;continue
    keys=[]
    if aura==29 and misc in (0,1,2,3,4,4294967295,-1):keys=['strength','agility','stamina','intellect','spirit'] if misc in (-1,4294967295) else [['strength','agility','stamina','intellect','spirit'][misc]]
    elif aura in (99,124,34,158):keys=[{99:'ap',124:'rap',34:'health',158:'block_value'}[aura]]
    elif aura==35 and misc==0:keys=['mana']
    else:safe=False
    for key in keys:stats[key]=stats.get(key,0)+amount
   if safe and seen and stats:bonus.update(modeled=True,stats=stats,reason='Static aura bonus modeled from DBC effect fields')

 sets.append(s)
report=dict(definitions=len(sets),populated_sets=sum(bool(s['items']) for s in sets),item_records=len(items),shared_sets=sum(s['class_scope']=='shared CoA' for s in sets),legacy_sets=sum(s['class_scope']=='legacy restricted' for s in sets),missing_sets=sum(not s['items'] for s in sets),class_specialized_sets=0,sets_with_modeled_stats=sum(s['has_modeled_stats'] for s in sets),modeled_set_bonuses=sum(b['modeled'] for s in sets for b in s['bonuses']))
output=dict(report=report,source={k:source[k] for k in ('source_database','source_kind','dbc_sha256')},sets=sets,items=items)
(B/'gear-catalog.json').write_text(json.dumps(output,separators=(',',':')))
lines=['# Gear set enumeration','',json.dumps(report,indent=2),'','Class scope is derived from item masks for CoA class IDs 12–32; names alone are not class evidence. The local qualification DB is not a live-realm inventory. Supported static aura bonuses execute at their piece thresholds; all other bonuses are explicitly unmodeled. Item stats may be partial; warnings are retained.','', '| Set ID | Name | Scope | Item variants | Modeled item stats | Bonus spells |','|---|---|---|---:|---|---:|']
for s in sets:lines.append(f"| {s['id']} | {s['name'].replace('|','/')} | {s['class_scope']} | {len(s['items'])} | {s['has_modeled_stats']} | {len(s['bonuses'])} |")
(B.parent/'GEAR-SETS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(report))
