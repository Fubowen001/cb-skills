"""Create immutable source copies. Multiple inputs stay separate by default."""
import argparse, shutil
from pathlib import Path
from common import sha,write

def prepare(out,images,style='source',instruction='',custom_style='',scope='scene',subject_instruction=''):
    if not images: raise ValueError('At least one image required')
    if scope not in ('scene','subject'):raise ValueError('Invalid scope')
    if scope=='subject' and not subject_instruction.strip():raise ValueError('Isolated subject requires explicit --subject-instruction')
    if style=='custom' and not custom_style.strip(): raise ValueError('Specify --custom-style')
    paths=[Path(p).resolve(strict=True) for p in images]
    for p in paths:
        if p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'): raise ValueError('Unsupported image: '+p.name)
    out=Path(out).resolve(); out.mkdir(parents=True,exist_ok=False); (out/'inputs').mkdir()
    sources=[]
    for i,p in enumerate(paths,1):
        rel=f'inputs/{i:03d}{p.suffix.lower()}'; shutil.copy2(p,out/rel)
        sources.append({'path':rel,'sha256':sha(out/rel),'original_name':p.name})
    groups=[sources] if instruction.strip() else [[s] for s in sources]
    assets=[]
    for i,g in enumerate(groups,1):
        assets.append({'id':f'asset-{i:03d}','sources':g,'inventory':{'observed':[],'inferred':[],'layout':''},'scene_contract':{'reviewed':False,'coverage':{},'required_elements':[]},'reference':{'path':g[0]['path'] if len(g)==1 else '', 'sha256':g[0]['sha256'] if len(g)==1 else '', 'kind':'original' if len(g)==1 else 'required','reviewed':False}})
    job={'schema':1,'scope':scope,'subject_instruction':subject_instruction,'input_mode':'multiview' if instruction.strip() else 'independent','multiview_instruction':instruction,'style':style,'custom_style':custom_style,'parameters':{'seed':42,'steps':20,'guidance':3.0,'gaussians':262144},'assets':assets}
    write(out/'job.json',job); return job
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--style',choices=['source','cartoon','pixar','ink','custom'],default='source');p.add_argument('--custom-style',default='');p.add_argument('--multiview-instruction',default='');p.add_argument('--scope',choices=['scene','subject'],default='scene');p.add_argument('--subject-instruction',default='');p.add_argument('images',nargs='+');a=p.parse_args()
    j=prepare(a.out,a.images,a.style,a.multiview_instruction,a.custom_style,a.scope,a.subject_instruction);print(f"Created {len(j['assets'])} independent output group(s): {Path(a.out).resolve()/'job.json'}")
