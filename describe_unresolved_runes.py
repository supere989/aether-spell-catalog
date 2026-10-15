"""Generate evidence-backed, provisional descriptions; never modifies game data."""
import collections, hashlib, json, re, sqlite3, sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=Path('/work/wow-coa/merge/core')
sys.path.insert(0,str(ROOT/'apps/coa-dbc'))
from inspect_dbc import DataSet
DS=DataSet('/tmp/coa-restart-validation/data/dbc')
inputs=[json.loads(s) for s in (P/'runes-unresolved.jsonl').read_text().splitlines()]
c=sqlite3.connect(f'file:{P}/catalog.sqlite?mode=ro',uri=True)
_,_,idx,origin=DS.load('Spell')
source_hashes={}
handlers={}
for table,path,owner in [('effect','src/server/game/Spells/SpellEffects.cpp','Spell'),('aura','src/server/game/Spells/Auras/SpellAuraEffects.cpp','AuraEffect')]:
    f=ROOT/path; text=f.read_text(); source_hashes[path]=hashlib.sha256(f.read_bytes()).hexdigest()
    handlers[table]={}
    lines=text.splitlines()
    for n,line in enumerate(lines,1):
        m=re.search(r'&'+owner+r'::(\w+),\s*//\s*(\d+)\s*(.*)',line)
        if m:
            fn,num,comment=m.groups()
            definition=next((i for i,s in enumerate(lines,1) if re.search(r'void '+owner+r'::'+fn+r'\(',s)),None)
            handlers[table][int(num)]={'function':owner+'::'+fn,'path':path,'dispatch_line':n,'definition_line':definition,'dispatch_comment':comment}
f=ROOT/'src/server/game/Spells/SpellDefines.h'
source_hashes[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
ops={int(n):name for name,n in re.findall(r'(SPELLMOD_\w+)\s*=\s*(\d+)',f.read_text())}
records={}; missing=set()
def get(i):
    if i not in idx: missing.add(i); return None
    if i not in records: records[i]=DS.record('Spell',i)
    return records[i]
def fields(r): return {x['name']:x for x in r['fields']}
def value(fs,k): return fs.get(k,{}).get('value',0)
def label(fs,k):
    v=fs.get(k,{})
    return next((s for s in v.get('labels',[]) if s!='Unknown enum value'),str(v.get('value',0)))
def friendly(s):
    return s.replace('SPELL_EFFECT_','').replace('SPELL_AURA_','').replace('SPELLMOD_','').replace('_',' ').lower()
def effects(r):
    fs=fields(r); out=[]
    for n in range(3):
        key=lambda s:f'{s}[{n}]'
        eid=value(fs,key('Effect')); aid=value(fs,key('EffectApplyAuraName'))
        if not eid: continue
        el=label(fs,key('Effect')); al=label(fs,key('EffectApplyAuraName')) if aid else None
        trigger=value(fs,key('EffectTriggerSpell'))
        phrases = {
            'SPELL_EFFECT_SCHOOL_DAMAGE':'Deals damage using the spell’s damage school',
            'SPELL_EFFECT_CREATE_ITEM':f"Creates item {value(fs,key('EffectItemType'))}",
            'SPELL_EFFECT_SUMMON':f"Summons creature entry {value(fs,key('EffectMiscValue'))}",
            'SPELL_EFFECT_DUMMY':'Invokes a custom-effect hook; its behavior requires a matching implementation',
            'SPELL_EFFECT_SCRIPT_EFFECT':'Invokes a scripted-effect handler',
            'SPELL_EFFECT_TELEPORT_UNITS':'Teleports the affected unit; destination rules require further resolution',
            'SPELL_EFFECT_KILL_CREDIT2':'Awards quest kill credit',
            'SPELL_EFFECT_QUEST_COMPLETE':'Marks a quest objective complete',
            'SPELL_EFFECT_ACTIVATE_RUNE':'Reactivates rune resource slots (not a selectable rune modification)',
            'SPELL_EFFECT_REMOVE_AURA':'Removes an aura; this does not execute the removed aura’s effects',
            'SPELL_EFFECT_HEAL_PCT':'Heals by a percentage of health',
            'SPELL_EFFECT_DISPEL':'Dispels effects of the configured dispel type',
            'SPELL_EFFECT_APPLY_AURA':'Applies an aura',
            'SPELL_EFFECT_APPLY_AREA_AURA_ENEMY':'Applies an area aura to eligible enemies',
            'SPELL_EFFECT_APPLY_AREA_AURA_PARTY':'Applies an area aura to eligible party members',
        }
        auras = {
            'SPELL_AURA_MOD_DAMAGE_DONE':'changes damage dealt by a flat amount for the configured school mask',
            'SPELL_AURA_MOD_DAMAGE_PERCENT_DONE':'changes damage dealt by a percentage for the configured school mask',
            'SPELL_AURA_MOD_DAMAGE_PERCENT_TAKEN':'changes damage received by a percentage for the configured school mask',
            'SPELL_AURA_MOD_POWER_REGEN_PERCENT':'changes regeneration of the configured resource by a percentage',
            'SPELL_AURA_MOD_POWER_REGEN':'changes regeneration of the configured resource',
            'SPELL_AURA_PERIODIC_DAMAGE':'deals damage on periodic ticks',
            'SPELL_AURA_PERIODIC_TRIGGER_SPELL':'triggers a linked spell on periodic ticks',
            'SPELL_AURA_PROC_TRIGGER_SPELL':'triggers a linked spell when its proc conditions are met',
            'SPELL_AURA_MOD_SPELL_CRIT_CHANCE_SCHOOL':'changes spell critical-strike chance for the configured schools',
            'SPELL_AURA_ADD_FLAT_MODIFIER':'adds a flat spell modifier to matching abilities',
            'SPELL_AURA_ADD_PCT_MODIFIER':'adds a percentage spell modifier to matching abilities',
            'SPELL_AURA_DUMMY':'provides a custom aura hook; behavior depends on its implementation',
            'SPELL_AURA_PERIODIC_DUMMY':'provides a periodic custom aura hook',
            'SPELL_AURA_CONVERT_RUNE':'converts rune resource types; conversion rules require review',
        }
        parts=[phrases.get(el, friendly(el))]
        if aid: parts.append(auras.get(al, 'aura: '+friendly(al)))
        op=None
        if al in ('SPELL_AURA_ADD_FLAT_MODIFIER','SPELL_AURA_ADD_PCT_MODIFIER'):
            op=ops.get(value(fs,key('EffectMiscValue')))
            parts.append('modifies '+friendly(op) if op else 'modifier operation is unknown')
        if trigger:
            linked=get(trigger)
            parts.append(f"linked spell {trigger} ({linked['name'] if linked else 'missing definition'})")
        out.append({'slot':n,'effect':el,'aura':al,'modifier_operation':op,
                    'description':'; '.join(parts)+'.',
                    'base_points_raw':value(fs,key('EffectBasePoints')),
                    'misc_value':value(fs,key('EffectMiscValue')),
                    'period_ms':value(fs,key('EffectAmplitude')),
                    'referenced_spell':trigger,
                    'trigger_spell':trigger if el != 'SPELL_EFFECT_REMOVE_AURA' else 0,
                    'targets':[label(fs,key('EffectImplicitTargetA')),label(fs,key('EffectImplicitTargetB'))],
                    'native_handlers':[h for h in [handlers['effect'].get(eid),handlers['aura'].get(aid) if aid else None] if h],
                    'requires_script_review': 'DUMMY' in el or 'SCRIPT' in el or bool(al and ('DUMMY' in al or 'OVERRIDE' in al))})
    return out
# Traverse all trigger links, with visited sets handling cycles.
queue=[r['spell_id'] for r in inputs]; visited=set(); details={}
while queue:
    i=queue.pop()
    if i in visited: continue
    visited.add(i); r=get(i)
    if not r: continue
    ee=effects(r); details[i]=ee
    queue.extend(e['trigger_spell'] for e in ee if e['trigger_spell'])
# Retain literal script/correction mentions as leads, not proof of execution.
mentions=collections.defaultdict(list)
for directory in ('src/server/coa','src/server/scripts','src/server/game/Spells'):
    for f in (ROOT/directory).rglob('*'):
        if f.suffix not in ('.cpp','.h'): continue
        text=f.read_text(errors='replace'); hits=[]
        for n,line in enumerate(text.splitlines(),1):
            for i in set(map(int,re.findall(r'\b\d{4,8}\b',line))) & visited:
                mentions[i].append({'path':str(f.relative_to(ROOT)),'line':n,'text':line.strip(),'evidence':'literal_id_reference_only'})
                hits.append(i)
        if hits: source_hashes[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
def closure(i):
    todo=[i]; seen=set()
    while todo:
        k=todo.pop()
        if k in seen: continue
        seen.add(k)
        todo.extend(e['trigger_spell'] for e in details.get(k,[]) if e['trigger_spell'])
    return sorted(seen)
results=[]
for row in inputs:
    i=row['spell_id']; reachable=closure(i); ee=details.get(i,[])
    tags=set(); ambiguous=False
    for k in reachable:
        for e in details.get(k,[]):
            s=' '.join(x or '' for x in (e['effect'],e['aura'],e['modifier_operation']))
            if any(t in s for t in ('DAMAGE','ATTACK_POWER','CRIT','SPELL_POWER','ARMOR_PENETRATION')): tags.add('damage_candidate')
            if any(t in s for t in ('ENERGIZE','POWER_REGEN','POWER_COST','POWER_DRAIN','POWER_BURN','SPELLMOD_COST','RUNE','MANA')): tags.add('resource_candidate')
            if any(t in s for t in ('HASTE','CASTING','ATTACKSPEED','COOLDOWN','CHARGES','ACTIVATION_TIME','SPELLMOD_DURATION')): tags.add('timing_candidate')
            ambiguous |= e['requires_script_review']
    sentences=[e['description'][0].upper()+e['description'][1:] for e in ee]
    linked=[k for k in reachable if k!=i and k in details]
    if linked:
        sentences.append('Linked execution: '+'; '.join(f"{k} ({records[k]['name']}): "+' '.join(e['description'] for e in details[k]) for k in linked)+'.')
    if i == 801512:
        sentences.append('Reviewed source: for living CLASS_SPIRIT_MAGE players, non-triggered Runeblade or Warpdagger casts with the Spellfire Runes aura can roll the configured proc chance, reset the known Smolder rank cooldown, and grant this ready aura. A non-triggered Smolder cast consumes the ready aura; removing the source Spellfire Runes aura also removes it. Source: AscensionRunemasterSecondary.cpp, OnSpellCast and OnAuraRemove. Hook registration/runtime execution remain unverified.')
    if not sentences: sentences=['No nonzero DBC effect is defined; behavior cannot be established from this record.']
    if ambiguous: sentences.append('Dummy/script or override behavior requires script review; the dispatch alone does not establish its final function.')
    if any(k in missing for k in reachable): sentences.append('At least one linked spell definition is missing.')
    results.append({'spell_id':i,'name':row['name'],'authored_description':row['description'],
                    'generated_description':' '.join(sentences),'description_basis':'DBC effect/aura enums and native dispatch; not runtime verified',
                    'scope_candidates':sorted(tags),'status':'script_review_required' if ambiguous else ('static_effects_described' if ee else 'no_effect_definition'),
                    'player_selectable':None,'planner_eligible':False,'effects':ee,'reachable_spell_ids':reachable,
                    'source_mentions':{str(k):mentions[k] for k in reachable if mentions[k]},
                    'limitations':['Raw base points are not final damage or modifier amounts.','SQL/C++ correction precedence and script bindings have not been validated.','Native dispatch references do not prove this spell is reachable by a player.']})
(P/'runes-described.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results))
(P/'rune-execution-evidence.json').write_text(json.dumps({'origin':origin,'source_hashes':source_hashes,'records':records},ensure_ascii=False))
md=['# Unresolved rune entries: generated execution descriptions','', 'All descriptions are provisional static interpretations, not verified player-facing tooltips. Amounts, player eligibility and script overrides remain unverified. Damage/resource/timing tags are candidates, not admission to the planner.','']
for r in results:
    md.extend([f"## {r['spell_id']} — {r['name']}",'',r['generated_description'],'',f"Status: {r['status']}. Scope: {', '.join(r['scope_candidates']) or 'no direct combat signal; review needed'}.",''])
(P/'RUNE-DESCRIPTIONS.md').write_text('\n'.join(md))
assert len(results)==len(inputs)==len({r['spell_id'] for r in results})
assert all(r['generated_description'] and not r['planner_eligible'] for r in results)
assert all(e['trigger_spell'] in r['reachable_spell_ids'] for r in results for e in r['effects'] if e['trigger_spell'])
report={'processed':len(results),'status_counts':dict(collections.Counter(r['status'] for r in results)),
        'scope_counts':dict(collections.Counter(t for r in results for t in r['scope_candidates'])),
        'with_combat_signal':sum(bool(r['scope_candidates']) for r in results),
        'execution_records':len(records),'missing_linked_spells':sorted(missing),
        'records_with_source_leads':sum(bool(r['source_mentions']) for r in results),
        'checks':{'complete_unique_coverage':True,'trigger_closure':True,'no_unverified_planner_admission':True,'sqlite_integrity':c.execute('pragma integrity_check').fetchone()[0]}}
(P/'rune-description-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
