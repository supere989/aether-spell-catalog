"""Bounded deterministic combat planner; estimates, never native game execution."""
from __future__ import annotations
import argparse
import copy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path

MODIFIABLE = {'cost', 'gain', 'damage', 'healing', 'cast', 'gcd', 'cooldown', 'periodic_damage', 'periodic_healing', 'control_duration'}
ABILITY_KEYS = MODIFIABLE | {'id', 'name', 'reviewed', 'evidence', 'resource', 'period', 'ticks', 'range', 'requires_stationary', 'school', 'cooldown_start', 'control_category'}

def number(v, name, minimum=0):
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v < minimum:
        raise ValueError(f'{name} must be a finite number >= {minimum}')
    return v

def prepare(profile):
    p = copy.deepcopy(profile)
    allowed = {'mode','duration','step','beam_width','resources','health','initial_health','incoming_dps','distance','moving_windows','silenced_windows','damage_multiplier','healing_multiplier','threat_safe','abilities','modifiers','pvp_weights','dr_reset','control_incoming_reduction'}
    if set(p) - allowed:
        raise ValueError('Unsupported profile fields: '+str(sorted(set(p)-allowed)))
    if p.get('mode') not in {'dps','hps','pvp'}:
        raise ValueError('mode must be dps, hps, or pvp')
    p.setdefault('step', .25); p.setdefault('duration', 30); p.setdefault('beam_width', 24)
    number(p['step'],'step',.05); number(p['duration'],'duration',p['step'])
    if p['duration'] > 180 or not 1 <= p['beam_width'] <= 128 or not isinstance(p['beam_width'],int):
        raise ValueError('duration <= 180 seconds and integer beam_width 1..128 required')
    def ticks(seconds):
        number(seconds,'timing'); q=seconds/p['step']
        if abs(q-round(q)) > 1e-7: raise ValueError('Timing values must align with step; no silent rounding')
        return round(q)
    ticks(p['duration'])
    p.setdefault('resources',{})
    for key, r in p['resources'].items():
        if set(r) != {'cap','initial','regen'}: raise ValueError('Resource requires cap, initial, regen')
        for k,v in r.items(): number(v,key+'.'+k)
        if r['initial'] > r['cap']: raise ValueError('Initial resource exceeds cap')
    p.setdefault('health',10000); p.setdefault('initial_health',p['health']); p.setdefault('incoming_dps',0)
    p.setdefault('distance',0); p.setdefault('damage_multiplier',1); p.setdefault('healing_multiplier',1)
    p.setdefault('threat_safe',True); p.setdefault('moving_windows',[]); p.setdefault('silenced_windows',[])
    p.setdefault('dr_reset',18); p.setdefault('control_incoming_reduction',1)
    p.setdefault('pvp_weights',{'damage':1,'healing':.5,'control_seconds':30,'survival_seconds':10})
    if set(p['pvp_weights']) != {'damage','healing','control_seconds','survival_seconds'}: raise ValueError('Invalid PvP weights')
    for k,v in p['pvp_weights'].items(): number(v,'weight '+k)
    for k in ('health','initial_health','incoming_dps','distance','damage_multiplier','healing_multiplier','dr_reset','control_incoming_reduction'): number(p[k],k)
    if p['health']<=0 or not 0<p['initial_health']<=p['health'] or p['control_incoming_reduction']>1: raise ValueError('Invalid health/control reduction')
    ticks(p['dr_reset'])
    for key in ('moving_windows','silenced_windows'):
        for start,end in p[key]:
            ticks(start); ticks(end)
            if not 0<=start<end<=p['duration']: raise ValueError('Invalid restriction window')
    abilities=p.get('abilities',[])
    if not 1<=len(abilities)<=32: raise ValueError('Provide 1..32 reviewed abilities')
    if len({a['id'] for a in abilities}) != len(abilities): raise ValueError('Duplicate ability ID')
    for a in abilities:
        if set(a)-ABILITY_KEYS: raise ValueError('Unsupported ability fields: '+str(set(a)-ABILITY_KEYS))
        if a.get('reviewed') is not True or not a.get('evidence'): raise ValueError('Unreviewed ability: '+str(a['id']))
        a.setdefault('name',str(a['id'])); a.setdefault('resource',None)
        for k in MODIFIABLE: a.setdefault(k,0)
        a.setdefault('period',0); a.setdefault('ticks',0); a.setdefault('range',40)
        a.setdefault('requires_stationary',bool(a['cast'])); a.setdefault('school','physical')
        a.setdefault('cooldown_start','finish'); a.setdefault('control_category',None)
        if a['resource'] not in p['resources'] and (a['cost'] or a['gain']): raise ValueError('Unknown resource')
        if a['cooldown_start'] not in ('start','finish'): raise ValueError('Invalid cooldown origin')
    # The caller supplies validated native operation order; no automatic slot/build selection.
    selected=set()
    for m in p.get('modifiers',[]):
        required={'id','ability_ids','field','operation','value','reviewed','evidence'}
        if set(m)!=required or m['reviewed'] is not True or not m['evidence']: raise ValueError('Unsupported/unreviewed modifier')
        if m['id'] in selected: raise ValueError('Duplicate modifier ID')
        selected.add(m['id'])
        if m['field'] not in MODIFIABLE or m['operation'] not in ('add','multiply','replace'): raise ValueError('Unsupported modifier operation')
        if isinstance(m['value'],bool) or not isinstance(m['value'],(int,float)) or not math.isfinite(m['value']): raise ValueError('Invalid modifier value')
        if not m['ability_ids'] or set(m['ability_ids'])-{a['id'] for a in abilities}: raise ValueError('Unknown modifier targets')
        for a in abilities:
            if a['id'] in m['ability_ids']:
                k=m['field']; v=m['value']
                a[k]=a[k]+v if m['operation']=='add' else a[k]*v if m['operation']=='multiply' else v
    for a in abilities:
        for k in MODIFIABLE|{'period','range','ticks'}: number(a[k],a['name']+'.'+k)
        if not isinstance(a['ticks'],int) or not 0<=a['ticks']<=100: raise ValueError('Invalid periodic tick count')
        for k in ('cast','gcd','cooldown','period','control_duration'): ticks(a[k])
        if a['ticks'] and not a['period']: raise ValueError('Periodic ticks require period > 0')
        if (a['periodic_damage'] or a['periodic_healing']) and not a['ticks']: raise ValueError('Periodic effect requires tick count')
        if a['control_duration'] and not a['control_category']: raise ValueError('Control needs DR category')
        if p['mode']!='pvp' and a['control_duration']: raise ValueError('Control simulation is supported only in PvP mode')
    return p

@dataclass
class State:
    resources: dict
    health: float
    busy_until: int=0
    cooldowns: dict=field(default_factory=dict)
    events: list=field(default_factory=list)
    generations: dict=field(default_factory=dict)
    dr: dict=field(default_factory=dict)
    control_until: int=0
    damage: float=0
    healing: float=0
    overheal: float=0
    controlled_seconds: float=0
    alive_seconds: float=0
    incoming: float=0
    dead: bool=False
    trace: list=field(default_factory=list)
    hits: list=field(default_factory=list)

def in_window(t, windows): return any(start<=t<end for start,end in windows)

def objective(s,p):
    if p['mode']=='dps': return s.damage
    if p['mode']=='hps': return s.healing
    w=p['pvp_weights']
    return s.damage*w['damage']+s.healing*w['healing']+s.controlled_seconds*w['control_seconds']+s.alive_seconds*w['survival_seconds']

def heal(s,amount,p):
    amount*=p['healing_multiplier']; effective=min(amount,p['health']-s.health)
    s.health+=effective; s.healing+=effective; s.overheal+=amount-effective

def hit(s,amount,t,p):
    amount*=p['damage_multiplier']; s.damage+=amount
    if amount: s.hits.append((t*p['step'],amount))

def apply_events(s,t,p,abilities):
    due=[e for e in s.events if e[0]==t]; s.events=[e for e in s.events if e[0]!=t]
    for _,aid,kind,generation in due:
        a=abilities[aid]
        if kind=='tick':
            if s.generations.get(aid)!=generation: continue
            hit(s,a['periodic_damage'],t,p); heal(s,a['periodic_healing'],p)
            continue
        hit(s,a['damage'],t,p); heal(s,a['healing'],p)
        if a['resource'] in s.resources:
            r=a['resource']; s.resources[r]=min(p['resources'][r]['cap'],s.resources[r]+a['gain'])
        if a['ticks']:
            gen=s.generations.get(aid,0)+1; s.generations[aid]=gen
            s.events.extend((t+round(a['period']/p['step'])*n,aid,'tick',gen) for n in range(1,a['ticks']+1))
        if a['control_duration']:
            cat=a['control_category']; count,reset=s.dr.get(cat,(0,0))
            if t>=reset: count=0
            factor=(1,.5,.25,0)[min(count,3)]
            # DR-reduced durations may be fractional; conservatively round down.
            duration=math.floor(a['control_duration']/p['step']*factor+1e-9)
            if duration:
                end=t+duration; s.control_until=max(s.control_until,end)
                s.dr[cat]=(count+1,end+round(p['dr_reset']/p['step']))


def legal(s,a,t,p):
    now=t*p['step']; end=now+a['cast']
    if s.dead or t<s.busy_until or t<s.cooldowns.get(a['id'],0) or end>p['duration']: return False
    if p['distance']>a['range']: return False
    if a['requires_stationary'] and any(start<max(end,now+p['step']) and stop>now for start,stop in p['moving_windows']): return False
    if a['school']!='physical' and any(start<max(end,now+p['step']) and stop>now for start,stop in p['silenced_windows']): return False
    if (a['damage'] or a['periodic_damage']) and not p['threat_safe']: return False
    return a['cost']<=s.resources.get(a['resource'],0)+1e-9


def start(s,a,t,p):
    before=dict(s.resources)
    if a['resource'] in s.resources: s.resources[a['resource']]-=a['cost']
    finish=t+round(a['cast']/p['step'])
    s.busy_until=t+max(1,round(max(a['cast'],a['gcd'])/p['step']))
    s.cooldowns[a['id']]=(t if a['cooldown_start']=='start' else finish)+round(a['cooldown']/p['step'])
    s.events.append((finish,a['id'],'cast',0))
    s.trace.append({'time':t*p['step'],'ability':a['id'],'finish':finish*p['step'],'resource_before':before,'resource_after_cost':dict(s.resources)})


def advance(s,t,p,abilities):
    dt=p['step']; controlled=t<s.control_until
    incoming=p['incoming_dps']*dt*(1-p['control_incoming_reduction'] if controlled else 1)
    # Interval damage before endpoint healing. No resurrection or healing after death.
    s.incoming+=min(incoming,s.health); s.health=max(0,s.health-incoming)
    s.alive_seconds+=dt
    if controlled: s.controlled_seconds+=dt
    for key,r in p['resources'].items(): s.resources[key]=min(r['cap'],s.resources[key]+r['regen']*dt)
    if s.health<=0: s.dead=True; s.events=[]; return
    apply_events(s,t+1,p,abilities)


def signature(s):
    return (tuple(sorted((k,round(v,7)) for k,v in s.resources.items())),round(s.health,7),s.dead,s.busy_until,
            tuple(sorted(s.cooldowns.items())),tuple(sorted(s.events)),tuple(sorted(s.generations.items())),tuple(sorted(s.dr.items())),s.control_until)


def evaluate(profile):
    p=prepare(profile); abilities={a['id']:a for a in p['abilities']}; horizon=round(p['duration']/p['step'])
    beam=[State({k:r['initial'] for k,r in p['resources'].items()},p['initial_health'])]
    for t in range(horizon):
        candidates={}
        for state in beam:
            choices=[None]+[a for a in p['abilities'] if legal(state,a,t,p)] if not state.dead else [None]
            for action in choices:
                s=copy.deepcopy(state)
                if action: start(s,action,t,p); apply_events(s,t,p,abilities)
                if not s.dead: advance(s,t,p,abilities)
                key=signature(s)
                old=candidates.get(key)
                if old is None or objective(s,p)>objective(old,p): candidates[key]=s
        def rank(s):
            # Pending direct effects prevent slow casts being pruned purely for latency.
            pending=sum((abilities[aid]['damage']*p['damage_multiplier'] if p['mode']!='hps' else min(abilities[aid]['healing']*p['healing_multiplier'],p['health']-s.health)) for end,aid,kind,gen in s.events if kind=='cast' and end<=horizon)
            return (objective(s,p)+pending, s.health, sum(s.resources.values()),-len(s.trace))
        beam=sorted(candidates.values(),key=rank,reverse=True)[:p['beam_width']]
    best=max(beam,key=lambda s:(objective(s,p),s.health,sum(s.resources.values())))
    # Five-second half-open windows: [first hit, first hit + 5).
    burst=max((sum(d for t,d in best.hits if start<=t<start+5) for start,_ in best.hits),default=0)
    duration=p['duration']
    return {'algorithm':'bounded_beam_v1','mode':p['mode'],'duration':duration,'step':p['step'],'beam_width':p['beam_width'],
            'estimated_dps':best.damage/duration,'estimated_effective_hps':best.healing/duration,
            'damage':best.damage,'effective_healing':best.healing,'overhealing':best.overheal,
            'pvp':{'five_second_burst_damage':burst,'control_seconds':best.controlled_seconds,'control_uptime':best.controlled_seconds/duration,'survival_seconds':best.alive_seconds,'survived':not best.dead} if p['mode']=='pvp' else None,
            'health_remaining':best.health,'resources_remaining':best.resources,'objective_score':objective(best,p),
            'selected_modifiers':[m['id'] for m in p.get('modifiers',[])],'rotation':best.trace,
            'limits':['Estimated deterministic throughput; no global optimality or win-rate claim.',
                      'One target/health pool; incoming damage and mitigation are supplied scenario inputs.',
                      'No random procs, auto-attacks, channels, absorbs, interrupts, dispels, pets, enemy decisions or multi-target model.',
                      'Periodic effects refresh per ability; no pandemic extension or cross-spell exclusivity.',
                      'Continuous resource regeneration; no discrete rune recharge, casting regen suppression or combo-point model.',
                      'At most one action per simulation step; timing inputs must align to the grid.',
                      'PvP control uses configured generic disable reduction and 1/0.5/0.25/0 DR; not a live-rule assertion.',
                      'Reviewed inputs and modifier order must be supplied; catalog descriptions are not executable rules.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',type=Path); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=evaluate(json.loads(args.profile.read_text()))
    text=json.dumps(result,indent=2)+'\n'
    if args.output: args.output.write_text(text)
    else: print(text,end='')
