import unittest,json,math
from pathlib import Path
from types import SimpleNamespace as S
import numpy as np
from model_pose import pose,rotation

def track(value):return S(global_sequence=-1,values=[] if value is None else [[value]])
class PoseTests(unittest.TestCase):
 def test_mesh_and_mount_share_hierarchical_transform(self):
  bone=lambda parent,t,s:S(parent_bone=parent,pivot=(0,0,0),translation=track(t),rotation=track(None),scale=track(s))
  root=S(sequences=[S(id=0,flags=32)],bones=[bone(-1,(3,0,0),(.5,.5,.5)),bone(0,None,None)],vertices=[S(pos=(1,0,0),normal=(0,0,1),bone_indices=[1],bone_weights=[255])],attachments=[S(id=11,bone=1,position=(1,0,0))])
  positions,normals,mounts=pose(root);self.assertEqual(positions,[3.5,0,0]);self.assertEqual(normals,[0,0,1]);self.assertEqual(mounts['11'][12:15],positions)
 def test_native_quaternion_axes(self):
  q=S(x=-32767,y=32767,z=-9598,w=-9598);v=rotation(q)@np.array([1,0,0,1]);self.assertAlmostEqual(v[0],0,places=3);self.assertAlmostEqual(v[1],1,places=3)
 def test_exported_mounts_are_finite(self):
  b=Path(__file__).parent/'assets/models'
  for p in b.glob('*.json'):
   d=json.loads(p.read_text());self.assertEqual(d['pose'],'standing-first-frame')
   for matrix in d['attachment_matrices'].values():self.assertEqual(len(matrix),16);self.assertTrue(all(math.isfinite(x) for x in matrix))
