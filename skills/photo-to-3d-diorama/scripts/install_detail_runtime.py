"""Install an existing local MediaPipe/SciPy/OpenCV environment; no uploads."""
import argparse,json
from pathlib import Path
from common import runtime,write,sha
from install_runtime import transfer
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--packages',required=True);p.add_argument('--models',required=True);p.add_argument('--destination');a=p.parse_args();dest=Path(a.destination).resolve() if a.destination else runtime()/'detail';stats={'linked':0,'copied':0,'existing':0}
    transfer(Path(a.packages),dest/'packages',stats)
    for name in ['face_landmarker.task','hand_landmarker.task']:transfer(Path(a.models)/name,dest/'models'/name,stats)
    write(dest/'installation.json',{'schema':1,'models':{name:sha(dest/'models'/name) for name in ['face_landmarker.task','hand_landmarker.task']},'source':'Google official MediaPipe model bundles; local CPU inference','statistics':stats});print(json.dumps({'destination':str(dest),**stats}))
