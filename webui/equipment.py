"""Explicit simulation equipment; no claims of live item or equip-rule parity."""
import math
from gear_catalog import resolve_equipment
SLOTS=('head','neck','shoulders','back','chest','shirt','tabard','wrists','hands','waist','legs','feet','finger1','finger2','trinket1','trinket2','main_hand','off_hand','ranged')
BONUSES=('strength','agility','stamina','intellect','spirit','ap','rap','sp','healing','health','mana','dodge','parry','block','block_value')
def number(v,name,lo=0,hi=1000000):
 if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid '+name)
 return v

def equipped(slot):
 slot,set_bonus,_,_=resolve_equipment(slot)
 gear=slot.get('gear',{})
 if not isinstance(gear,dict) or set(gear)-set(SLOTS):raise ValueError('Invalid equipment slots')
 result=dict(slot);bonus={k:set_bonus.get(k,0) for k in BONUSES}
 for place,item in gear.items():
  if not isinstance(item,dict) or set(item)-{'name','stats','weapon_damage','weapon_speed','kind'}:raise ValueError('Invalid equipment item')
  if not isinstance(item.get('name',''),str) or len(item.get('name',''))>100:raise ValueError('Invalid item name')
  values=item.get('stats',{})
  if not isinstance(values,dict) or set(values)-set(BONUSES):raise ValueError('Unsupported item stat')
  for key,value in values.items():bonus[key]+=number(value,key,hi=100 if key in ('dodge','parry','block') else 1000000)
  kind=item.get('kind','armor')
  if kind not in ('armor','weapon','shield','two_hand'):raise ValueError('Invalid equipment kind')
  if kind=='shield' and place!='off_hand':raise ValueError('Shields belong in off hand')
  if kind=='two_hand' and place!='main_hand':raise ValueError('Two-handed weapons belong in main hand')
  if kind=='weapon' and place not in ('main_hand','off_hand','ranged'):raise ValueError('Invalid weapon slot')
  if 'weapon_damage' in item or 'weapon_speed' in item:
   if kind not in ('weapon','two_hand'):raise ValueError('Weapon fields require a weapon')
   damage=number(item.get('weapon_damage',0),'weapon damage');speed=number(item.get('weapon_speed',2.5),'weapon speed',.1,10)
   if place=='main_hand':result.update(weapon=damage,weapon_speed=speed)
 if gear.get('main_hand',{}).get('kind')=='two_hand' and gear.get('off_hand'):raise ValueError('Unequip off hand before equipping a two-handed weapon')
 # Base inputs already include their base attribute contribution: add only the gear delta.
 def attr_delta(key,scale):
  before=number(slot.get(key,150),key);after=before+bonus[key]
  return min(after,20)+max(0,after-20)*scale-min(before,20)-max(0,before-20)*scale
 bonus['health']+=attr_delta('stamina',10)
 bonus['mana']+=attr_delta('intellect',15)
 # Source-confirmed CoA unshifted AP deltas; other class/form conversions remain explicit AP inputs.
 coefficients={12:(1,1),30:(2,1),27:(2,0),26:(1,1)}
 if slot.get('class_id') in coefficients:
  strength,agility=coefficients[slot['class_id']];bonus['ap']+=strength*bonus['strength']+agility*bonus['agility']
 defaults={'health':6000,'mana':4000,'ap':500,'rap':500,'sp':500,'healing':500,'strength':150,'agility':150,'stamina':150,'intellect':150,'spirit':150}
 for key,value in bonus.items():result[key]=number(slot.get(key,defaults.get(key,0)),key)+value
 for key in ('dodge','parry','block'):result[key]=min(100,result[key])
 if 'gear' in slot:result['shield_equipped']=gear.get('off_hand',{}).get('kind')=='shield'
 return result,bonus
