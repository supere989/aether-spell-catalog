"""Read-only client extraction into a local, hash-addressed cache."""
import json,hashlib,subprocess,threading,struct
from pathlib import Path
from functools import lru_cache
BASE=Path(__file__).resolve().parent
LOCK=threading.RLock()
@lru_cache(maxsize=1)
def manifest():return json.loads((BASE/'assets/manifest.json').read_text())
def extract(identity):
 record=manifest()['files'].get(identity)
 if record is None:raise ValueError('Unknown asset')
 target=BASE/'assets/raw'/identity
 with LOCK:
  if not target.exists():
   temp=target.with_suffix('.tmp')
   result=subprocess.run([str(BASE/'tools/mpqextract'),'extract',record['archive'],record['path'],str(temp)],capture_output=True,timeout=25)
   if result.returncode:temp.unlink(missing_ok=True);raise ValueError('Client asset could not be extracted')
   temp.replace(target)
 return target

def decode_texture(path):
 from PIL import Image
 raw=Path(path).read_bytes()
 if raw[:4]==b'BLP2' and raw[8]==1:
  depth=raw[9];width,height=struct.unpack_from('<II',raw,12);offset=struct.unpack_from('<I',raw,20)[0];n=width*height
  if not 0<width<=4096 or not 0<height<=4096 or depth not in (0,1,4,8):raise ValueError('Unsupported paletted texture')
  needed=(n*depth+7)//8
  if len(raw)<offset+n+needed or len(raw)<1172:raise ValueError('Truncated paletted texture')
  palette=raw[148:1172];indices=raw[offset:offset+n];alpha=raw[offset+n:offset+n+needed];pixels=bytearray(n*4)
  for i,index in enumerate(indices):
   b,g,r,_=palette[index*4:index*4+4]
   a=255 if depth==0 else alpha[i] if depth==8 else ((alpha[i//2]>>((i%2)*4))&15)*17 if depth==4 else ((alpha[i//8]>>(i%8))&1)*255
   pixels[i*4:i*4+4]=bytes((r,g,b,a))
  return Image.frombytes('RGBA',(width,height),bytes(pixels))
 with Image.open(path) as im:
  if im.width>4096 or im.height>4096:raise ValueError('Texture exceeds preview bounds')
  return im.convert('RGBA')

def png(identity):
 record=manifest()['files'].get(identity)
 if not record or not record['path'].lower().endswith('.blp'):raise ValueError('Unknown texture')
 directory=BASE/'assets/png-v2';directory.mkdir(exist_ok=True)
 target=directory/(identity+'.png')
 with LOCK:
  if not target.exists():decode_texture(extract(identity)).save(target)
 return target
