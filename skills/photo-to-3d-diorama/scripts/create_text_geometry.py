import bpy,json,sys
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);words=json.loads(Path(a.spec).read_text(encoding='utf8'));bpy.ops.wm.read_factory_settings(use_empty=True);out=[]
for item in words:
 curve=bpy.data.curves.new(item['id'],'FONT');curve.body=item['text'];curve.align_x='LEFT';curve.size=1;curve.resolution_u=8;curve.extrude=.018 if item.get('thin') else .09;curve.bevel_depth=.008 if item.get('thin') else .035;curve.bevel_resolution=3
 font=Path(item['font'])
 if not font.is_file():raise FileNotFoundError('A font containing the exact original characters is required: '+str(font))
 curve.font=bpy.data.fonts.load(str(font));obj=bpy.data.objects.new(item['id'],curve);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.convert(target='MESH');m=bpy.context.object.data;m.calc_loop_triangles();out.append({**item,'vertices':[list(v.co) for v in m.vertices],'triangles':[list(t.vertices) for t in m.loop_triangles]});obj.select_set(False)
Path(a.out).write_text(json.dumps(out,ensure_ascii=False),encoding='utf8');print('ACTUAL_TEXT_MESHES',len(out))
