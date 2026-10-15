import hashlib,json,re
from pathlib import Path
import paths
ROOT=paths.path('coa_src')/'src/server/coa'
OUT=Path(__file__).resolve().parent/'mechanics-source.json'
data={'coefficients':{},'sources':{},'progression':[],'stock_zero':[],'resource_gains':[],'resource_costs':[],'resource_displays':[]}
def read(name):
 p=ROOT/name;s=p.read_text();data['sources'][name]=hashlib.sha256(p.read_bytes()).hexdigest();return s
for name in ['Pyromancer','SunCleric','Templar','Felsworn','Necromancer','Cultist','Starcaller','Tinker','Venomancer','Xoroth']:
 s=read('Ascension'+name+'Data.h');m=re.search(r'struct '+name+r'Coefficient\s*\{(.*?)\};',s,re.S)
 fields=[]
 for typ,names in re.findall(r'(uint32|uint8|float|bool)\s+([^;]+);',m.group(1)):
  fields.extend(x.strip() for x in names.split(','))
 body=s.split(name+'Coefficients',1)[1].split('};',1)[0]
 for row in re.findall(r'\{([^{}]+)\}',body):
  parts=[x.strip() for x in row.split(',')]
  if len(parts)!=len(fields):raise ValueError((name,parts,fields))
  vals=[]
  for x in parts:
   vals.append(True if x=='true' else False if x=='false' else float(x[:-1]) if x.endswith('f') else int(x,0))
  d=dict(zip(fields,vals));
  if 'id' in d:d['spell']=d.pop('id')
  if name=='Necromancer':d['heal']=d.pop('healing')
  d['source']='Ascension'+name+'Data.h';d['class_contract']=name
  data['coefficients'][str(d['spell'])+':'+str(d['effect'])]=d
s=read('AscensionSpellProgressionData.h')
data['progression']=[list(map(int,m)) for m in re.findall(r'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',s)]
s=read('AscensionStockCoefficientData.h').split('StockCoefficientSpells',1)[1].split('{{',1)[1].split('}}',1)[0]
data['stock_zero']=list(map(int,re.findall(r'\d+',s)))
s=read('AscensionCustomResourceData.h')
for name,key in [('ResourceGainRules','resource_gains'),('ResourceCostRules','resource_costs'),('ResourceDisplays','resource_displays')]:
 body=s.split(name+' =',1)[1].split('}};',1)[0]
 for row in re.findall(r'\{([^{}]+)\}',body):
  parts=[x.strip() for x in row.split(',')];v=[]
  for x in parts:
   v.append(int(x) if re.fullmatch(r'-?\d+',x) else x.split('::')[-1].strip('"'))
  data[key].append(v)
for name in ['AscensionPyromancer.cpp','AscensionPyromancerContracts.cpp','AscensionSunClericContracts.cpp','AscensionTemplarContracts.cpp','AscensionFelswornContracts.cpp','AscensionNecromancerContracts.cpp','AscensionCultistContracts.cpp','AscensionStarcallerContracts.cpp','AscensionTinkerContracts.cpp','AscensionVenomancerContracts.cpp','AscensionXorothContracts.cpp','AscensionRunemasterScaling.cpp']:
 read(name)
OUT.write_text(json.dumps(data,indent=2)+'\n')
print({k:len(v) for k,v in data.items()})
