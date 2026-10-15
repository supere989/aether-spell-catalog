"""Evaluate the first embedded standing frame in native M2 coordinates."""
import numpy as np

def translate(v):
 m=np.eye(4);m[:3,3]=v;return m

def first(track,sequence,default):
 index=0 if track.global_sequence>=0 else sequence
 return track.values[index][0] if index<len(track.values) and len(track.values[index]) else default

def rotation(q):
 if q is None:return np.eye(4)
 # pywowlib's reader swaps/negates XY for Blender; vertices are still native.
 raw=(q.y,-q.x,q.z,q.w)
 x,y,z,w=[(v+32768 if v<0 else v-32767)/32767 for v in raw]
 norm=(x*x+y*y+z*z+w*w)**.5
 if norm<1e-10:return np.eye(4)
 x,y,z,w=[v/norm for v in (x,y,z,w)]
 m=np.eye(4);m[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]];return m

def pose(root):
 sequence=next((i for i,s in enumerate(root.sequences) if s.id==0 and s.flags&32),0)
 matrices={};active=set()
 def bone(i):
  if i in matrices:return matrices[i]
  if i in active:raise ValueError('Cyclic skeleton')
  active.add(i);b=root.bones[i];scale=np.eye(4);scale[:3,:3]=np.diag(first(b.scale,sequence,(1,1,1)))
  local=translate(b.pivot)@translate(first(b.translation,sequence,(0,0,0)))@rotation(first(b.rotation,sequence,None))@scale@translate(-np.array(b.pivot))
  result=(bone(b.parent_bone)@local) if b.parent_bone>=0 else local
  active.remove(i);matrices[i]=result;return result
 for i in range(len(root.bones)):bone(i)
 positions=[];normals=[]
 for v in root.vertices:
  weights=[(idx,w) for idx,w in zip(v.bone_indices,v.bone_weights) if w and idx<len(root.bones)];total=sum(w for _,w in weights)
  transform=sum((matrices[i]*w/total for i,w in weights),np.zeros((4,4))) if total else np.eye(4)
  positions.extend((transform@np.array([*v.pos,1]))[:3]);normal=np.linalg.pinv(transform[:3,:3]).T@np.array(v.normal);length=np.linalg.norm(normal);normals.extend(normal/length if length else normal)
 mounts={str(a.id):(matrices[a.bone]@translate(a.position)).T.flatten().tolist() for a in root.attachments}
 return [round(float(x),6) for x in positions],[round(float(x),6) for x in normals],mounts
