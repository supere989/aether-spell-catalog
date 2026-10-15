import os,re,json,subprocess,struct
from pathlib import Path
B=Path(__file__).resolve().parent
conf=Path('/work/wow-coa/dungeon-runs/fixture-observer-isolation-witness/worldserver.conf')
host,port,user,password,db=re.search(r'^WorldDatabaseInfo\s*=\s*"([^"]+)"',conf.read_text(),re.M).group(1).split(';')
env=os.environ.copy();env['MYSQL_PWD']=password
r=subprocess.run(['mysql','-h',host,'-P',port,'-u',user,'--batch','--raw','--skip-column-names',db],input='SELECT entry,displayid FROM item_template WHERE itemset<>0;',env=env,capture_output=True,text=True,timeout=90)
if r.returncode:raise RuntimeError('Visual lookup failed')
displays={int(a):int(b) for a,b in (line.split('\t') for line in r.stdout.splitlines())}
def dbc(name):
 b=Path('/tmp/coa-restart-validation/data/dbc',name+'.dbc').read_bytes();_,n,f,z,_=struct.unpack_from('<4s4I',b);strings=b[20+n*z:]
 def st(offset):return strings[offset:strings.find(b'\0',offset)].decode(errors='replace')
 return [struct.unpack_from('<'+str(f)+'I',b,20+i*z) for i in range(n)],st
rows,st=dbc('ItemDisplayInfo');lookup={r[0]:r for r in rows};items={}
for identity,display in displays.items():
 row=lookup.get(display)
 if not row:continue
 items[str(identity)]=dict(display=display,icon=st(row[5]),models=[st(row[i]) for i in (1,2)],model_textures=[st(row[i]) for i in (3,4)],components=[st(row[i]) for i in range(15,23)],geosets=list(row[7:10]))
rows,st=dbc('CharSections');sections=[dict(race=r[1],sex=r[2],kind=r[3],textures=[st(r[i]) for i in (4,5,6)],flags=r[7],variation=r[8],color=r[9]) for r in rows if r[1] in (1,2,3,4,5,6,7,8,10,11)]
(B/'visual-source.json').write_text(json.dumps(dict(items=items,sections=sections),separators=(',',':')))
print('Visual metadata:',len(items),'items,',len(sections),'character sections')
