"""Self-contained interactive anisotropic Gaussian preview, no external URLs."""
import base64,html,mimetypes,json
from pathlib import Path
from common import ROOT

def make_preview(asset,source=None):
    asset=Path(asset);data=base64.b64encode((asset/'model.splat').read_bytes()).decode('ascii')
    vendor=''.join('<script>'+ (ROOT/'assets'/name).read_text(encoding='utf8').replace('</script','<\\/script')+'</script>' for name in ['three.min.js','OrbitControls.js'])
    image=''
    if source:
        source=Path(source);mime=mimetypes.guess_type(source.name)[0] or 'image/png'
        image='<details><summary>原图对照</summary><img alt="原图" src="data:'+mime+';base64,'+base64.b64encode(source.read_bytes()).decode('ascii')+'"></details>'
    focuses=[]
    if (asset/'details.json').exists():
        import math
        detail=json.loads((asset/'details.json').read_text(encoding='utf8'))
        for mesh in detail.get('meshes',[]):
            verts=mesh['vertices_runtime'];lo=[min(v[k] for v in verts) for k in range(3)];hi=[max(v[k] for v in verts) for k in range(3)];kind=mesh['kind'];label=('人物'+str(mesh.get('source_face_index',0)+1)+' · 面部') if 'face' in kind else ('手部'+str(mesh.get('source_hand_index',0)+1)) if 'hand' in kind else ('文字：'+mesh.get('text','').replace('\n',' '))
            source_box=None
            if mesh.get('uv'):source_box=[min(uv[0] for uv in mesh['uv']),min(uv[1] for uv in mesh['uv']),max(uv[0] for uv in mesh['uv']),max(uv[1] for uv in mesh['uv'])]
            focuses.append({'id':mesh['id'],'label':label,'center':[(lo[k]+hi[k])*.5 for k in range(3)],'span':max(hi[k]-lo[k] for k in range(3)),'source_box':source_box,'source_text':mesh.get('text')})
    template='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>3D微观模型 · 核验预览</title><style>body{margin:0;background:#eeeae0;color:#302f29;font:15px system-ui}canvas{width:100vw;height:100vh;display:block;touch-action:none}header{position:fixed;top:18px;left:20px;z-index:2}h1{font-size:20px;margin:0 0 8px}nav{position:fixed;bottom:18px;left:18px;right:18px;display:flex;gap:8px;flex-wrap:wrap;z-index:2}button,summary{cursor:pointer;padding:9px 14px;background:#fcfaf3;border:1px solid #bbb6a9;border-radius:6px}details{position:fixed;right:20px;top:18px;z-index:3}details img{display:block;max-height:65vh;max-width:30vw;background:#fff}#status{font-size:12px}#error{position:fixed;inset:35%;color:#a22}button:focus{outline:2px solid #936}</style><header><h1>3D微观模型</h1><span id="status">正在准备真实高斯模型…</span></header>@@IMAGE@@<canvas id="canvas"></canvas><nav><button data-view="front">正面</button><button data-view="45">45°</button><button data-view="left">左侧</button><button data-view="right">右侧</button><button data-view="back">背面</button><button data-view="top">俯视</button><button id="orbit-left">向左转</button><button id="orbit-right">向右转</button><button id="zoom-in">放大</button><button id="zoom-out">缩小</button><select id="detail-focus" aria-label="细节近看"><option value="">整体场景</option></select><button id="reset">重置</button><button id="shot">保存视角</button></nav><p id="error"></p><div id="detail-comparison" style="position:fixed;right:20px;top:70px;z-index:3;background:#fffaf3;padding:10px;border-radius:8px;display:none;max-width:240px;font-size:13px"></div><script id="model-data" type="application/octet-stream">@@DATA@@</script>@@VENDOR@@<script>@@VIEWER@@</script></html>'''.replace('<\\/style>','</style>')
    scene=(asset/'scene.json').read_text(encoding='utf8') if (asset/'scene.json').exists() else '{}'
    template=template.replace('@@VENDOR@@','<script id="detail-focus-data" type="application/json">'+json.dumps(focuses,ensure_ascii=False).replace('</','<\\/')+'</script>@@VENDOR@@')
    template=template.replace('@@VENDOR@@','<script id="scene-data" type="application/json">'+scene.replace('</','<\\/')+'</script>@@VENDOR@@')
    result=template.replace('@@IMAGE@@',image).replace('@@DATA@@',data).replace('@@VENDOR@@',vendor).replace('@@VIEWER@@',(ROOT/'assets/viewer.js').read_text(encoding='utf8'))
    (asset/'preview.html').write_text(result,encoding='utf8')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('--source');a=p.parse_args();make_preview(a.asset,a.source)
