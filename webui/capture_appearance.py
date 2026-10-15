import json,struct
from pathlib import Path
b=Path(__file__).parent
out={}
for name in ('CharHairGeosets','CharacterFacialHairStyles','HelmetGeosetVisData','ItemDisplayInfo'):
 raw=Path('/tmp/coa-restart-validation/data/dbc',name+'.dbc').read_bytes();_,n,f,z,_=struct.unpack_from('<4s4I',raw)
 rows=[struct.unpack_from('<'+str(f)+'I',raw,20+i*z) for i in range(n)]
 out[name]=[[r[0],r[13],r[14]] for r in rows] if name=='ItemDisplayInfo' else rows
(b/'appearance-source.json').write_text(json.dumps(out))
