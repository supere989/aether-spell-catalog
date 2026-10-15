import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = Path('/work/wow-coa/merge/core')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'apps/coa-dbc'))
from inspect_dbc import DataSet

DS = DataSet('/tmp/coa-restart-validation/data/dbc')
DB = OUT / 'catalog.sqlite'
if DB.exists():
    raise SystemExit('Refusing to replace an existing catalog')
c = sqlite3.connect(DB)
c.executescript('''
CREATE TABLE spell_index(id INTEGER PRIMARY KEY,name TEXT,description TEXT,level INTEGER,family INTEGER,power_type INTEGER,base_cost INTEGER);
CREATE TABLE abilities(id INTEGER PRIMARY KEY,name TEXT,logic_json TEXT);
CREATE TABLE acquisitions(class_id INTEGER,level INTEGER,spell_id INTEGER,source TEXT,source_entry INTEGER,requirements_json TEXT);
CREATE TABLE reference_records(table_name TEXT,id INTEGER,data_json TEXT,PRIMARY KEY(table_name,id));
CREATE TABLE spell_links(spell_id INTEGER,field TEXT,target_table TEXT,target_id INTEGER);
CREATE TABLE sql_rows(table_name TEXT,row_json TEXT);
CREATE TABLE source_mentions(spell_id INTEGER,path TEXT,line INTEGER,evidence TEXT);
CREATE TABLE scenario_links(spell_id INTEGER,path TEXT,name TEXT);
CREATE TABLE provenance(source TEXT PRIMARY KEY,data_json TEXT);
CREATE INDEX acquisition_spell ON acquisitions(spell_id);
CREATE INDEX acquisition_class ON acquisitions(class_id);
CREATE INDEX source_spell ON source_mentions(spell_id);
''')
j=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':'))
origins={}
errors=[]
def fields(table,row,schema):
    result={}
    for f in schema.columns:
        if f.kind=='s' and '[' in f.name and not f.name.endswith('[enUS]'):
            continue
        value,error=DS.value(table,row,f)
        result[f.name]=value
        if error:
            errors.append([table.name,row,f.name,error])
    return result

def table_records(name):
    table,schema,index,origin=DS.load(name)
    origins[name]=origin
    for identity,row in index.items():
        yield identity,fields(table,row,schema)

text=(ROOT/'src/server/coa/AscensionCustomClassData.h').read_text()
section=text.split('ClassSpells =',1)[1].split('}};',1)[0]
acq=[tuple(map(int,m)) for m in re.findall(r'\{(\d+),\s*(\d+),\s*(\d+)\}',section)]
for cls,level,spell in acq:
    c.execute('INSERT INTO acquisitions VALUES(?,?,?,?,?,?)',(cls,level,spell,'declared_class_spell',None,'{}'))
seed={v[2] for v in acq}
class_types=dict(table_records('CharacterAdvancementClassTypes'))
for name in ('CharacterAdvancementClassTypes','CharacterAdvancementTabTypes','ChrSpecs','SpellDuration','SpellRange','SpellCastTimes','SpellCharges','SpellChargesCategory','SpellAddon','SpellCustomAttr'):
    for identity,data in table_records(name):
        c.execute('INSERT INTO reference_records VALUES(?,?,?)',(name,identity,j(data)))
for identity,data in table_records('CharacterAdvancement'):
    cls=class_types.get(data['ClassType'],{}).get('ClassID')
    if cls not in range(12,33):
        continue
    c.execute('INSERT INTO reference_records VALUES(?,?,?)',('CharacterAdvancement',identity,j(data)))
    for key,value in data.items():
        if key.startswith('RankSpell[') and value:
            seed.add(value)
            c.execute('INSERT INTO acquisitions VALUES(?,?,?,?,?,?)',(cls,data['RequiredLevel'],value,'advancement_candidate',identity,j(data)))
sql=json.loads((OUT/'sql-capture.json').read_text())
seed.update(sql['resolved_spells'])
for name,data in sql['tables'].items():
    for row in data['rows']:
        c.execute('INSERT INTO sql_rows VALUES(?,?)',(name,j(row)))
c.execute('INSERT INTO provenance VALUES(?,?)',('sql_capture',j({k:v for k,v in sql.items() if k!='tables'})))
print('Indexing all spell names and descriptions',flush=True)
t,s,index,origin=DS.load('Spell'); origins['Spell']=origin
wanted=['SpellName[enUS]','Description[enUS]','SpellLevel','SpellFamilyName','PowerType','ManaCost']
cols={f.name:f for f in s.columns}
for identity,row in index.items():
    values=[DS.value(t,row,cols[key])[0] for key in wanted]
    c.execute('INSERT INTO spell_index VALUES(?,?,?,?,?,?,?)',(identity,*values))
print('Expanding class abilities, talent candidates, ranks and referenced effects',flush=True)
pending=list(seed); seen=set(); missing=[]
with (OUT/'abilities.jsonl').open('x') as export:
    while pending:
        identity=pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        if identity not in index:
            missing.append(identity)
            continue
        record=DS.record('Spell',identity)
        raw={f['name']:f['value'] for f in record['fields'] if f['name']!='Unknown bytes' and (f['type']!='s' or '[' not in f['name'] or f['name'].endswith('[enUS]'))}
        effects=[]
        for i in range(3):
            effect={k:v for k,v in raw.items() if k.startswith('Effect') and k.endswith(f'[{i}]')}
            effect['labels']={f['name']:f['labels'] for f in record['fields'] if f.get('labels') and f['name'].startswith('Effect') and f['name'].endswith(f'[{i}]')}
            effects.append(effect)
        links=[]
        for f in record['fields']:
            if 'reference' in f:
                ref=f['reference']; links.append({'field':f['name'],**ref})
                c.execute('INSERT INTO spell_links VALUES(?,?,?,?)',(identity,f['name'],ref['table'],ref['id']))
                if ref['table']=='Spell' and ref['id'] not in seen:
                    pending.append(ref['id'])
        logic={'id':identity,'name':record['name'],'description':raw.get('Description[enUS]'),
          'cost':{k:raw.get(k) for k in ['PowerType','ManaCost','ManaCostPercentage','ManaCostPerlevel','ManaPerSecond','ManaPerSecondPerLevel','RuneCostID']},
          'timing':{k:raw.get(k) for k in ['CastingTimeIndex','RecoveryTime','CategoryRecoveryTime','StartRecoveryTime','StartRecoveryCategory','DurationIndex']},
          'restrictions':{k:v for k,v in raw.items() if k.startswith(('Attributes','Stances','CasterAura','TargetAura','Exclude','EquippedItem','Requires','Reagent','Totem')) or k in ['RangeIndex','Targets','TargetCreatureType','FacingCasterFlags','MaxTargetLevel','MaxAffectedTargets','SpellLevel']},
          'effects':effects,'references':links,'raw_fields':raw,
          'sustainability':{'status':'requires_character_and_rotation','inputs_needed':['effective_cost_after_modifiers','resource_cap','regeneration_rate_and_ticks','resource_generators','cast_GCD_and_cooldown_schedule','proc_probabilities','target_lifetime'],'constraint':'At every action: available resource >= effective cost; apply gains and regeneration over elapsed time, capped at resource maximum.'},
          'evidence':{'dbc':'Spell','sql_capture_contains_requested_or_rank_id':identity in set(sql['resolved_spells']),'effective_runtime_verified':False,'notes':record['notes']}}
        c.execute('INSERT INTO abilities VALUES(?,?,?)',(identity,record['name'],j(logic))); export.write(j(logic)+'\n')
print('Linking literal source references and scenario definitions',flush=True)
for p in (ROOT/'src/server/coa').glob('*'):
    if p.suffix not in ('.cpp','.h') or p.name=='AscensionCustomClassData.h':
        continue
    for number,line in enumerate(p.read_text(errors='replace').splitlines(),1):
        for identity in {int(v) for v in re.findall(r'\b\d{5,8}\b',line)} & seen:
            c.execute('INSERT INTO source_mentions VALUES(?,?,?,?)',(identity,str(p.relative_to(ROOT)),number,'literal reference only; not semantic or runtime proof'))
for p in (ROOT/'apps/coa-gameplay-test/scenarios').glob('*.json'):
    data=json.loads(p.read_text()); ids=set()
    def walk(v):
        if isinstance(v,dict):
            if isinstance(v.get('spell'),int): ids.add(v['spell'])
            for value in v.values(): walk(value)
        elif isinstance(v,list):
            for value in v: walk(value)
    walk(data)
    for identity in ids & seen:
        c.execute('INSERT INTO scenario_links VALUES(?,?,?)',(identity,str(p.relative_to(ROOT)),data.get('name','')))
for name,origin in origins.items():
    DS.load(name)
    c.execute('INSERT INTO provenance VALUES(?,?)',(name,j(origin)))
c.execute('INSERT INTO provenance VALUES(?,?)',('class_acquisition_source',j({'path':'src/server/coa/AscensionCustomClassData.h','sha256':hashlib.sha256((ROOT/'src/server/coa/AscensionCustomClassData.h').read_bytes()).hexdigest()})))
c.commit()
counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ['spell_index','abilities','acquisitions','reference_records','spell_links','sql_rows','source_mentions','scenario_links']}
checks={'sqlite_integrity':c.execute('PRAGMA integrity_check').fetchone()[0], 'declared_acquisitions_match_source':c.execute("SELECT COUNT(*) FROM acquisitions WHERE source='declared_class_spell'").fetchone()[0]==len(acq),'missing_referenced_spell_ids':sorted(missing),'field_errors':errors,'classes':c.execute('SELECT DISTINCT class_id FROM acquisitions ORDER BY class_id').fetchall()}
summary={'created_at':datetime.now(timezone.utc).isoformat(),'counts':counts,'checks':checks,'scope':'Searchable all-spell index; detailed CoA class acquisition/talent candidate/rank/reference corpus. Raw DBC plus separately retained SQL evidence; no runtime semantics or optimal DPS claimed.','stale_manifests':[name for name,o in origins.items() if o.get('manifest_match') is False]}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
c.close()
print(json.dumps(summary,indent=2),flush=True)
