"""Portable job and runtime utilities; no credentials or network access."""
import os, sys, json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ['diffusion_models/triposplat_fp16.safetensors','vae/triposplat_vae_decoder_fp16.safetensors','clip_vision/dino_v3_vit_h.safetensors','vae/flux2-vae.safetensors','background_removal/birefnet.safetensors']
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p, obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8'); tmp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def runtime():
    conf=ROOT/'runtime.local.json'
    path=os.environ.get('PHOTO3D_RUNTIME') or (read(conf)['runtime'] if conf.exists() else str(Path.home()/'.codex/cache/photo-to-3d-diorama/v1'))
    return Path(path).resolve()
def activate():
    r=runtime()
    sys.path.insert(0,str(r/'packages')); sys.path.insert(0,str(r/'source'))
    return r
def inside(base, relative):
    base=Path(base).resolve(); p=(base/relative).resolve()
    if not p.is_relative_to(base): raise ValueError('Path leaves job directory: '+str(relative))
    return p
def validate_asset(job, a, base):
    if len(a['sources'])!=1 and (job['input_mode']!='multiview' or not job.get('multiview_instruction','').strip()):
        raise ValueError('Multiple photos require explicit grouping instruction')
    for src in a['sources']:
        if sha(inside(base,src['path']))!=src['sha256']: raise ValueError('Original input changed')
    ref=a['reference']; p=inside(base,ref['path'])
    if ref.get('reviewed') is not True or not a.get('inventory',{}).get('observed'): raise ValueError('Inspect reference and fill observed inventory before inference')
    if sha(p)!=ref.get('sha256'): raise ValueError('Reference missing or changed hash; import with set_reference.py')
    if job['input_mode']=='multiview' and ref['kind']!='generated_multiview_reference': raise ValueError('This backend needs a reviewed multi-image-constrained reference, not just first image')
    if job['style']!='source' and ref['kind']=='original': raise ValueError('Style requires a style-conditioned reference; TripoSplat does not accept style prompts')
    scope=job.get('scope','scene')
    if scope=='subject' and not job.get('subject_instruction','').strip():raise ValueError('Subject-only requires explicit user instruction')
    if scope=='scene':
        c=a.get('scene_contract',{})
        if c.get('reviewed') is not True or not c.get('required_elements'):raise ValueError('Complete-scene element coverage must be reviewed')
        if not all(c.get('coverage',{}).get(k) is True for k in ['subjects','ground','setting']):raise ValueError('Scene must retain subjects, supporting ground and spatial setting')
        if not isinstance(c.get('subject_count'),int) or c['subject_count']<0:raise ValueError('Explicit nonnegative source subject count required')
        if c.get('subject_count')!=c.get('reference_subject_count'):raise ValueError('Reference changed source subject count')
        if ref['kind'] not in ('generated_scene_reference','generated_multiview_reference'):raise ValueError('Scene requires a reviewed whole-environment reference; no automatic subject cutout')
        from PIL import Image
        with Image.open(p) as im:
            if 'A' not in im.getbands() or im.getchannel('A').getextrema()[0]==255:raise ValueError('Whole-scene reference needs genuine exterior alpha; do not remove the environment with foreground matting')
    return p
