"""File/geometry diagnostics only. Does NOT approve visual quality."""
import argparse
from pathlib import Path
from common import read,write,sha
from gaussian_io import load_ply
import numpy as np

def audit(asset):
    a=Path(asset);v=load_ply(a/'model.ply');p=a/'model.splat';raw=p.read_bytes()
    if len(raw)!=len(v)*32:raise ValueError('SPLAT record count mismatch')
    pos=np.frombuffer(raw,dtype=np.dtype([('xyz','<f4',3),('rest','u1',20)]))['xyz']
    if not np.array_equal(pos,v[:,:3]):raise ValueError('PLY/SPLAT positions differ')
    if (a/'record.json').exists():
        rec=read(a/'record.json')
        for name,h in rec.get('outputs',{}).items():
            if sha(a/name)!=h:raise ValueError('Output hash mismatch: '+name)
    extent=np.ptp(v[:,:3],axis=0);sv=np.linalg.svd(v[:,:3]-v[:,:3].mean(0),compute_uv=False)
    report={'structural_status':'pass','visual_status':'needs_visual_review','count':len(v),'bbox_extent':extent.tolist(),'principal_axis_ratio':(sv/(sv.max() or 1)).tolist(),'note':'Thin ratio is a diagnostic, not a visual verdict; inspect all views.','files':{x:sha(a/x) for x in ['model.ply','model.splat','preview.html']}}
    write(a/'audit.json',report);return report
if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('asset');a=p.parse_args();print(json.dumps(audit(a.asset),ensure_ascii=False,indent=2))
