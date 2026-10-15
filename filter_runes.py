"""Conservative description triage, not proof of selectable rune mechanics."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATTERNS = {
    'damage': r'\b(damage|attack power|spell power|critical strike|critical hit|armor penetration|spell penetration|expertise|hit rating|strength|agility|intellect)\b',
    'resource': r'\b(mana|energy|rage|runic power|resource|regenerat\w*|restor\w* .{0,30}runes?|rune .{0,20}(cost|refresh|recharg)|cost .{0,20}reduc\w*)\b',
    'timing': r'\b(cooldown|haste|casting speed|cast speed|attack speed|casting time|cast time|global cooldown|recharge|charges)\b',
}
EXCLUDE = r'\b(cosmetic|appearance|transmog\w*|teleport\w*|mount|movement speed|swim\w*|water walking|opens? .{0,30}(container|door)|heals?|healing|parry|disarm|silence|immobili\w*|summon\w*)\b'

def classify(row):
    description = row.get('description') or ''
    matches = {kind: sorted(set(m.group(0).lower() for m in re.finditer(pattern, description, re.I)))
               for kind, pattern in PATTERNS.items()}
    matches = {kind: values for kind, values in matches.items() if values}
    # Broad matches deliberately remain review candidates: costs in a tooltip do
    # not establish a cost modifier; NPC attacks do not establish player eligibility.
    if matches:
        bucket = 'combat_candidates'
    elif re.search(EXCLUDE, description, re.I):
        bucket = 'out_of_scope_candidates'
    else:
        bucket = 'unresolved'
    return {**row, 'triage': bucket, 'scope_signals': matches,
            'classification_method': 'description_keywords_v1',
            'planner_eligible': False}

if __name__ == '__main__':
    rows = [classify(json.loads(line)) for line in (ROOT/'rune-candidates.jsonl').read_text().splitlines()]
    counts = {}
    for bucket in ('combat_candidates', 'out_of_scope_candidates', 'unresolved'):
        subset = [r for r in rows if r['triage'] == bucket]
        counts[bucket] = len(subset)
        (ROOT/f'runes-{bucket}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in subset))
    assert sum(counts.values()) == len(rows) == len({r['spell_id'] for r in rows})
    assert classify({'description':'Reduces Fireball cooldown and changes its appearance'})['triage'] == 'combat_candidates'
    assert classify({'description':'Changes your appearance'})['triage'] == 'out_of_scope_candidates'
    assert classify({'description':''})['triage'] == 'unresolved'
    assert classify({'description':'Restores mana when dealing damage'})['scope_signals'].keys() == {'damage','resource'}
    report = {'counts':counts,'total':len(rows),'partition_check':'passed','classification_checks':'passed',
              'limitations':['Name-search cohort only; modifiers without rune in their names may be absent.',
                            'Keyword triage is not semantic validation or confirmed player eligibility.',
                            'Empty or indirect descriptions remain unresolved, not discarded.',
                            'Utility effects with indirect DPS interactions require review.']}
    (ROOT/'rune-triage-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    manifest = {f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
                for f in sorted(ROOT.iterdir()) if f.is_file() and f.name != 'manifest.json'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(report,indent=2))
