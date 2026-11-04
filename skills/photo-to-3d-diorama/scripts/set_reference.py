"""Import a reference only AFTER the agent actually inspected it."""
import argparse,shutil
from pathlib import Path
from common import read,write,sha,inside

def set_reference(jobfile,asset_id,image,kind,note,reviewed=False):
    jp=Path(jobfile).resolve();j=read(jp);a=next(x for x in j['assets'] if x['id']==asset_id)
    if not reviewed: raise ValueError('Reference must be visually reviewed first')
    if kind=='original' and j['style']!='source': raise ValueError('Style-conditioned reference required')
    if j['input_mode']=='multiview' and kind!='generated_multiview_reference': raise ValueError('Multi-image-constrained reference required')
    src=Path(image).resolve(strict=True);rel=f'references/{asset_id}{src.suffix.lower()}';target=inside(jp.parent,rel);target.parent.mkdir(exist_ok=True)
    if target.exists() and sha(target)!=sha(src): raise FileExistsError('Use a new task for changed reference; existing reference locked')
    if src!=target:shutil.copy2(src,target)
    a['reference']={'path':rel,'sha256':sha(target),'kind':kind,'reviewed':True,'note':note}
    write(jp,j)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('job');p.add_argument('asset');p.add_argument('image');p.add_argument('--kind',required=True,choices=['original','generated_source_constrained','generated_scene_reference','generated_multiview_reference']);p.add_argument('--note',required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args();set_reference(a.job,a.asset,a.image,a.kind,a.note,a.reviewed)
