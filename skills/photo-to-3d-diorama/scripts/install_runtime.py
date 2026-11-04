"""Migrate an existing licensed local runtime; no downloads, junctions or tokens."""
import argparse,os,shutil,json
from pathlib import Path
from common import WEIGHTS,write,sha

def transfer(src,dst,stats):
    src=Path(src).resolve(strict=True);dst=Path(dst).resolve()
    if src==dst or src.is_relative_to(dst) or dst.is_relative_to(src):raise ValueError('Source/target overlap')
    files=src.rglob('*') if src.is_dir() else [src]
    for f in files:
        if not f.is_file() or '__pycache__' in f.parts or f.suffix=='.pyc':continue
        target=dst/f.relative_to(src) if src.is_dir() else dst
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if os.path.samefile(f,target):stats['existing']+=1;continue
            if target.stat().st_size!=f.stat().st_size or sha(target)!=sha(f):raise FileExistsError('Conflicting runtime file: '+str(target))
            stats['existing']+=1;continue
        try:os.link(f,target);stats['linked']+=1
        except OSError:shutil.copy2(f,target);stats['copied']+=1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python-root',required=True);p.add_argument('--packages',required=True);p.add_argument('--source',required=True);p.add_argument('--weights',required=True);p.add_argument('--blender-root');p.add_argument('--cache-root',required=True);a=p.parse_args();r=Path(a.cache_root).resolve();stats={'linked':0,'copied':0,'existing':0}
    sources=[(Path(a.python_root),r/'python'),(Path(a.packages),r/'packages')]
    sources += [(Path(a.source)/name,r/'source'/name) for name in ['triposplat.py','model.py','LICENSE']]
    sources += [(Path(a.weights)/name,r/'weights'/name) for name in WEIGHTS]
    if a.blender_root:sources.append((Path(a.blender_root),r/'blender'))
    for s,_ in sources:
        if not s.exists():raise FileNotFoundError(s)
    for s,t in sources:transfer(s,t,stats)
    write(r/'installation.json',{'schema':1,'mode':'local files, hardlink or copy','statistics':stats,'weights':{name:sha(r/'weights'/name) for name in WEIGHTS}})
    print(json.dumps({'runtime':str(r),**stats}))
