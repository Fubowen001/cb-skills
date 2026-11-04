"""Source-locked local single-image TripoSplat batch runner (staged CUDA)."""
import argparse,sys,gc,time,hashlib,json,re,traceback
from pathlib import Path
from common import activate,read,write,sha,inside,validate_asset,WEIGHTS,ROOT
r=activate()

def run(jobfile):
    jp=Path(jobfile).resolve();base=jp.parent;j=read(jp);params=j['parameters']
    if j.get('schema')!=1 or j['input_mode'] not in ('independent','multiview'):raise ValueError('Unsupported job schema/mode')
    if j['input_mode']=='independent' and any(len(a['sources'])!=1 for a in j['assets']):raise ValueError('Independent photos cannot be merged')
    if not 1<=int(params['steps'])<=100 or not 1024<=int(params['gaussians'])<=262144:raise ValueError('Out of bounds inference budget')
    ids=[a['id'] for a in j['assets']]
    if len(set(ids))!=len(ids) or any(not re.fullmatch(r'asset-[0-9]{3,}',i) for i in ids):raise ValueError('Invalid/duplicate asset ID')
    preview_engine_version=sha(ROOT/'assets/viewer.js')+sha(ROOT/'scripts/make_preview.py')+sha(ROOT/'scripts/scene_manifest.py')
    pending=[];summary=[]
    for a in j['assets']:
        preview_version=preview_engine_version+hashlib.sha256(json.dumps(a.get('environment',{}),sort_keys=True).encode()).hexdigest()
        try:
            ref=validate_asset(j,a,base)
            signature={'schema':1,'source_hashes':[s['sha256'] for s in a['sources']],'reference_sha256':sha(ref),'reference_kind':a['reference']['kind'],'inventory':a['inventory'],'scope':j.get('scope','scene'),'scene_contract':a.get('scene_contract',{}),'style':j['style'],'custom_style':j.get('custom_style',''),'parameters':params,'pipeline':'TripoSplat-single-image-default-ply-v2','code':{name:sha(r/'source'/name) for name in ['triposplat.py','model.py']},'weights':read(r/'installation.json')['weights']}
            digest=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            dest=base/'assets'/a['id']/(j['style']+'-'+digest[:12]);recfile=dest/'record.json'
            if recfile.exists():
                rec=read(recfile)
                if rec.get('signature')!=signature:raise ValueError('Existing asset signature conflict')
                if all((dest/f).exists() and sha(dest/f)==h for f,h in rec['outputs'].items()):
                    if rec.get('preview_version')!=preview_version or not (dest/'scene.json').exists():
                        from scene_manifest import make_scene
                        make_scene(dest,j,a);rec['outputs']['scene.json']=sha(dest/'scene.json')
                        from make_preview import make_preview
                        make_preview(dest,inside(base,a['sources'][0]['path']));rec['outputs']['preview.html']=sha(dest/'preview.html');rec['preview_version']=preview_version;write(recfile,rec)
                    summary.append({'id':a['id'],'status':'cached','asset':dest.relative_to(base).as_posix()});continue
                raise ValueError('Existing output modified; preserved instead of overwritten')
            if dest.exists() and any(dest.iterdir()):raise FileExistsError('Partial output preserved; move it aside before retry')
            pending.append((a,ref,signature,dest,preview_version))
        except Exception as e:summary.append({'id':a['id'],'status':'failed_validation','error':str(e)})
    if pending:
        import torch
        from triposplat import TripoSplatPipeline
        from gaussian_io import pack
        from make_preview import make_preview
        from audit_asset import audit
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; run preflight.py')
        torch.set_num_threads(12);torch.backends.cuda.matmul.allow_tf32=True
        w=r/'weights';print('Loading official local pipeline',flush=True)
        pipe=TripoSplatPipeline(ckpt_path=str(w/WEIGHTS[0]),decoder_path=str(w/WEIGHTS[1]),dinov3_path=str(w/WEIGHTS[2]),flux2_vae_encoder_path=str(w/WEIGHTS[3]),rmbg_path=str(w/WEIGHTS[4]),device='cpu');pipe._device=torch.device('cuda')
        def offload(module):module.to('cpu');gc.collect();torch.cuda.empty_cache()
        for a,ref,signature,dest,preview_version in pending:
            dest.mkdir(parents=True,exist_ok=True);start=time.monotonic();print('GENERATING '+a['id'],flush=True)
            try:
                with torch.inference_mode():
                    print('PREPROCESS CUDA',flush=True);pipe.rmbg.to('cuda')
                    prepared=pipe.preprocess_image(str(ref),erode_radius=0);offload(pipe.rmbg);prepared.save(dest/'prepared.png')
                    gen=torch.Generator(device='cuda').manual_seed(int(params['seed']))
                    print('ENCODE CUDA',flush=True);pipe.dinov3.to('cuda');pipe.vae_encoder.to('cuda');cond=pipe.encode_image(prepared,generator=gen)
                    offload(pipe.dinov3);offload(pipe.vae_encoder)
                    print('DENOISE CUDA',flush=True);pipe.flow_model.to('cuda');latent=pipe.sample_latent(cond,steps=int(params['steps']),guidance_scale=float(params['guidance']),generator=gen,show_progress=True);offload(pipe.flow_model);del cond
                    print('DECODE CUDA',flush=True);pipe.decoder.to('cuda');gaussian=pipe.decode_latent(latent['latent'],num_gaussians=int(params['gaussians']));offload(pipe.decoder);del latent
                    gaussian.save_ply(str(dest/'model.ply'))
                    del gaussian,prepared;gc.collect();torch.cuda.empty_cache()
                from scene_manifest import make_scene
                make_scene(dest,j,a)
                count=pack(dest/'model.ply',dest/'model.splat');make_preview(dest,inside(base,a['sources'][0]['path']))
                rec={'schema':1,'preview_version':preview_version,'generator':'Official TripoSplat local staged CUDA','signature':signature,'count':count,'seconds':time.monotonic()-start,'device':torch.cuda.get_device_name(0),'coordinate_system':'official default PLY transform; viewer=(x,-y,-z), front +X','representation':'anisotropic 3D Gaussians, not triangle mesh','method':'multi-image constrained reference then single-image reconstruction' if j['input_mode']=='multiview' else 'single-image reconstruction','sources':a['sources'],'reference':a['reference'],'inventory':a['inventory'],'scene_contract':a.get('scene_contract',{}),'outputs':{name:sha(dest/name) for name in ['model.ply','model.splat','preview.html','prepared.png','scene.json']}}
                write(dest/'record.json',rec);write(dest/'review.json',{'status':'needs_visual_review','views':[],'source_fidelity':None,'style':None,'volume':None,'issues':[],'inferred':a['inventory'].get('inferred',[])})
                audit(dest);summary.append({'id':a['id'],'status':'generated_needs_visual_review','asset':dest.relative_to(base).as_posix()});print('DONE '+a['id'],flush=True)
            except Exception as e:
                summary.append({'id':a['id'],'status':'failed','error':str(e)});write(dest/'failure.json',{'error':str(e),'signature':signature});traceback.print_exc()
                for module in [pipe.rmbg,pipe.dinov3,pipe.vae_encoder,pipe.flow_model,pipe.decoder]:offload(module)
                if isinstance(e,torch.cuda.OutOfMemoryError):break
    write(base/'batch.json',{'schema':1,'input_mode':j['input_mode'],'style':j['style'],'results':summary})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 1 if any(s['status'].startswith('failed') for s in summary) or len(summary)!=len(j['assets']) else 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('job');a=p.parse_args();sys.exit(run(a.job))
