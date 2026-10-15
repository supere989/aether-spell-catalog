"""Stage local-only visual references and static player meshes from installed archives."""
import json,re,hashlib,sys,struct
from pathlib import Path
import paths
B=Path(__file__).resolve().parent;CLIENT=paths.path('client_root');CATALOG=paths.path('asset_catalog');DATA=CLIENT/'Data'
source=json.loads((B/'visual-source.json').read_text());available={}
archives={p.name.lower():p for p in DATA.glob('*.MPQ')};archives.update({'enus_'+p.name.lower():p for p in (DATA/'enUS').glob('*.MPQ')})
def priority(name):
 name=name.lower().replace('enus_','');return (3 if name.startswith('patch') else 2 if name.startswith('lichking') else 1 if name.startswith('expansion') else 0,name)
for listing in sorted((CATALOG/'mpq-index').glob('*.txt'),key=lambda p:priority(p.name)):
 archive=archives.get(listing.name[:-4].lower())
 if not archive:continue
 for line in listing.read_text(errors='replace').splitlines():
  match=re.match(r'\s*\d+\s+(.+)$',line)
  if match:
   path=match[1];key=path.replace('/','\\').lower()
   if key.startswith(('interface\\icons\\','character\\','item\\')):available[key]=(str(archive.relative_to(CLIENT)),path)
files={};missing=set()
def register(path):
 if not path:return None
 path=path.replace('/','\\').lower()
 if path not in available:missing.add(path);return None
 identity=hashlib.sha256(path.encode()).hexdigest()[:32];archive,original=available[path];files[identity]={'archive':archive,'path':original};return identity

def texture(path):
 identity=register(path);return '/assets/'+identity+'.png' if identity else None
regions=['armupper','armlower','hand','torsoupper','torsolower','legupper','leglower','foot']
visuals={};item_map={}
for identity,item in source['items'].items():
 display=str(item['display']);item_map[identity]=display
 if display in visuals:continue
 components=[]
 for region,name in zip(regions,item['components']):
  if not name:continue
  male=next((f'item\\texturecomponents\\{region}texture\\{name}{suffix}.blp' for suffix in ('_u','_m','') if f'item\\texturecomponents\\{region}texture\\{name}{suffix}.blp'.lower() in available),None)
  female=next((f'item\\texturecomponents\\{region}texture\\{name}{suffix}.blp' for suffix in ('_u','_f','') if f'item\\texturecomponents\\{region}texture\\{name}{suffix}.blp'.lower() in available),None)
  components.append(dict(region=region,male=texture(male),female=texture(female)))
 visuals[display]=dict(icon=texture('interface\\icons\\'+item['icon']+'.blp') if item['icon'] else None,components=components,models=item['models'],model_textures=item['model_textures'],geosets=item['geosets'])
profiles=[]
appearance=json.loads((B/'appearance-source.json').read_text())
races={1:'Human',2:'Orc',3:'Dwarf',4:'NightElf',5:'Scourge',6:'Tauren',7:'Gnome',8:'Troll',10:'BloodElf',11:'Draenei'}
for race,folder in races.items():
 for sex,gender in enumerate(('Male','Female')):
  prefix=f'character\\{folder}\\{gender}\\{folder}{gender}'
  model=register(prefix+'.m2');skin=register(prefix+'00.skin')
  if not model or not skin:continue
  parts={};hair_geoset=0
  hair_rows=[r for r in appearance['CharHairGeosets'] if r[1]==race and r[2]==sex and r[4]>0]
  selected_hair=None
  for r in sorted(hair_rows,key=lambda r:r[3]):
   candidates=[s for s in source['sections'] if s['race']==race and s['sex']==sex and s['kind']==3 and s['variation']==r[3] and s['textures'][0].lower() in available]
   if candidates:selected_hair=min(candidates,key=lambda s:s['color']);hair_geoset=r[4];break
  face_rows=[r for r in appearance['CharacterFacialHairStyles'] if r[0]==race and r[1]==sex]
  face_row=min(face_rows,key=lambda r:r[2]) if face_rows else None
  facial=[100+face_row[3],200+face_row[5],300+face_row[4]] if face_row else []
  for kind in (0,1,3,4):
   choices=[s for s in source['sections'] if s['race']==race and s['sex']==sex and s['kind']==kind]
   choices.sort(key=lambda s:(s['color'],s['variation']))
   if kind==3 and selected_hair:choices=[selected_hair]
   if choices:parts[str(kind)]=[texture(t) for t in choices[0]['textures']]
  profiles.append(dict(id=f'{race}-{sex}',name=folder+' '+gender,race=race,sex=sex,m2=model,skin=skin,textures=parts,hair_geoset=hair_geoset,facial_geosets=facial))
(B/'assets/manifest.json').write_text(json.dumps(dict(files=files,missing=sorted(missing),note='Archive listing precedence, lexical patch order; model/skin source recorded. Local previews only.'),separators=(',',':')))
(B/'assets/visuals.json').write_text(json.dumps(dict(items=item_map,displays=visuals,profiles=profiles),separators=(',',':')))
print('Planned',len(files),'assets,',len(visuals),'displays,',len(profiles),'race/sex profiles; missing',len(missing))
