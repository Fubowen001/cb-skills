import bpy,json,sys
from pathlib import Path
p=Path(sys.argv[sys.argv.index('--')+1]);bpy.ops.wm.open_mainfile(filepath=str(p/'model.blend'));items=[]
for o in bpy.data.objects:
 if o.type!='MESH' or not o.name.endswith('_SOURCE_CONSTRAINED_DETAIL'):continue
 edges={}
 for f in o.data.polygons:
  ids=list(f.vertices)
  for a,b in zip(ids,ids[1:]+ids[:1]):k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
 item={'id':o.name,'vertices':len(o.data.vertices),'boundary_edges':sum(n==1 for n in edges.values()),'exact_text':o.get('exact_original_text'),'source_sha256':o.get('source_sha256')}
 if o.name.startswith('hand-'):assert not item['boundary_edges'],item
 if item['exact_text']:assert min(o.dimensions)>0,item
 items.append(item)
r={'status':'pass','detail_meshes':items,'packed_images':sum(i.packed_file is not None for i in bpy.data.images)};assert r['packed_images']>=1;(p/'blender-detail-audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('EDITABLE_DETAIL_AUDIT_PASS',len(items))
