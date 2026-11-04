"""Validate fine-detail geometry and source linkage. Visual approval stays explicit."""
import argparse,json
from pathlib import Path
from common import read,write,sha
from gaussian_io import load_ply,np

def audit_details(asset,requirements):
    asset=Path(asset);d=read(asset/'details.json');meshes=d['meshes'];faces=[m for m in meshes if 'face' in m['kind']];hands=[m for m in meshes if 'hand' in m['kind']];texts=[m for m in meshes if m['kind']=='exact_extruded_text'];errors=[]
    if len(faces)!=requirements['faces']:errors.append('Missing or duplicate face surfaces')
    if len(hands)!=requirements['hands']:errors.append('Missing or duplicate hand surfaces')
    if sorted(m['text'] for m in texts)!=sorted(requirements.get('texts',[])):errors.append('Exact text differs from verified source transcription')
    diagnostics=[]
    for m in meshes:
        p=np.asarray(m['vertices_runtime']);sv=np.linalg.svd(p-p.mean(0),compute_uv=False);ratio=float(sv[-1]/sv[0]) if sv[0] else 0
        if not np.isfinite(p).all() or not len(m['faces']):errors.append('Invalid mesh '+m['id'])
        if ('face' in m['kind'] or 'hand' in m['kind']) and ratio<.002:errors.append('Detail surface appears planar: '+m['id'])
        if m.get('texture'):
            texture=asset/m['texture']
            if not texture.exists():errors.append('Missing texture: '+m['texture'])
            uv=np.asarray(m['uv'])
            if len(uv)!=len(p) or not np.isfinite(uv).all():errors.append('Invalid UV correspondence '+m['id'])
        diagnostics.append({'id':m['id'],'vertices':len(p),'triangles':len(m['faces']),'depth_ratio':ratio})
    points=load_ply(asset/'model.ply');report={'structural_status':'fail' if errors else 'pass','visual_status':'needs_closeup_and_multiview_review','gaussians':len(points),'faces':len(faces),'hands':len(hands),'exact_texts':[m['text'] for m in texts],'source_sha256':d['original_source_sha256'],'diagnostics':diagnostics,'errors':errors};write(asset/'detail-audit.json',report)
    if errors:raise ValueError('; '.join(errors))
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('--requirements',required=True);a=p.parse_args();r=audit_details(a.asset,read(a.requirements));print(json.dumps(r,ensure_ascii=True,indent=2))
