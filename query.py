import argparse
import json
from pathlib import Path
import sqlite3

p=argparse.ArgumentParser(description='Read-only CoA spell catalog lookup')
p.add_argument('--id',type=int)
p.add_argument('--class-id',type=int)
p.add_argument('--search',default='')
p.add_argument('--limit',type=int,default=20)
a=p.parse_args()
c=sqlite3.connect((Path(__file__).with_name('catalog.sqlite')).as_uri()+'?mode=ro',uri=True)
c.execute('PRAGMA query_only=ON')
if a.id is not None:
    row=c.execute('SELECT logic_json FROM abilities WHERE id=?',(a.id,)).fetchone()
    data=json.loads(row[0]) if row else {'status':'not in detailed cohort','id':a.id}
    generated=c.execute('SELECT evidence_json FROM generated_spell_descriptions WHERE spell_id=?',(a.id,)).fetchone()
    data['generated_interpretation']=json.loads(generated[0]) if generated else None
    data['acquisitions']=[dict(zip(['class_id','level','source','entry'],r)) for r in c.execute('SELECT class_id,level,source,source_entry FROM acquisitions WHERE spell_id=?',(a.id,))]
    data['source_mentions']=[dict(zip(['path','line','evidence'],r)) for r in c.execute('SELECT path,line,evidence FROM source_mentions WHERE spell_id=? LIMIT 30',(a.id,))]
    data['scenario_definitions']=[dict(zip(['path','name'],r)) for r in c.execute('SELECT path,name FROM scenario_links WHERE spell_id=?',(a.id,))]
else:
    conditions=['s.name LIKE ?']; values=['%'+a.search+'%']
    if a.class_id is not None:
        conditions.append('EXISTS(SELECT 1 FROM acquisitions a WHERE a.spell_id=s.id AND a.class_id=?)'); values.append(a.class_id)
    values.append(max(1,min(a.limit,200)))
    data=[dict(zip(['id','name','level','power_type','raw_base_cost'],r)) for r in c.execute('SELECT s.id,s.name,s.level,s.power_type,s.base_cost FROM spell_index s WHERE '+' AND '.join(conditions)+' ORDER BY s.level,s.id LIMIT ?',values)]
print(json.dumps(data,indent=2,ensure_ascii=False))
