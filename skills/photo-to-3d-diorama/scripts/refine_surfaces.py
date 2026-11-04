"""Source-textured curved face/hand surfaces. Original images are never edited.
A calibrated source view and explicit per-element correspondences are required.
"""
import sys,json,math,shutil,hashlib
from pathlib import Path
import os,argparse
from common import runtime,inside
D=Path(os.environ.get('PHOTO3D_DETAIL_RUNTIME',runtime()/'detail'));sys.path.insert(0,str(D/'packages'))
from common import read,write,sha
from gaussian_io import load_ply,NAMES,np,pack
from make_preview import make_preview
from scipy.spatial import Delaunay
from scipy.spatial.transform import Rotation
from scipy.ndimage import distance_transform_edt,gaussian_filter
from PIL import Image
import cv2

def similarity(a,b):
    ac=a-a.mean(0);bc=b-b.mean(0);u,s,vt=np.linalg.svd(ac.T@bc);rot=u@vt
    if np.linalg.det(rot)<0:u[:,-1]*=-1;rot=u@vt
    scale=np.sum((ac@rot)*bc)/np.sum(ac*ac);offset=b.mean(0)-a.mean(0)@rot*scale
    return rot*scale,offset
class Camera:
    def __init__(self,eye,target,width,height,fov):
        self.eye=np.array(eye);self.f=np.array(target)-self.eye;self.f/=np.linalg.norm(self.f);self.r=np.cross(self.f,[0,1,0]);self.r/=np.linalg.norm(self.r);self.u=np.cross(self.r,self.f);self.w=width;self.h=height;self.focal=height/(2*np.tan(np.deg2rad(fov)/2))
    def project(self,p):
        delta=p-self.eye;d=delta@self.f;uv=np.column_stack([self.w*.5+(delta@self.r)*self.focal/d,self.h*.5-(delta@self.u)*self.focal/d]);return uv,d
    def unproject(self,uv,depth):
        return self.eye+depth[:,None]*self.f+(uv[:,0]-self.w*.5)[:,None]*depth[:,None]/self.focal*self.r-(uv[:,1]-self.h*.5)[:,None]*depth[:,None]/self.focal*self.u

def splats_for_mesh(vertices,faces,uv,image,source_step=1.2,solid_color=None):
    output=[];rgb_array=np.asarray(image.convert('RGB'),dtype=np.float32)/255;W,H=image.size;C=np.diag([1,-1,-1])
    for tri in faces:
        ids=np.asarray(tri);pts=vertices[ids];tex=uv[ids]*[W,H];normal=np.cross(pts[1]-pts[0],pts[2]-pts[0]);area=np.linalg.norm(normal)
        if area<1e-12:continue
        normal/=area;tangent=pts[1]-pts[0];tangent/=np.linalg.norm(tangent);bi=np.cross(normal,tangent);mat=np.column_stack([tangent,bi,normal]);q=Rotation.from_matrix(C@mat).as_quat();q=q[[3,0,1,2]]
        n=max(1,int(np.ceil(max(np.linalg.norm(tex[1]-tex[0]),np.linalg.norm(tex[2]-tex[0]),np.linalg.norm(tex[2]-tex[1]))/source_step)))
        aa,bb=np.meshgrid(np.arange(n+1),np.arange(n+1));a=aa.ravel()/n;b=bb.ravel()/n;valid=a+b<=1.00001;a=a[valid];b=b[valid];bary=np.column_stack([1-a-b,a,b]);xyz=bary@pts;xy=bary@tex
        ix=np.clip(xy[:,0],0,W-1);iy=np.clip(xy[:,1],0,H-1);x0=ix.astype(int);y0=iy.astype(int);x1=np.minimum(x0+1,W-1);y1=np.minimum(y0+1,H-1);fx=(ix-x0)[:,None];fy=(iy-y0)[:,None];colors=(rgb_array[y0,x0]*(1-fx)+rgb_array[y0,x1]*fx)*(1-fy)+(rgb_array[y1,x0]*(1-fx)+rgb_array[y1,x1]*fx)*fy
        if solid_color is not None:colors[:]=solid_color
        spacing=max(np.linalg.norm(pts[1]-pts[0]),np.linalg.norm(pts[2]-pts[0]),np.linalg.norm(pts[2]-pts[1]))/n
        v=np.zeros((len(xyz),14),dtype=np.float32);v[:,:3]=xyz@C;v[:,3:6]=(colors-.5)/.28209479177387814;v[:,6]=5.;v[:,7:10]=np.log([max(spacing*.68,1e-5),max(spacing*.68,1e-5),max(spacing*.15,1e-6)]);v[:,10:14]=q;output.append(v)
    return np.concatenate(output) if output else np.zeros((0,14),dtype=np.float32)

def refine(case,asset,out,spec):
    if out.exists():raise FileExistsError(out)
    source=Image.open(inside(case,spec.get('style_texture',spec['source']))).convert('RGB');
    if spec.get('style','source')!='source' and not spec.get('style_texture'):raise ValueError('Style-matched detail texture required')
    SW,SH=source.size;sl=read(case/spec['source_landmarks']);rl=read(case/spec['reference_landmarks']);tl=read(case/spec['target_landmarks']);camdata=read(case/spec['camera']);old=load_ply(asset/'model.ply');runtime=old[:,:3]*[1,-1,-1];target=(runtime.min(0)+runtime.max(0))*.5;cam=Camera(camdata['camera'],target,tl['width'],tl['height'],camdata.get('fov',40));projected,depth=cam.project(runtime);source_faces=np.asarray(sl['faces']);ref_faces=np.asarray(rl['faces']);target_faces=np.asarray(tl['faces']);rw,rh=rl['width'],rl['height'];tw,th=tl['width'],tl['height']
    if len(source_faces)!=len(ref_faces) or len(source_faces)!=len(spec['target_face_centers']):raise ValueError('Every observed face needs a correspondence')
    if len(sl['hands'])!=len(rl['hands']):raise ValueError('Every observed hand needs a correspondence')
    if sl.get('source_sha256') and sl['source_sha256']!=sha(inside(case,spec['source'])):raise ValueError('Source changed since extraction')
    if camdata.get('asset_sha256') and camdata['asset_sha256']!=sha(asset/'model.ply'):raise ValueError('Calibration belongs to a different asset')
    roi_centers=np.array(spec['target_face_centers']);matches=[]
    for face in target_faces:
        nose=face[1,:2]*[tw,th];idx=int(np.argmin(np.linalg.norm(roi_centers-nose,axis=1)));matches.append((idx,nose))
    ref_centers=np.array([ref_faces[i,1,:2]*[rw,rh] for i,_ in matches]);tar_centers=np.array([xy for _,xy in matches]);A=np.column_stack([ref_centers,np.ones(len(ref_centers))]);affine=np.linalg.lstsq(A,tar_centers,rcond=None)[0] if len(matches)>=3 else None
    additions=[];meshes=[];remove=np.zeros(len(old),dtype=bool);report=[]
    for i,(sface,rface) in enumerate(zip(source_faces,ref_faces)):
        src=sface[:468,:2]*[SW,SH];ref=rface[:468,:2]*[rw,rh]
        if i in dict(matches):
            dst=next(face[:468,:2]*[tw,th] for face in target_faces if np.argmin(np.linalg.norm(roi_centers-face[1,:2]*[tw,th],axis=1))==i)
            M,T=similarity(src[[33,263,1,152,10]],dst[[33,263,1,152,10]])
        else:
            dst=np.column_stack([ref,np.ones(len(ref))])@affine;M,T=similarity(src[[33,263,1,152,10]],dst[[33,263,1,152,10]])
        dest=src@M+T;hull=Delaunay(dest);face_inside=hull.find_simplex(projected)>=0;ids=np.flatnonzero(face_inside & (old[:,6]>-3));facewidth=np.ptp(dest[:,0]);candidates=depth[ids]
        if not len(ids):raise ValueError('No existing head under correspondence '+str(i))
        anchor=float(np.quantile(candidates,.18))-.0015;worldpx=anchor/cam.focal;scale=np.sqrt(abs(np.linalg.det(M)));z=(sface[:468,2]-sface[1,2])*SW*scale*worldpx*float(spec.get('face_depth_scale',.28))
        vertices=cam.unproject(dest,anchor+z);triangles=Delaunay(src).simplices;uv=src/[SW,SH];new=splats_for_mesh(vertices,triangles,uv,source,source_step=1.25);additions.append(new)
        remove |= face_inside & (depth < anchor+facewidth*worldpx*.75) & (depth > anchor-facewidth*worldpx*.65)
        meshes.append({'id':f'face-{i+1:02d}','kind':'source_landmark_curved_face','vertices_runtime':vertices.tolist(),'faces':triangles.tolist(),'uv':uv.tolist(),'texture':'textures/source.jpg','source_face_index':i,'unseen_surface':'existing inferred head sides retained'})
        report.append({'element':f'face-{i+1:02d}','source_sha256':sha(case/spec['source']),'source_landmarks':468,'added_gaussians':len(new),'nonplanar_depth_range':float(np.ptp(vertices@cam.f)),'placement_anchor_depth':anchor,'target_bbox':[dest.min(0).tolist(),dest.max(0).tolist()]})
    for region in spec.get('cleanup_regions',[]):
        if not region.get('reason'):raise ValueError('Local cleanup needs an observed reason')
        x0,y0,x1,y1=region['bbox'];hit=(projected[:,0]>=x0)&(projected[:,0]<=x1)&(projected[:,1]>=y0)&(projected[:,1]<=y1);color=np.clip(.5+.28209479177387814*old[:,3:6],0,1)
        if region.get('color')=='red_orange':hit &= (color[:,0]>color[:,1]*1.18)&(color[:,0]>color[:,2]*1.1)
        remove |= hit
    # Hands: real source silhouette, 3D landmark depth, rounded skin surface and opaque back.
    for i,(shand,rhand) in enumerate(zip(sl['hands'],rl['hands'])):
        shand=np.array(shand);rhand=np.array(rhand);src=shand[:,:2]*[SW,SH];ref=rhand[:,:2]*[rw,rh];M,T=similarity(src[[0,5,9,17]],ref[[0,5,9,17]])
        if spec.get('hand_targets'):
            center=np.array(spec['hand_targets'][i]['center']);factor=spec['hand_targets'][i]['scale'];dest_ref=(ref-ref[9])*factor+center;M,T=similarity(src[[0,5,9,17]],dest_ref[[0,5,9,17]])
        else:
            dest_ref=np.column_stack([ref,np.ones(21)])@affine;M,T=similarity(src[[0,5,9,17]],dest_ref[[0,5,9,17]])
        left,top=np.floor(src.min(0)-5).astype(int);right,bottom=np.ceil(src.max(0)+5).astype(int);left=max(0,left);top=max(0,top);right=min(SW,right);bottom=min(SH,bottom)
        roi=np.asarray(source)[top:bottom,left:right];HH,WW=roi.shape[:2];joints=src-[left,top];skeleton=np.zeros((HH,WW),np.uint8);palm=np.round(joints[[0,1,5,9,13,17]]).astype(np.int32);cv2.fillConvexPoly(skeleton,palm,255);radius=max(2,int(np.linalg.norm(src[5]-src[17])*.15))
        for root in [1,5,9,13,17]:
            for a,b in zip(range(root,root+3),range(root+1,root+4)):cv2.line(skeleton,tuple(np.round(joints[a]).astype(int)),tuple(np.round(joints[b]).astype(int)),255,radius*2)
        hsv=cv2.cvtColor(roi,cv2.COLOR_RGB2HSV);skin=(roi[:,:,0].astype(float)>=roi[:,:,1]*.88)&(roi[:,:,0].astype(float)>=roi[:,:,2]*.85)&(hsv[:,:,2]>40);mask=(skeleton>0)&skin
        if spec.get('hand_mask_mode')=='skeleton':mask=skeleton>0
        custom=spec.get('hand_silhouettes',{}).get(str(i))
        if custom:
            if not custom.get('reviewed') or not custom.get('reason'):raise ValueError('Hand silhouette needs source review')
            raster=np.zeros((HH,WW),np.uint8);cv2.fillPoly(raster,[np.round(np.array(custom['polygon'])-[left,top]).astype(np.int32)],255);mask=raster>0
        mask=cv2.morphologyEx(mask.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))>0
        distance=distance_transform_edt(mask);yy,xx=np.mgrid[0:HH:1.5,0:WW:1.5];xy=np.column_stack([xx.ravel(),yy.ravel()]);take=mask[np.minimum(xy[:,1].astype(int),HH-1),np.minimum(xy[:,0].astype(int),WW-1)];xy=xy[take];source_xy=xy+[left,top]
        if len(xy)<10:raise ValueError('Hand silhouette too small '+str(i))
        dest=source_xy@M+T;boxlo,boxhi=dest.min(0),dest.max(0);hit=(projected[:,0]>boxlo[0])&(projected[:,0]<boxhi[0])&(projected[:,1]>boxlo[1])&(projected[:,1]<boxhi[1]);near=depth[hit]
        if not len(near):raise ValueError('No hand surface under target '+str(i))
        anchor=float(np.quantile(near,.18))-.001;worldpx=anchor/cam.focal;scale=np.sqrt(abs(np.linalg.det(M)));dist=np.linalg.norm(source_xy[:,None,:]-src[None,:,:],axis=2);weights=1/np.maximum(dist,1)**3;z=(weights@(shand[:,2]-shand[9,2]))/weights.sum(1)*SW*scale*worldpx*float(spec.get('hand_depth_scale',.35));rounding=np.clip(distance[xy[:,1].astype(int),xy[:,0].astype(int)]/radius,0,1)*radius*scale*worldpx*.25
        vertices=cam.unproject(dest,anchor+z-rounding);triangles=Delaunay(xy).simplices;centers=xy[triangles].mean(1);edge=np.linalg.norm(xy[triangles]-np.roll(xy[triangles],1,axis=1),axis=2).max(1);valid=mask[np.clip(centers[:,1].astype(int),0,HH-1),np.clip(centers[:,0].astype(int),0,WW-1)]&(edge<3.2);triangles=triangles[valid];uv=source_xy/[SW,SH];new=splats_for_mesh(vertices,triangles,uv,source,source_step=1.3);additions.append(new)
        # Keep a real skin back separated from the textured front, not a zero-thickness photograph.
        back=vertices+cam.f[None,:]*max(radius*scale*worldpx*.45,.0007);skin_color=np.median(roi[mask],axis=0)/255.;additions.append(splats_for_mesh(back,triangles[:,::-1],uv,source,source_step=1.8,solid_color=skin_color))
        keep2d=mask[np.clip(((projected-T)@np.linalg.inv(M))[:,1]-top,0,HH-1).astype(int),np.clip(((projected-T)@np.linalg.inv(M))[:,0]-left,0,WW-1).astype(int)];remove |= hit&keep2d&(depth<anchor+np.ptp(dest[:,0])*worldpx*.7)&(depth>anchor-np.ptp(dest[:,0])*worldpx*.7)
        if spec.get('hand_cleanup_margin') is not None:
            margin=float(spec['hand_cleanup_margin'])*max(np.ptp(dest[:,0]),np.ptp(dest[:,1]));expanded=(projected[:,0]>boxlo[0]-margin)&(projected[:,0]<boxhi[0]+margin)&(projected[:,1]>boxlo[1]-margin)&(projected[:,1]<boxhi[1]+margin);rgb=np.clip(.5+.28209479177387814*old[:,3:6],0,1);coarse_skin=(rgb[:,0]>rgb[:,1]*1.05)&(rgb[:,0]>rgb[:,2]*1.02)&(rgb.mean(1)>.16);depth_window=max(np.ptp(dest[:,0]),np.ptp(dest[:,1]))*worldpx*2.5
            if not spec.get('hand_cleanup_reason'):raise ValueError('Hand cleanup requires observed reason')
            selected=expanded if spec.get('hand_cleanup_mode')=='all' else expanded&coarse_skin
            wrist=src[0]@M+T;wrist_keep=np.linalg.norm(projected-wrist,axis=1)<max(np.ptp(dest[:,0]),np.ptp(dest[:,1]))*.33
            remove |= selected&~wrist_keep&(abs(depth-anchor)<depth_window)
        meshes.append({'id':f'hand-{i+1:02d}','kind':'source_landmark_rounded_hand','vertices_runtime':vertices.tolist(),'faces':triangles.tolist(),'uv':uv.tolist(),'texture':'textures/source.jpg','back_vertices_runtime':back.tolist(),'back_color':skin_color.tolist(),'source_hand_index':i})
        report.append({'element':f'hand-{i+1:02d}','source_sha256':sha(case/spec['source']),'source_landmarks':21,'silhouette_pixels':int(mask.sum()),'added_gaussians':len(new),'placement_anchor_depth':anchor})
    shutil.copytree(asset,out,ignore=shutil.ignore_patterns('model.blend','*.tmp'));(out/'textures').mkdir(exist_ok=True);source.save(out/'textures/source.jpg',quality=100,subsampling=0)
    v=np.concatenate([old[~remove],*additions]);dt=np.dtype([(n,'<f4') for n in NAMES]);arr=np.empty(len(v),dtype=dt)
    for i,n in enumerate(NAMES):arr[n]=v[:,i]
    header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(v))+'\n'+''.join('property float '+n+'\n' for n in NAMES)+'end_header\n';(out/'model.ply').write_bytes(header.encode()+arr.tobytes());pack(out/'model.ply',out/'model.splat');write(out/'details.json',{'schema':1,'method':'Source-photo texture sampled onto nonplanar landmark-derived face and rounded hand surfaces','original_source_sha256':sha(case/spec['source']),'meshes':meshes,'report':report,'removed_coarse_gaussians':int(remove.sum())});make_preview(out,case/spec['source']);rec=read(out/'record.json');rec['count']=len(v);rec['detail_refinement']={'source_sha256':sha(case/spec['source']),'elements':report,'original_ply_sha256':sha(asset/'model.ply')}
    for name in ['model.ply','model.splat','preview.html','details.json','textures/source.jpg']:rec['outputs'][name]=sha(out/name)
    scene_path=out/'scene.json'
    if scene_path.exists():
        scene=read(scene_path);scene['components'][0]['count']=len(v);scene['detail_manifest']='details.json';write(scene_path,scene);rec['outputs']['scene.json']=sha(scene_path)
    write(out/'record.json',rec);write(out/'review.json',{'status':'needs_visual_review','detail_elements':report});print('DETAILS_CREATED',len(v),'removed',int(remove.sum()),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('spec');p.add_argument('--job-root');a=p.parse_args();path=Path(a.spec).resolve();spec=read(path);case=Path(a.job_root).resolve() if a.job_root else path.parent
    refine(case,inside(case,spec['asset']),inside(case,spec['output']),spec)
