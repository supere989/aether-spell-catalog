"""Read-only capture of available set items from local qualification database."""
import json,subprocess,struct,hashlib
from pathlib import Path
import paths
OUT=Path(__file__).resolve().parent
args,env=paths.mysql_args(['--batch','--raw']);db=paths.world_db()['database']
def query(q):
 r=subprocess.run(args,input=q,text=True,capture_output=True,env=env,timeout=90)
 if r.returncode:raise RuntimeError('Read-only item query failed')
 lines=r.stdout.splitlines();keys=lines[0].split('\t')
 return [dict(zip(keys,line.split('\t'))) for line in lines[1:]]
p=paths.path('dbc')/'ItemSet.dbc';b=p.read_bytes();_,n,f,z,ss=struct.unpack_from('<4s4I',b);strings=b[20+n*z:]
sets=[]
for i in range(n):
 r=struct.unpack_from('<'+str(f)+'I',b,20+i*z)
 sets.append(dict(id=r[0],name=strings[r[1]:].split(b'\0')[0].decode(),items=[v for v in r[18:35] if v],bonuses=[dict(spell_id=r[35+j],pieces=r[43+j]) for j in range(8) if r[35+j]],required_skill=r[51],required_skill_rank=r[52]))
ids=sorted({i for s in sets for i in s['items']})
columns=['entry','name','class','subclass','InventoryType','AllowableClass','RequiredLevel','Quality','ItemLevel','itemset','armor','block','delay','dmg_min1','dmg_max1','dmg_type1','dmg_min2','dmg_max2','ScalingStatDistribution','ScalingStatValue','RandomProperty','RandomSuffix']+[f'stat_{k}{i}' for i in range(1,11) for k in ('type','value')]+[f'spellid_{i}' for i in range(1,6)]
rows=query('SELECT '+','.join('`'+c+'`' for c in columns)+' FROM item_template WHERE itemset<>0 OR entry IN ('+','.join(map(str,ids))+');')
(OUT/'gear-source.json').write_text(json.dumps(dict(source_database=db,source_kind='local qualification database; not live realm verification',dbc_sha256=hashlib.sha256(b).hexdigest(),sets=sets,items=rows),indent=2))
print(json.dumps(dict(sets=len(sets),items=len(rows),custom_class_items=sum(int(r['AllowableClass'])>0 and bool(int(r['AllowableClass'])&sum(1<<(c-1) for c in range(12,33))) for r in rows))))
