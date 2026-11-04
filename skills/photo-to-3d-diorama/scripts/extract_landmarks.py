"""Local face/hand landmark extraction with explicit ROI and missed-region reporting."""
import argparse,sys,os,json
from pathlib import Path
from common import runtime,read,write,sha
D=Path(os.environ.get('PHOTO3D_DETAIL_RUNTIME',runtime()/'detail'));sys.path.insert(0,str(D/'packages'))
import numpy as np
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def extract(image_path,roi_path,out):
    image_path=Path(image_path);spec=read(roi_path);rgb=Image.open(image_path).convert('RGB');W,H=rgb.size;result={'schema':1,'source_sha256':sha(image_path),'width':W,'height':H,'faces':[],'hands':[],'face_roi_indices':[],'hand_roi_indices':[],'missing_faces':[],'missing_hands':[],'visual_review_required':True}
    options=[('faces',vision.FaceLandmarker,vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(D/'models/face_landmarker.task')),num_faces=12,min_face_detection_confidence=.1,min_face_presence_confidence=.1),'face_landmarks'),('hands',vision.HandLandmarker,vision.HandLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(D/'models/hand_landmarker.task')),num_hands=20,min_hand_detection_confidence=.15,min_hand_presence_confidence=.15),'hand_landmarks')]
    for kind,cls,opts,field in options:
        with cls.create_from_options(opts) as detector:
            for i,region in enumerate(spec.get(kind,[])):
                cx,cy,size=region;left,top=int(cx-size/2),int(cy-size/2);tile=rgb.crop((left,top,left+size,top+size)).resize((384,384));image=mp.Image(image_format=mp.ImageFormat.SRGB,data=np.asarray(tile));found=getattr(detector.detect(image),field)
                correction=spec.get('manual_'+kind,{}).get(str(i))
                if correction:
                    if not correction.get('reviewed') or not correction.get('reason'):raise ValueError('Manual corrections need actual source review and reason')
                    landmarks=[[p[0]/W,p[1]/H,p[2] if len(p)>2 else 0] for p in correction['pixel_landmarks']]
                elif found:landmarks=[[(left+p.x*size)/W,(top+p.y*size)/H,p.z*size/W] for p in found[0]]
                else:result['missing_'+kind].append(i);continue
                expected=478 if kind=='faces' else 21
                if len(landmarks)!=expected and not (kind=='faces' and len(landmarks)==468):raise ValueError('Unexpected landmark count')
                result[kind].append(landmarks);result[('face' if kind=='faces' else 'hand')+'_roi_indices'].append(i)
    write(out,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--rois',required=True);p.add_argument('--out',required=True);a=p.parse_args();result=extract(a.image,a.rois,a.out);print(json.dumps({'faces':len(result['faces']),'hands':len(result['hands']),'missing_faces':result['missing_faces'],'missing_hands':result['missing_hands']}))
