"""Trace set bonuses to acquired CoA spells/resources with explicit structural evidence."""
import json,sqlite3,sys,collections,hashlib
from pathlib import Path
B=Path(__file__).resolve().parent
sys.path.insert(0,'/work/wow-coa/merge/core/apps/coa-dbc')
from inspect_dbc import DataSet
D=DataSet('/tmp/coa-restart-validation/data/dbc');t,s,idx,origin=D.load('Spell');cols={c.name:c for c in s.columns}
cache={}
def raw(identity):
 if identity in cache:return cache[identity]
 row=idx.get(identity)
 if row is None:return None
 keys=['SpellName[enUS]','SpellFamilyName','CasterAuraSpell','TargetAuraSpell']+[f'SpellFamilyFlags[{i}]' for i in range(3)]+[f'EffectTriggerSpell[{i}]' for i in range(3)]+[f'EffectSpellClassMask{letter}[{i}]' for i in range(3) for letter in ('A','B','C')]
 # Schemas differ: require exact effect-mask columns below.
 result={name:D.value(t,row,cols[name])[0] for name in keys if name in cols};cache[identity]=result;return result
print('mask schema:',[c for c in cols if 'SpellClassMask' in c][:9])
with sqlite3.connect((B.parent/'catalog.sqlite').as_uri()+'?mode=ro',uri=True) as db:
 owners=collections.defaultdict(set)
 for cls,spell in db.execute('SELECT DISTINCT class_id,spell_id FROM acquisitions'):
  if cls in range(12,33):owners[spell].add(cls)
source=json.loads((B/'mechanics-source.json').read_text())
for cls,root,spell,lv in source['progression']:owners[spell].add(cls)
for cls,spell,maximum,name in source['resource_displays']:owners[spell].add(cls)
family=collections.defaultdict(list)
for spell,classes in owners.items():
 r=raw(spell)
 if r and r.get('SpellFamilyName'):family[r['SpellFamilyName']].append((spell,r,classes))
data=json.loads((B/'gear-catalog.json').read_text());byclass={str(i):[] for i in range(12,33)};mapped_bonus=0;links_total=0
masknames=[]
for i in range(3):
 names=[f'EffectSpellClassMask{a}[{i}]' for a in 'ABC']
 if not all(n in cols for n in names):
  names=[f'EffectSpellClassMask[{i*3+j}]' for j in range(3)]
 if not all(n in cols for n in names):raise RuntimeError('Unknown effect mask schema; refuse guessing')
 masknames.append(names)
for definition in data['sets']:
 allclasses=set();count=0
 for bonus in definition['bonuses']:
  evidence=[];seen=set();queue=[(bonus['spell_id'],[bonus['spell_id']])];visited=set()
  def add(kind,target,classes,path):
   nonlocal_dummy=None
   key=(kind,target,tuple(sorted(classes)))
   if key in seen:return
   seen.add(key);record=raw(target)
   evidence.append(dict(kind=kind,spell_id=target,spell_name=record.get('SpellName[enUS]',str(target)) if record else str(target),classes=sorted(classes),path=path))
  while queue:
   identity,path=queue.pop(0)
   if identity in visited:continue
   visited.add(identity);r=raw(identity)
   if not r:continue
   row=idx[identity]
   for name in ['CasterAuraSpell','TargetAuraSpell']+[f'EffectTriggerSpell[{i}]' for i in range(3)]:
    target=r.get(name,0)
    if target:
     if target in owners:add(name,target,owners[target],path+[target])
     if name.startswith('EffectTriggerSpell') and len(path)<8:queue.append((target,path+[target]))
   fam=r.get('SpellFamilyName',0)
   for effect_index,names in enumerate(masknames):
    if D.value(t,row,cols[f'EffectApplyAuraName[{effect_index}]'])[0] not in (107,108):continue
    masks=[D.value(t,row,cols[name])[0] for name in names]
    if not any(masks) or not fam:continue
    for target,other,classes in family.get(fam,[]):
     if any(masks[j]&other.get(f'SpellFamilyFlags[{j}]',0) for j in range(3)):add('spell modifier family mask',target,classes,path)
  classes=sorted({cls for e in evidence for cls in e['classes']});allclasses.update(classes)
  bonus['class_links']=evidence;bonus['linked_classes']=classes
  bonus['association']='single-class structural link' if len(classes)==1 else 'multi-class structural link' if classes else 'no verified class-specific link'
  if classes:mapped_bonus+=1
  links_total+=len(evidence)
 definition['linked_classes']=sorted(allclasses)
 definition['class_association']='single-class structural link' if len(allclasses)==1 else 'multi-class structural link' if allclasses else 'shared stats / cosmetic / unresolved scripts'
 for cls in allclasses:byclass[str(cls)].append(definition['id'])
report=dict(mapped_bonus_entries=mapped_bonus,structural_links=links_total,linked_sets=sum(bool(s['linked_classes']) for s in data['sets']),single_class_sets=sum(len(s['linked_classes'])==1 for s in data['sets']),class_sets=byclass,spell_dbc_sha256=hashlib.sha256(Path('/tmp/coa-restart-validation/data/dbc/Spell.dbc').read_bytes()).hexdigest(),limits='Structural association is not class-exclusive ownership or tier proof. Unmatched script-only logic and name-only hints remain unresolved. Acquisition candidates include talent candidates.')
data['class_mapping']=report;(B/'gear-catalog.json').write_text(json.dumps(data,separators=(',',':')))
(B/'set-class-mapping.json').write_text(json.dumps(report,indent=2))
labels=['Barbarian','Witch Doctor','Felsworn','Witch Hunter','Stormbringer','Knight of Xoroth','Guardian','Templar','Bloodmage','Ranger','Chronomancer','Necromancer','Pyromancer','Cultist','Starcaller','Sun Cleric','Tinker','Venomancer','Reaper','Primalist','Runemaster']
lines=['# Set bonus to CoA class mapping','',report['limits'],'','| Class | Sets with structural links |','|---|---:|']
for cls,name in enumerate(labels,12):lines.append(f'| {name} | {len(byclass[str(cls)])} |')
for definition in data['sets']:
 if not definition['linked_classes']:continue
 lines+=['',f"## {definition['name']} (#{definition['id']})",', '.join(labels[c-12] for c in definition['linked_classes'])]
 for bonus in definition['bonuses']:
  for link in bonus['class_links']:lines.append(f"- {bonus['pieces']} pieces: {bonus['spell_id']} → {link['spell_id']} {link['spell_name']} ({link['kind']}); path {link['path']}")
(B.parent/'SET-CLASS-MAPPING.md').write_text('\n'.join(lines)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='class_sets'}))
