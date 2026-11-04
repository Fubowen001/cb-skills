"""Explicit, source-constrained structural repairs after multi-angle review.
Spec coordinates are runtime X,Y,Z (Y up), not raw PLY coordinates.
Never run this as automatic solidification of every asset.
"""
import argparse,json,shutil,hashlib,math
from pathlib import Path
from common import read,write,sha
from gaussian_io import load_ply,NAMES,np,pack
from make_preview import make_preview
from audit_asset import audit

def mesh_for(p):
    if p['type']=='box':
        lo=np.array(p['min']);hi=np.array(p['max']);v=[[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]];f=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]
    elif p['type']=='extruded_polygon':
        poly=p['polygon_xz'];n=len(poly);v=[]
        for level in ['bottom','top']:
            plane=p.get(level+'_plane')
            for x,z in poly:
                y=plane[0]*x+plane[1]*z+plane[2] if plane else p[level];v.append([x,y,z])
        f=[list(reversed(range(n))),list(range(n,n*2))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    else:raise ValueError('Unsupported structural primitive')
    return np.array(v,dtype=np.float32),f

def sample_surface(vertices,faces,spacing,color,seed):
    rng=np.random.default_rng(seed);points=[];seen=set()
    for face in faces:
        # Fan triangles, barycentric grid; rounded 3D keys deduplicate seams.
        a=vertices[face[0]]
        for i in range(1,len(face)-1):
            b,c=vertices[face[i]],vertices[face[i+1]];n=max(1,int(math.ceil(max(np.linalg.norm(b-a),np.linalg.norm(c-a),np.linalg.norm(c-b))/spacing)))
            for u in range(n+1):
                for v in range(n+1-u):
                    point=a+(b-a)*(u/n)+(c-a)*(v/n);key=tuple(np.round(point/spacing*.7).astype(int))
                    if key not in seen:seen.add(key);points.append(point)
    pts=np.asarray(points,dtype=np.float32);out=np.zeros((len(pts),14),dtype=np.float32);out[:,:3]=pts*[1,-1,-1];variation=rng.uniform(.88,1.08,(len(pts),1));rgb=np.clip(np.array(color)[None,:]*variation,0,1);out[:,3:6]=(rgb-.5)/.28209479177387814;out[:,6]=6.;out[:,7:10]=np.log(spacing*.72);out[:,10]=1;return out

def complete(asset,spec_path,backup):
    asset=Path(asset).resolve();spec=read(spec_path);signature=sha(spec_path)
    if (asset/'structure.json').exists():
        old=read(asset/'structure.json')
        if old.get('spec_sha256')==signature:return {'status':'already_applied'}
        raise FileExistsError('Existing structure preserved; use a new variant')
    review=read(asset/'review.json') if (asset/'review.json').exists() else {}
    if review.get('status') in ('approved','accepted'):raise ValueError('Approved asset locked; make a new variant')
    backup=Path(backup).resolve();backup.mkdir(parents=True,exist_ok=False)
    for name in ['model.ply','model.splat','record.json','review.json']:
        if (asset/name).exists():shutil.copy2(asset/name,backup/name)
    v=load_ply(asset/'model.ply');original_count=len(v);removed=0
    for primitive in spec['primitives']:
        if 'trim_below_plane' in primitive:
            a,b,c=primitive['trim_below_plane'];runtime=v[:,:3]*[1,-1,-1];keep=runtime[:,1]>=a*runtime[:,0]+b*runtime[:,2]+c-float(primitive.get('trim_margin',.02));removed+=int((~keep).sum());v=v[keep]
    parts=[v];meshes=[]
    for i,p in enumerate(spec['primitives']):
        if not p.get('source_constraint') or not p.get('reason'):raise ValueError('Structural repair needs source constraint and observed reason')
        vertices,faces=mesh_for(p);parts.append(sample_surface(vertices,faces,float(p.get('spacing',.008)),p['color'],i+42));meshes.append({**p,'vertices_runtime':vertices.tolist(),'faces':faces})
    result=np.concatenate(parts);dt=np.dtype([(n,'<f4') for n in NAMES]);arr=np.empty(len(result),dtype=dt)
    for i,n in enumerate(NAMES):arr[n]=result[:,i]
    header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(arr))+'\n'+''.join('property float '+n+'\n' for n in NAMES)+'end_header\n';temp=asset/'model.ply.tmp';temp.write_bytes(header.encode()+arr.tobytes());temp.replace(asset/'model.ply');pack(asset/'model.ply',asset/'model.splat')
    write(asset/'structure.json',{'schema':1,'spec_sha256':signature,'coordinates':'runtime X,Y,Z (Y up)','method':'Explicit authored closed structural meshes and matching Gaussian surfaces','inferred':True,'repairs':meshes,'original_ply_sha256':sha(backup/'model.ply'),'removed_gaussians':removed,'original_gaussian_count':original_count,'added_gaussians':len(result)-len(v)})
    scene=read(asset/'scene.json');scene['authored_structure']='structure.json';scene['components'][0]['count']=len(result);write(asset/'scene.json',scene)
    record=read(asset/'record.json');source=asset.parents[2]/record['sources'][0]['path'] if record.get('sources') else None
    make_preview(asset,source if source and source.exists() else None)
    rec=read(asset/'record.json');rec['count']=len(result);rec['structural_completion']={'spec_sha256':signature,'original_ply_sha256':sha(backup/'model.ply'),'added_gaussians':len(result)-len(v)}
    for name in ['model.ply','model.splat','preview.html','scene.json','structure.json']:rec['outputs'][name]=sha(asset/name)
    write(asset/'record.json',rec);review['status']='needs_visual_review';review['structural_repairs']=meshes;write(asset/'review.json',review);audit(asset);return {'status':'completed','count':len(result)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('--spec',required=True);p.add_argument('--backup',required=True);a=p.parse_args();print(json.dumps(complete(a.asset,a.spec,a.backup)))
