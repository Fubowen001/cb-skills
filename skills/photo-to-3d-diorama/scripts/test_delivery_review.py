import unittest,tempfile,os,json,sys,types,contextlib
from pathlib import Path
from unittest import mock
from check_delivery_review import evaluate,sha,CHECKS

class DeliveryReview(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP'));self.root=Path(self.tmp.name)
  for n in ['candidate','reference','baseline','proof']:(self.root/n).write_bytes(n.encode())
  def lock(n):return {'path':n,'sha256':sha(self.root/n)}
  self.record={'candidate':lock('candidate'),'style_reference':lock('reference'),'baseline_locks':[lock('baseline')],'requested_representation':'mesh','actual_representation':'mesh','checks':{n:{'status':'pass','candidate_sha256':sha(self.root/'candidate'),'reviewer':'test reviewer','observation':'Test observation','evidence':[lock('proof')]} for n in CHECKS}}
 def tearDown(self):self.tmp.cleanup()
 def test_complete_record_allows_final(self):self.assertTrue(evaluate(self.record,self.root)['final_quality_approved'])
 def test_unobserved_view_blocks_final(self):
  self.record['checks']['multiview']={'status':'unreviewed'};self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_geometry_does_not_prove_likeness(self):
  self.record['checks']['reference_fidelity']={'status':'fail'};self.assertFalse(evaluate(self.record,self.root)['final_quality_approved'])
 def test_named_blend_cannot_substitute_for_mesh(self):
  self.record['actual_representation']='gaussian';self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_changed_baseline_is_detected(self):
  (self.root/'baseline').write_bytes(b'changed');self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_stale_evidence_is_detected(self):
  (self.root/'proof').write_bytes(b'changed');self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_explicit_component_review_is_not_final_approval(self):
  self.record.update(delivery_policy='review_requested',review_requested_by_user=True,user_instruction='Show the selected version by parts');self.record['checks']['assembly']={'status':'unreviewed'};r=evaluate(self.record,self.root);self.assertTrue(r['allowed_to_show']);self.assertFalse(r['final_quality_approved']);self.assertTrue(r['review_only'])
 def test_preview_exception_needs_actual_request(self):
  self.record.update(delivery_policy='review_requested');self.record['checks']['assembly']={'status':'fail'};self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_old_candidate_approval_cannot_be_reused(self):
  (self.root/'candidate').write_bytes(b'new candidate');self.record['candidate']['sha256']=sha(self.root/'candidate');self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_core_visual_checks_cannot_be_skipped(self):
  for n in CHECKS:self.record['checks'][n]={'status':'not_applicable','reason':'Skip'}
  self.assertFalse(evaluate(self.record,self.root)['allowed_to_show'])
 def test_batch_generation_keeps_both_records(self):
  # Exercise the actual batch runner with a synthetic backend; no GPU, remote calls or real generation.
  from prepare_job import prepare
  from common import write,read
  from gaussian_io import NAMES,np
  from PIL import Image
  import run_job
  image=self.root/'input.png';Image.new('RGBA',(16,16),(220,180,120,255)).save(image);jobdir=self.root/'job';j=prepare(jobdir,[image,image],scope='subject',subject_instruction='Test isolated props only')
  for a in j['assets']:a['reference']['reviewed']=True;a['inventory']['observed']=['test prop']
  write(jobdir/'job.json',j)
  class Gaussian:
   def save_ply(self,p):
    v=np.zeros(3,dtype=[(n,'<f4') for n in NAMES]);v['x']=[0,.1,0];v['y']=[0,0,.1];v['z']=[0,.02,.03];v['rot_0']=1;v['opacity']=3
    for n in ['scale_0','scale_1','scale_2']:v[n]=-5
    h='ply\nformat binary_little_endian 1.0\nelement vertex 3\n'+''.join('property float '+n+'\n' for n in NAMES)+'end_header\n';Path(p).write_bytes(h.encode()+v.tobytes())
  class Pipeline:
   def __init__(self,**kw):
    for n in ['rmbg','dinov3','vae_encoder','flow_model','decoder']:setattr(self,n,mock.MagicMock())
   def preprocess_image(self,p,**kw):return Image.open(p).copy()
   def encode_image(self,*a,**kw):return {}
   def sample_latent(self,*a,**kw):return {'latent':0}
   def decode_latent(self,*a,**kw):return Gaussian()
  torch=mock.MagicMock();torch.inference_mode=contextlib.nullcontext;torch.cuda.is_available.return_value=True;torch.cuda.get_device_name.return_value='SYNTHETIC_TEST_BACKEND';torch.cuda.OutOfMemoryError=RuntimeError
  fixture=self.root/'fake-runtime';(fixture/'source').mkdir(parents=True);(fixture/'source/triposplat.py').write_text('# Synthetic backend fixture');(fixture/'source/model.py').write_text('# Synthetic model fixture');write(fixture/'installation.json',{'weights':{'fixture':'test-only'}})
  with mock.patch.object(run_job,'r',fixture),mock.patch.dict(sys.modules,{'torch':torch,'triposplat':types.SimpleNamespace(TripoSplatPipeline=Pipeline)}):self.assertEqual(run_job.run(jobdir/'job.json'),0)
  results=read(jobdir/'batch.json')['results'];self.assertEqual(len(results),2)
  for item in results:
   rec=read(jobdir/item['asset']/'record.json');self.assertEqual(rec['sources'][0]['path'],'inputs/'+('001' if item['id']=='asset-001' else '002')+'.png');self.assertEqual(rec['count'],3)
if __name__=='__main__':unittest.main()
