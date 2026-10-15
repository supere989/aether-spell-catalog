import sys,json,hashlib
import paths
sys.path.insert(0,str(paths.path('third_party')))
from pywowlib.m2_file import M2File
from pywowlib.file_formats.skin_format import M2SkinProfile
from asset_io import BASE,extract,manifest
from model_pose import pose
identity,skin=sys.argv[1:3];m=M2File(2,str(extract(identity)))
with extract(skin).open('rb') as f:s=M2SkinProfile().read(f)
def flat(name):return [round(float(x),6) for v in m.root.vertices for x in getattr(v,name)]
textures=[]
for t in m.root.textures:
 path=t.filename.value.replace('/','\\').lower();key=hashlib.sha256(path.encode()).hexdigest()[:32]
 textures.append('/assets/'+key+'.png' if key in manifest()['files'] else None)
units={}
for u in s.texture_units:units.setdefault(int(u.skin_section_index),int(m.root.texture_lookup_table[u.texture_combo_index]))
positions,normals,_=pose(m.root)
d=dict(positions=positions,normals=normals,uv=flat('tex_coords'),indices=[int(s.vertex_indices[i]) for i in s.triangle_indices],groups=[dict(start=int(g.index_start),count=int(g.index_count),texture=textures[units[i]] if i in units else None) for i,g in enumerate(s.submeshes)])
folder=BASE/'assets/item-models-v2';folder.mkdir(exist_ok=True);target=folder/(identity+'.json');temp=target.with_suffix('.tmp');temp.write_text(json.dumps(d,separators=(',',':')));temp.replace(target)
