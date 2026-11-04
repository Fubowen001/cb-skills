import sys,unittest,tempfile,struct,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import activate,sha,read,write,validate_asset
activate()
from prepare_job import prepare
from set_reference import set_reference
from gaussian_io import pack,load_ply,NAMES
from make_preview import make_preview
from audit_asset import audit
from PIL import Image
import numpy as np
class Contracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP'));self.root=Path(self.tmp.name);self.img=self.root/'white.png';Image.new('RGBA',(16,16),(255,255,255,255)).save(self.img)
 def tearDown(self):self.tmp.cleanup()
 def test_independent_and_immutable(self):
  out=self.root/'job';j=prepare(out,[self.img,self.img],'ink');self.assertEqual(len(j['assets']),2);self.assertEqual(j['input_mode'],'independent');self.assertEqual(sha(out/j['assets'][0]['sources'][0]['path']),sha(self.img));self.assertEqual(Image.open(out/'inputs/001.png').getpixel((0,0)),(255,255,255,255))
  with self.assertRaises(FileExistsError):prepare(out,[self.img])
 def test_group_requires_explicit_reference(self):
  out=self.root/'job';j=prepare(out,[self.img,self.img],instruction='这两张是同一个物体的前后视角，合成一个',scope='subject',subject_instruction='测试只生成白色物体');self.assertEqual(len(j['assets']),1)
  with self.assertRaises(ValueError):set_reference(out/'job.json','asset-001',self.img,'original','not multiview',True)
  set_reference(out/'job.json','asset-001',self.img,'generated_multiview_reference','Both views constrained reference',True);j=read(out/'job.json');j['assets'][0]['inventory']['observed']=['white test object'];validate_asset(j,j['assets'][0],out)
 def test_style_and_hash_guards(self):
  out=self.root/'job';j=prepare(out,[self.img],'ink',scope='subject',subject_instruction='只生成单件');a=j['assets'][0];a['reference']['reviewed']=True;a['inventory']['observed']=['white object']
  with self.assertRaises(ValueError):validate_asset(j,a,out)
  set_reference(out/'job.json','asset-001',self.img,'generated_source_constrained','inspected reference',True);j=read(out/'job.json');j['assets'][0]['inventory']['observed']=['white object'];validate_asset(j,j['assets'][0],out)
  (out/'inputs/001.png').write_bytes(b'changed')
  with self.assertRaises(ValueError):validate_asset(j,j['assets'][0],out)
 def test_scene_default_cannot_accept_subject_only_reference(self):
  out=self.root/'scene';j=prepare(out,[self.img]);self.assertEqual(j['scope'],'scene');a=j['assets'][0];a['inventory']['observed']=['people and room'];a['reference']['reviewed']=True
  with self.assertRaises(ValueError):validate_asset(j,a,out)
  a['scene_contract']={'reviewed':True,'coverage':{'subjects':True,'ground':False,'setting':False},'required_elements':['room'],'subject_count':8,'reference_subject_count':8}
  with self.assertRaises(ValueError):validate_asset(j,a,out)
 def test_subject_mode_needs_user_instruction(self):
  with self.assertRaises(ValueError):prepare(self.root/'bad',[self.img],scope='subject')
 def test_scene_count_and_exterior_alpha(self):
  out=self.root/'scene';j=prepare(out,[self.img]);a=j['assets'][0];a['inventory']['observed']=['8 people and a room'];a['scene_contract']={'reviewed':True,'coverage':{'subjects':True,'ground':True,'setting':True},'required_elements':['people','floor','walls'],'subject_count':8,'reference_subject_count':7};a['reference'].update(kind='generated_scene_reference',reviewed=True)
  with self.assertRaises(ValueError):validate_asset(j,a,out)
  a['scene_contract']['reference_subject_count']=8
  with self.assertRaises(ValueError):validate_asset(j,a,out)
  ref=Image.new('RGBA',(16,16),(255,255,255,255));ref.putpixel((0,0),(0,0,0,0));ref.save(out/'inputs/001.png');a['sources'][0]['sha256']=sha(out/'inputs/001.png');a['reference']['sha256']=a['sources'][0]['sha256'];validate_asset(j,a,out)
 def test_targeted_repair_preserves_original_and_adds_closed_mesh(self):
  from complete_structure import complete
  path,v,h=self.ply();pack(path/'model.ply',path/'model.splat');make_preview(path);write(path/'record.json',{'count':3,'outputs':{n:sha(path/n) for n in ['model.ply','model.splat','preview.html']}});write(path/'scene.json',{'components':[{'file':'model.ply'}]});write(path/'review.json',{'status':'needs_visual_review'})
  spec=self.root/'repair.json';write(spec,{'primitives':[{'id':'floor','type':'box','min':[-.2,-.2,-.2],'max':[.2,-.1,.2],'color':[.4,.3,.2],'spacing':.05,'source_constraint':'Visible ground in test','reason':'Explicit missing underside'}]});original=sha(path/'model.ply');result=complete(path,spec,self.root/'backup');self.assertGreater(result['count'],3);self.assertEqual(sha(self.root/'backup/model.ply'),original);mesh=read(path/'structure.json')['repairs'][0];edges={}
  for face in mesh['faces']:
   for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted([a,b]))]=edges.get(tuple(sorted([a,b])),0)+1
  self.assertTrue(all(v==2 for v in edges.values()));self.assertEqual(audit(path)['structural_status'],'pass');self.assertEqual(complete(path,spec,self.root/'unused')['status'],'already_applied')
 def test_approved_asset_repair_is_blocked(self):
  from complete_structure import complete
  path,v,h=self.ply();write(path/'review.json',{'status':'approved'});spec=self.root/'repair.json';write(spec,{'primitives':[]});original=sha(path/'model.ply')
  with self.assertRaises(ValueError):complete(path,spec,self.root/'backup')
  self.assertEqual(sha(path/'model.ply'),original);self.assertFalse((self.root/'backup').exists())
 def ply(self):
  names=['nz']+list(reversed(NAMES))+['nx','ny'];dt=np.dtype([(n,'<f4') for n in names]);v=np.zeros(3,dtype=dt);v['x']=[-1,0,1];v['y']=[0,1,0];v['z']=[.2,0,.5];v['opacity']=[-np.inf,0,np.inf];v['rot_0']=2
  for k in range(3):v['scale_'+str(k)]=np.log(.01*(k+1))
  path=self.root/'asset';path.mkdir();header='ply\nformat binary_little_endian 1.0\nelement vertex 3\n'+''.join('property float '+n+'\n' for n in names)+'end_header\n';(path/'model.ply').write_bytes(header.encode()+v.tobytes());return path,v,header
 def test_ply_property_order_and_real_preview(self):
  path,v,h=self.ply();self.assertEqual(pack(path/'model.ply',path/'model.splat'),3);raw=(path/'model.splat').read_bytes();self.assertEqual(len(raw),96);self.assertAlmostEqual(struct.unpack_from('<f',raw,12)[0],.01,places=6);self.assertEqual(raw[27],0);self.assertEqual(raw[91],255);self.assertEqual(raw[28],255);make_preview(path,self.img);r=audit(path);self.assertEqual(r['structural_status'],'pass');self.assertEqual(r['visual_status'],'needs_visual_review');text=(path/'preview.html').read_text(encoding='utf8');self.assertNotIn('@@',text);self.assertIn('InstancedBufferGeometry',text);self.assertNotIn('src="https://',text)
 def test_invalid_gaussians_rejected(self):
  path,v,h=self.ply();v['x'][1]=np.nan;(path/'model.ply').write_bytes(h.encode()+v.tobytes())
  with self.assertRaises(ValueError):load_ply(path/'model.ply')
if __name__=='__main__':unittest.main(verbosity=2)
