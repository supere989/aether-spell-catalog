"""Export static WotLK bind-pose geometry; never edits client archives."""
import sys,json,hashlib,math
from pathlib import Path
import paths
sys.path.insert(0,str(paths.path('third_party')))
from pywowlib.m2_file import M2File
from pywowlib.file_formats.skin_format import M2SkinProfile
from asset_io import BASE,extract
from model_pose import pose
v=json.loads((BASE/'assets/visuals.json').read_text());out=BASE/'assets/models';out.mkdir(exist_ok=True)
for p in v['profiles']:
 try:
  raw=extract(p['m2']);m=M2File(2,str(raw))
  with extract(p['skin']).open('rb') as f:s=M2SkinProfile().read(f)
  vertices=m.root.vertices
  def flat(attr):return [round(float(x),6) for vert in vertices for x in getattr(vert,attr)]
  indices=[int(s.vertex_indices[i]) for i in s.triangle_indices]
  assert all(0<=i<len(vertices) for i in indices)
  types={}
  for u in s.texture_units:
   types.setdefault(int(u.skin_section_index),int(m.root.textures[m.root.texture_lookup_table[u.texture_combo_index]].type))
  positions,normals,mounts=pose(m.root)
  d={'positions':positions,'normals':normals,'attachment_matrices':mounts,'pose':'standing-first-frame','uv':flat('tex_coords'),'indices':indices,'groups':[{'id':int(g.skin_section_id),'start':int(g.index_start),'count':int(g.index_count),'texture_type':types.get(i,1)} for i,g in enumerate(s.submeshes)],'attachments':{str(a.id):list(a.position) for a in m.root.attachments},'source_sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
  assert all(math.isfinite(x) for k in ('positions','normals','uv') for x in d[k])
  (out/(p['id']+'.json')).write_text(json.dumps(d,separators=(',',':')))
  p['model']='/models/'+p['id']+'.json';print(p['name'],len(vertices),flush=True)
 except Exception as e:p['error']=str(e);print('FAILED',p['name'],e,flush=True)
(BASE/'assets/visuals.json').write_text(json.dumps(v,separators=(',',':')))
