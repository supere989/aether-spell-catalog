"""Immutable local catalog lookup and server-side equipment resolution."""
import json
from pathlib import Path
from functools import lru_cache
from collections import Counter
@lru_cache(maxsize=1)
def catalog():
 data=json.loads((Path(__file__).parent/'gear-catalog.json').read_text());data['by_set']={s['id']:s for s in data['sets']};return data

def item(identity):
 if isinstance(identity,bool) or not isinstance(identity,int):raise ValueError('Catalog item ID must be an integer')
 value=catalog()['items'].get(str(identity))
 if value is None:raise ValueError('Unknown catalog item')
 return value

def resolve_equipment(slot):
 gear=slot.get('gear',{});resolved={};counts=Counter();seen=set();warnings=[]
 if not isinstance(gear,dict):raise ValueError('Invalid gear')
 for place,entry in gear.items():
  if not isinstance(entry,dict):raise ValueError('Invalid item')
  if 'catalog_id' not in entry:resolved[place]=entry;continue
  obj=item(entry['catalog_id']);dest=obj['slot']
  compatible=place==dest or (dest=='finger1' and place=='finger2') or (dest=='trinket1' and place=='trinket2')
  if not obj['equippable'] or not compatible:raise ValueError('Catalog item cannot occupy this slot')
  if slot.get('class_id') not in obj['allowed_classes']:raise ValueError('Catalog item class restriction')
  if slot.get('level',60)<obj['required_level']:raise ValueError('Catalog item requires a higher level')
  if obj['id'] in seen:raise ValueError('Duplicate catalog piece; choose a different item')
  seen.add(obj['id']);counts[obj['set_id']]+=1
  resolved[place]={k:obj[k] for k in ('name','kind','stats','weapon_damage','weapon_speed') if k in obj}
  warnings.extend(f"{obj['name']}: {warning}" for warning in obj['warnings'])
 bonuses={};sets=[]
 for sid,count in counts.items():
  definition=catalog()['by_set'][sid];active=[]
  for bonus in definition['bonuses']:
   if count>=bonus['pieces']:
    active.append(bonus)
    if bonus['modeled']:
     for key,value in bonus['stats'].items():bonuses[key]=bonuses.get(key,0)+value
  sets.append(dict(id=sid,name=definition['name'],pieces=count,bonuses=active))
 result=dict(slot)
 if 'gear' in slot:result['gear']=resolved
 return result,bonuses,sets,warnings

def search_sets(q='',offset=0,stats_only=False):
 data=catalog();rows=[s for s in data['sets'] if (q.lower() in s['name'].lower() or q==str(s['id'])) and (not stats_only or s['has_modeled_stats'])]
 return dict(total=len(rows),offset=offset,report=data['report'],sets=[{k:s[k] for k in ('id','name','class_scope','has_modeled_stats','usable_pieces')}|{'items':len(s['items']),'bonuses':len(s['bonuses'])} for s in rows[offset:offset+100]])

def set_detail(identity):
 s=catalog()['by_set'].get(identity)
 if not s:raise ValueError('Unknown set')
 return dict(s,items=[item(i) for i in s['items']])

def search_items(place,class_id,level,q='',offset=0):
 allowed={'head','neck','shoulders','back','chest','shirt','tabard','wrists','hands','waist','legs','feet','finger1','finger2','trinket1','trinket2','main_hand','off_hand','ranged'}
 if place not in allowed or class_id not in range(12,33) or not 1<=level<=80:raise ValueError('Invalid character or equipment slot')
 dest={'finger2':'finger1','trinket2':'trinket1'}.get(place,place)
 rows=[i for i in catalog()['items'].values() if i['equippable'] and i['slot']==dest and class_id in i['allowed_classes'] and i['required_level']<=level and (q.lower() in i['name'].lower() or q==str(i['id']))]
 rows.sort(key=lambda i:(-i['item_level'],i['name'],i['id']))
 offset=max(0,offset)
 return dict(total=len(rows),offset=offset,items=rows[offset:offset+40])
