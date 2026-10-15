"""Extend visual index with item meshes; extraction remains lazy and read only."""
# Reuse the archive resolver; restores metadata then exports player geometry afterward.
from build_visuals import *
for key in available:
 if key.startswith('item\\') and key.endswith('.blp'):register(key)
catalog=json.loads((B/'gear-catalog.json').read_text());slots={}
for i in catalog['items'].values():slots.setdefault(item_map.get(str(i['id'])),set()).add(i['slot'])
suffix={1:'Hu',2:'Or',3:'Dw',4:'Ni',5:'Sc',6:'Ta',7:'Gn',8:'Tr',10:'Be',11:'Dr'}
def model(folder,name,tex,racial=''):
 if not name:return None
 stem=re.sub(r'\.(mdx|m2)$','',name,flags=re.I)
 paths=[f'item\\objectcomponents\\{folder}\\{stem}{racial}.m2',f'item\\objectcomponents\\{folder}\\{stem}.m2']
 path=next((x for x in paths if x.lower() in available),None)
 if not path:return None
 m=register(path);sk=register(path[:-3]+'00.skin')
 if not sk:return None
 t=texture(f'item\\objectcomponents\\{folder}\\{tex}.blp') if tex else None
 return dict(model=m,skin=sk,texture=t)
visrows={str(r[0]):r[1:] for r in appearance['HelmetGeosetVisData']}
displayvis={str(r[0]):[visrows.get(str(r[1]),[0]*7),visrows.get(str(r[2]),[0]*7)] for r in appearance['ItemDisplayInfo']}
for did,d in visuals.items():
 d['helmet_visibility']=displayvis.get(did,[[0]*7,[0]*7])
 places=slots.get(did,set());d['attachments']={}
 for place in places:
  if place=='head':
   d['attachments']['head']={p['id']:model('head',d['models'][0],d['model_textures'][0],'_'+suffix[p['race']]+('M' if p['sex']==0 else 'F')) for p in profiles}
  elif place=='shoulders':d['attachments'][place]=[model('shoulder',n,t) for n,t in zip(d['models'],d['model_textures'])]
  elif place in ('main_hand','off_hand','ranged'):
   d['attachments'][place]=next((m for folder in ('weapon','shield','quiver') if (m:=model(folder,d['models'][0],d['model_textures'][0]))),None)
  elif place=='back':d['cape_texture']=texture('item\\objectcomponents\\cape\\'+d['model_textures'][0]+'.blp') if d['model_textures'][0] else None
(B/'assets/manifest.json').write_text(json.dumps(dict(files=files,missing=sorted(missing)),separators=(',',':')))
(B/'assets/visuals.json').write_text(json.dumps(dict(items=item_map,displays=visuals,profiles=profiles),separators=(',',':')))
print('Item model references staged')
