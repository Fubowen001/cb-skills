"""Blender --background --python export_blender.py -- <asset-directory>.
Preserves full Gaussian data; visible ellipsoids are explicitly a sampled proxy.
"""
import sys,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gaussian_io import load_ply,NAMES
from common import sha,read
args=sys.argv[sys.argv.index('--')+1:];asset=Path(args[0]).resolve();dest=asset/'model.blend'
if dest.exists():raise FileExistsError('Existing Blender file preserved')
v=load_ply(asset/'model.ply');xyz=v[:,[0,2,1]].copy();xyz[:,2]*=-1
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0
mesh=bpy.data.meshes.new('Full Gaussian parameters');mesh.from_pydata(xyz.tolist(),[],[]);mesh.update();obj=bpy.data.objects.new('Full_Gaussians_RAW_ATTRIBUTES',mesh);bpy.context.collection.objects.link(obj)
for i,name in enumerate(NAMES):
    a=mesh.attributes.new('raw_'+name,'FLOAT','POINT');a.data.foreach_set('value',v[:,i].copy())
obj.hide_render=True;obj.hide_viewport=True;obj['representation']='Complete anisotropic Gaussian data, NOT polygon mesh';obj['coordinate_transform']='positions=(raw.x,raw.z,-raw.y); attributes raw_* remain in original PLY coordinates';obj['source_sha256']=sha(asset/'model.ply')
step=max(1,math.ceil(len(v)/30000));ids=np.arange(0,len(v),step);alpha=1/(1+np.exp(-np.clip(v[ids,6],-30,30)));ids=ids[alpha>.03]
pm=bpy.data.meshes.new('Sampled Gaussian proxy');pm.from_pydata(xyz[ids].tolist(),[],[]);pm.update();preview=bpy.data.objects.new('ELLIPSOID_PROXY_NOT_FINAL_GAUSSIAN_RENDER',pm);bpy.context.collection.objects.link(preview)
cols=np.clip(.5+.28209479177387814*v[ids,3:6],0,1);a=pm.color_attributes.new('gs_color','FLOAT_COLOR','POINT');a.data.foreach_set('color',np.column_stack([cols,np.ones(len(ids))]).astype(np.float32).ravel())
a=pm.attributes.new('gs_scale','FLOAT_VECTOR','POINT');a.data.foreach_set('vector',np.exp(v[ids,7:10]).astype(np.float32).ravel());turn=Quaternion((1,0,0),-math.pi/2);angles=[]
for q in v[ids,10:14]:angles.extend((turn@Quaternion(tuple(q)).normalized()).to_euler())
a=pm.attributes.new('gs_rotation','FLOAT_VECTOR','POINT');a.data.foreach_set('vector',angles)
mat=bpy.data.materials.new('Gaussian source color');mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();at=n.new('ShaderNodeAttribute');at.attribute_name='gs_color';em=n.new('ShaderNodeEmission');out=n.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(at.outputs['Color'],em.inputs['Color']);mat.node_tree.links.new(em.outputs[0],out.inputs[0]);pm.materials.append(mat)
tree=bpy.data.node_groups.new('Sampled ellipsoids NOT transparent splats','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=tree.nodes;l=tree.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');ico=n.new('GeometryNodeMeshIcoSphere');ico.inputs['Radius'].default_value=1;ico.inputs['Subdivisions'].default_value=1;inst=n.new('GeometryNodeInstanceOnPoints');sc=n.new('GeometryNodeInputNamedAttribute');sc.data_type='FLOAT_VECTOR';sc.inputs['Name'].default_value='gs_scale';rt=n.new('GeometryNodeInputNamedAttribute');rt.data_type='FLOAT_VECTOR';rt.inputs['Name'].default_value='gs_rotation';real=n.new('GeometryNodeRealizeInstances');sm=n.new('GeometryNodeSetMaterial');sm.inputs['Material'].default_value=mat
for a,b in [(inp.outputs['Geometry'],inst.inputs['Points']),(ico.outputs['Mesh'],inst.inputs['Instance']),(sc.outputs['Attribute'],inst.inputs['Scale']),(rt.outputs['Attribute'],inst.inputs['Rotation']),(inst.outputs['Instances'],real.inputs['Geometry']),(real.outputs['Geometry'],sm.inputs['Geometry']),(sm.outputs['Geometry'],out.inputs['Geometry'])]:l.new(a,b)
preview.modifiers.new('Sampled ellipsoid preview','NODES').node_group=tree;preview['notice']='Sampled opaque ellipsoids; use preview.html for full transparent Gaussian rendering.'
if (asset/'structure.json').exists():
    structural=read(asset/'structure.json')
    for repair in structural['repairs']:
        verts=[(p[0],-p[2],p[1]) for p in repair['vertices_runtime']];m=bpy.data.meshes.new(repair['id']+'_closed_mesh');m.from_pydata(verts,[],repair['faces']);m.update();o=bpy.data.objects.new(repair['id']+'_AUTHORED_SOURCE_CONSTRAINED',m);bpy.context.collection.objects.link(o)
        material=bpy.data.materials.new(repair['id']+'_material');material.diffuse_color=(*repair['color'],1);m.materials.append(material);o['inferred_completion']=True;o['source_constraint']=repair['source_constraint'];o['reason']=repair['reason']

if (asset/'details.json').exists():
    fine=read(asset/'details.json');image_materials={}
    for element in fine['meshes']:
        rv=element['vertices_runtime'];verts=[(v[0],-v[2],v[1]) for v in rv];faces=[list(f) for f in element['faces']];front_count=len(faces);material_indices=[0]*front_count;uvs=element.get('uv')
        if element.get('back_vertices_runtime'):
            N=len(verts);verts += [(v[0],-v[2],v[1]) for v in element['back_vertices_runtime']];backfaces=[[i+N for i in reversed(f)] for f in element['faces']];faces += backfaces;material_indices += [1]*len(backfaces);edges={}
            for f in element['faces']:
                for a,b in zip(f,f[1:]+f[:1]):
                    key=tuple(sorted((a,b)))
                    if key in edges:edges[key]=None
                    else:edges[key]=(a,b)
            for edge in edges.values():
                if edge:
                    a,b=edge;faces.append([a,b,b+N,a+N]);material_indices.append(1)
            if uvs:uvs=uvs+uvs
        m=bpy.data.meshes.new(element['id']+'_fine_mesh');m.from_pydata(verts,[],faces);m.update();o=bpy.data.objects.new(element['id']+'_SOURCE_CONSTRAINED_DETAIL',m);bpy.context.collection.objects.link(o);o['method']=element['kind'];o['source_sha256']=fine['original_source_sha256'];o['hidden_depth_inferred']=True
        if element.get('text'):o['exact_original_text']=element['text']
        if element.get('texture'):
            key=element['texture']
            if key not in image_materials:
                image=bpy.data.images.load(str(asset/key));image.pack();mat=bpy.data.materials.new('Original photo detail');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();tex=nodes.new('ShaderNodeTexImage');tex.image=image;em=nodes.new('ShaderNodeEmission');out=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(tex.outputs['Color'],em.inputs['Color']);mat.node_tree.links.new(em.outputs[0],out.inputs[0]);image_materials[key]=mat
            m.materials.append(image_materials[key]);layer=m.uv_layers.new(name='OriginalPhotoUV')
            for loop in m.loops:
                coord=uvs[loop.vertex_index];layer.data[loop.index].uv=(coord[0],1-coord[1])
            if element.get('back_color'):
                back=bpy.data.materials.new(element['id']+'_inferred_skin_back');back.diffuse_color=(*element['back_color'],1);m.materials.append(back)
                for poly,material_index in zip(m.polygons,material_indices):poly.material_index=material_index
        else:
            mat=bpy.data.materials.new(element['id']+'_solid_text');mat.diffuse_color=(*element.get('color',[.8,.8,.8]),1);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*element.get('color',[.8,.8,.8]),1);bs.inputs['Metallic'].default_value=1. if element.get('metallic') else 0.;bs.inputs['Roughness'].default_value=.23;m.materials.append(mat)

lo=xyz.min(0);hi=xyz.max(0);center=Vector(((lo+hi)*.5).tolist());extent=float(np.max(hi-lo));bpy.ops.object.camera_add(location=center+Vector((extent*2,0,extent*.1)));cam=bpy.context.object;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=extent*1.3;bpy.context.scene.camera=cam
scene=bpy.context.scene
if (asset/'scene.json').exists():
    spec=read(asset/'scene.json');scene['portable_scene_manifest']=__import__('json').dumps(spec,ensure_ascii=False)
    for e in spec.get('required_elements',[]):scene['element_'+e['id']]=str(e)
scene['representation']='Gaussian source plus sampled ellipsoid proxy';scene['gaussian_count']=len(v);scene['units']='Relative; no physical scale inferred';scene.world=bpy.data.worlds.new('Neutral background');scene.world.color=(.9,.88,.8);scene.view_settings.view_transform='Standard'
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(dest));print('BLENDER_EXPORT_OK '+str(dest))
