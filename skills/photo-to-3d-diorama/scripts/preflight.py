"""Report actual usable runtime, GPU and optional Blender."""
import subprocess,json,sys
from common import runtime,WEIGHTS
if __name__=='__main__':
    r=runtime();py=r/'python'/('python.exe' if sys.platform=='win32' else 'bin/python3')
    missing=[str(r/'weights'/w) for w in WEIGHTS if not (r/'weights'/w).is_file()]
    for p in [py,r/'source/triposplat.py',r/'source/model.py',r/'packages']:
        if not p.exists():missing.append(str(p))
    result={'runtime':str(r),'python':str(py),'missing':missing,'representation':'anisotropic Gaussian splats, not triangle mesh','native_multiview':False,'text_conditioning':False}
    if not missing:
        code="import sys,json;sys.path[:0]="+repr([str(r/'packages'),str(r/'source')])+";import torch,torchvision,numpy,PIL,safetensors,tqdm,triposplat;print(json.dumps({'torch':torch.__version__,'cuda':torch.cuda.is_available(),'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'free_vram':torch.cuda.mem_get_info()[0] if torch.cuda.is_available() else 0}))"
        proc=subprocess.run([str(py),'-c',code],capture_output=True,text=True)
        if proc.returncode:result['error']=proc.stderr[-2000:]
        else:result['gpu']=json.loads(proc.stdout.strip().splitlines()[-1])
    result['blender']=str(r/'blender/blender.exe') if (r/'blender/blender.exe').exists() else None
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(1 if missing or 'error' in result or not result.get('gpu',{}).get('cuda') else 0)
