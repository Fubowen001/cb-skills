import unittest,tempfile,json,os
from pathlib import Path
import numpy as np
from refine_surfaces import Camera,similarity,splats_for_mesh
from PIL import Image
from audit_details import audit_details
from gaussian_io import NAMES

class FineDetails(unittest.TestCase):
 def test_camera_roundtrip(self):
  c=Camera([2,.2,0],[0,0,0],1200,800,40);p=np.array([[0,0,0],[.1,.2,.3],[-.2,.3,-.1]]);uv,d=c.project(p);np.testing.assert_allclose(c.unproject(uv,d),p,atol=1e-12)
 def test_similarity_preserves_correspondence(self):
  p=np.array([[0,0],[1,0],[0,1],[2,3.]]);q=p@np.array([[0.,2.],[-2.,0.]])+[10,20];m,t=similarity(p,q);np.testing.assert_allclose(p@m+t,q,atol=1e-12)
 def test_surface_samples_have_true_depth(self):
  v=np.array([[0,0,0],[.1,0,.01],[0,.1,-.02]]);uv=np.array([[0,0],[1,0],[0,1]]);s=splats_for_mesh(v,[[0,1,2]],uv,Image.new('RGB',(8,8),(120,80,60)));self.assertGreater(len(s),10);self.assertTrue(np.isfinite(s).all());self.assertTrue((np.exp(s[:,7:10])>0).all());self.assertGreater(np.ptp(s[:,2]),.02)
 def make_asset(self,root,flat=False):
  verts=[[0,0,0],[1,0,0],[0,1,0],[.2,.2,0 if flat else .2]];m={'id':'face-01','kind':'source_landmark_curved_face','vertices_runtime':verts,'faces':[[0,1,3],[1,2,3]],'uv':[[0,0],[1,0],[0,1],[.2,.2]],'texture':'source.jpg'};d={'original_source_sha256':'test','meshes':[m]};(root/'details.json').write_text(json.dumps(d));(root/'source.jpg').write_bytes(b'test');a=np.zeros(1,dtype=[(n,'<f4') for n in NAMES]);a[NAMES[10]]=1;header='ply\nformat binary_little_endian 1.0\nelement vertex 1\n'+''.join('property float '+n+'\n' for n in NAMES)+'end_header\n';(root/'model.ply').write_bytes(header.encode()+a.tobytes())
 def test_audit_rejects_planar_face(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP')) as t:
   p=Path(t);self.make_asset(p,True)
   with self.assertRaisesRegex(ValueError,'planar'):audit_details(p,{'faces':1,'hands':0,'texts':[]})
 def test_audit_rejects_missing_person(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP')) as t:
   p=Path(t);self.make_asset(p)
   with self.assertRaisesRegex(ValueError,'Missing'):audit_details(p,{'faces':2,'hands':0,'texts':[]})
 def test_audit_does_not_auto_approve(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP')) as t:
   p=Path(t);self.make_asset(p);r=audit_details(p,{'faces':1,'hands':0,'texts':[]});self.assertEqual(r['structural_status'],'pass');self.assertIn('needs_',r['visual_status'])
if __name__=='__main__':unittest.main()
