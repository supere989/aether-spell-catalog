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
 def test_uncompressed_bgra(self):
  # BLP2 compression 3 (raw BGRA, 8-bit alpha): 3 shipped weapon textures use it (ledgered as "Unknown BLP encoding 3" until 2026-10-15)
  raw=bytearray(1172);raw[:4]=b'BLP2';raw[4:8]=b'\1\0\0\0';raw[8]=3;raw[9]=8;raw[10]=8;struct.pack_into('<II',raw,12,2,1);struct.pack_into('<I',raw,20,1172);struct.pack_into('<I',raw,84,8)
  raw.extend(bytes([30,20,10,200, 3,2,1,255]))
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'raw.blp';p.write_bytes(raw);im=decode_texture(p)
   self.assertEqual(im.size,(2,1));self.assertEqual(im.getpixel((0,0)),(10,20,30,200));self.assertEqual(im.getpixel((1,0)),(1,2,3,255))
 def test_uncompressed_bgra_truncated(self):
  raw=bytearray(1172);raw[:4]=b'BLP2';raw[8]=3;raw[9]=8;struct.pack_into('<II',raw,12,2,1);struct.pack_into('<I',raw,20,1172);raw.extend(b'\0'*4)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'short.blp';p.write_bytes(raw)
   with self.assertRaises(ValueError):decode_texture(p)

