import sys,json,math
from pathlib import Path
import os,argparse
from common import runtime
D=Path(os.environ.get('PHOTO3D_DETAIL_RUNTIME',runtime()/'detail'));sys.path.insert(0,str(D/'packages'))
from common import *
from gaussian_io import *
from refine_surfaces import Camera
from scipy.spatial.transform import Rotation
from make_preview import make_preview
def apply_text(asset,geometry,camera_path,source):
    if read(asset/'review.json').get('status') in ('approved','accepted'):raise ValueError('Approved asset locked; create a new variant')
    old=load_ply(asset/'model.ply');world=old[:,:3]*[1,-1,-1];target=(world.min(0)+world.max(0))*.5;camdata=read(camera_path);cam=Camera(camdata['camera'],target,camdata['width'],camdata['height'],camdata.get('fov',40));uv,d=cam.project(world);rgb=np.clip(.5+.28209479177387814*old[:,3:6],0,1);remove=np.zeros(len(old),bool);add=[];details=read(asset/'details.json');sourcewords=read(geometry);
    existing={m['id'] for m in details['meshes']}
    if any('text-'+item['id'] in existing for item in sourcewords):raise ValueError('Text IDs already exist; create a fresh variant rather than duplicate glyphs')
    C=np.diag([1,-1,-1])
    for item in sourcewords:
     bbox=np.array(item['bbox']);mask=(uv[:,0]>bbox[0])&(uv[:,0]<bbox[2])&(uv[:,1]>bbox[1])&(uv[:,1]<bbox[3]);neutral=(rgb.max(1)-rgb.min(1)<.17)&(rgb.mean(1)>.38);select=mask&neutral
     if select.sum()<5:select=mask
     anchor=float(np.quantile(d[select],.35))-.002
     if item.get('remove_mode')=='full':anchor=float(np.quantile(d[mask],.025))-.005
     if item.get('thin'):anchor=float(np.quantile(d[mask],.045))-.002
     pp=anchor/cam.focal;verts=np.array(item['vertices']);lo=verts.min(0);hi=verts.max(0);xy=np.column_stack([bbox[0]+(verts[:,0]-lo[0])/(hi[0]-lo[0])*(bbox[2]-bbox[0]),bbox[3]-(verts[:,1]-lo[1])/(hi[1]-lo[1])*(bbox[3]-bbox[1])]);z=(verts[:,2]-lo[2])/(hi[2]-lo[2]+1e-9)*(bbox[3]-bbox[1])*pp*(.035 if item.get('thin') else .13);points=cam.unproject(xy,anchor-z)
     if not item.get('thin'):
      scope=mask&(d>anchor-.03)&(d<anchor+.075)
      if item.get('remove_mode','neutral')=='neutral':scope &= neutral
      remove |= scope
     faces=np.array(item['triangles']);tri=points[faces];normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);areas=np.linalg.norm(normals,axis=1)*.5;valid=areas>1e-14;tri=tri[valid];normals=normals[valid];areas=areas[valid];normals/=np.linalg.norm(normals,axis=1,keepdims=True)
     N=int(item.get('gaussian_budget',3500 if item.get('thin') else 12000));rng=np.random.default_rng(42);chosen=rng.choice(len(tri),size=N,p=areas/areas.sum());patch=tri[chosen];a=rng.random(N);b=rng.random(N);root=np.sqrt(a);bary=np.column_stack([1-root,root*(1-b),root*b]);xyz=np.einsum('ni,nij->nj',bary,patch);normal=normals[chosen];tangent=patch[:,1]-patch[:,0];tangent/=np.linalg.norm(tangent,axis=1,keepdims=True);bi=np.cross(normal,tangent);mat=np.stack([tangent,bi,normal],axis=2);mat=np.einsum('ij,njk->nik',C,mat);q=Rotation.from_matrix(mat).as_quat()[:,[3,0,1,2]]
     shade=.8+.2*np.abs(normal@np.array([.5,.7,.5]));color=np.array(item['color'])[None,:]*shade[:,None]
     if item.get('metallic'):color=np.clip(np.array(item['color'])[None,:]*(.35+.65*np.abs(normal@cam.f)**3)[:,None]+.2*np.maximum(0,normal@np.array([-.3,.8,-.4]))[:,None]**8,0,1)
     spacing=max(math.sqrt(float(areas.sum())/N)*.72,.00008);v=np.zeros((N,14),np.float32);v[:,:3]=xyz@C;v[:,3:6]=(color-.5)/.28209479177387814;v[:,6]=6.;v[:,7:10]=np.log([spacing,spacing,spacing*.25]);v[:,10:14]=q;add.append(v);details['meshes'].append({'id':'text-'+item['id'],'kind':'exact_extruded_text','text':item['text'],'vertices_runtime':points.tolist(),'faces':faces.tolist(),'color':item['color'],'metallic':item.get('metallic',False),'calibration_bbox':item['bbox']});details['report'].append({'element':'text-'+item['id'],'exact_text':item['text'],'method':'actual beveled extruded glyph geometry, not generated letter texture','added_gaussians':len(v)});print('TEXT',item['id'],len(v),flush=True)
    v=np.concatenate([old[~remove],*add]);arr=np.empty(len(v),dtype=[(n,'<f4') for n in NAMES])
    for i,n in enumerate(NAMES):arr[n]=v[:,i]
    header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(v))+'\n'+''.join('property float '+n+'\n' for n in NAMES)+'end_header\n';(asset/'model.ply').write_bytes(header.encode()+arr.tobytes());pack(asset/'model.ply',asset/'model.splat');write(asset/'details.json',details);make_preview(asset,source);rec=read(asset/'record.json');rec['count']=len(v)
    for p in ['model.ply','model.splat','details.json','preview.html']:rec['outputs'][p]=sha(asset/p)
    scene_path=asset/'scene.json'
    if scene_path.exists():
        scene=read(scene_path);scene['components'][0]['count']=len(v);scene['detail_manifest']='details.json';write(scene_path,scene);rec['outputs']['scene.json']=sha(scene_path)
    write(asset/'record.json',rec);print('FINISHED',len(v),'removed bad letter Gaussians',int(remove.sum()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('asset');p.add_argument('--geometry',required=True);p.add_argument('--camera',required=True);p.add_argument('--source',required=True);a=p.parse_args();apply_text(Path(a.asset).resolve(),Path(a.geometry).resolve(),Path(a.camera).resolve(),Path(a.source).resolve())
