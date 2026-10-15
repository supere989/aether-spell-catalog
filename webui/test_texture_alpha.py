import unittest,struct,tempfile,importlib.util
from pathlib import Path
from asset_io import decode_texture
@unittest.skipUnless(importlib.util.find_spec('PIL'),'Pillow required for asset conversion')
class TextureAlphaTests(unittest.TestCase):
 def test_separate_alpha_plane(self):
  for depth,alpha,expected in [(0,b'',[255,255]),(1,b'\x02',[0,255]),(4,b'\xf2',[34,255]),(8,b'\x20\xe0',[32,224])]:
   raw=bytearray(1172);raw[:4]=b'BLP2';raw[8]=1;raw[9]=depth;struct.pack_into('<II',raw,12,2,1);struct.pack_into('<I',raw,20,1172);raw[148:152]=bytes([30,20,10,0]);raw.extend(b'\0\0'+alpha)
   with tempfile.TemporaryDirectory() as folder:
    p=Path(folder)/'sample.blp';p.write_bytes(raw);im=decode_texture(p);self.assertEqual(list(im.getchannel('A').getdata()),expected);self.assertEqual(im.getpixel((0,0))[:3],(10,20,30))
