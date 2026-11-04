"""Portable scene manifest: actual model plus environment, never a photo backdrop."""
from common import write,read

def make_scene(asset,job,item):
    scene={'schema':1,'scope':job.get('scope','scene'),'representation':'anisotropic_gaussian_scene','units':'relative','coordinates':'official_default_PLY','runtime_coordinates':'(x,-y,-z), Y up, front +X','components':[{'id':'complete_scene','file':'model.ply','runtime_file':'model.splat','position':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1]}],'source_elements':item.get('inventory',{}),'required_elements':item.get('scene_contract',{}).get('required_elements',[]),'environment':item.get('environment',{'type':'neutral','color':'#eeeae0'}),'note':'Structural scene is in 3D Gaussians. Sky is atmosphere, not a rectangular photo wall. Ground and real walls must remain in the actual model.'}
    if (asset/'structure.json').exists():
        scene['authored_structure']='structure.json';scene['structural_note']='Source-constrained authored closed meshes and corresponding Gaussian surfaces'
    if (asset/'record.json').exists():scene['components'][0]['count']=read(asset/'record.json').get('count')
    write(asset/'scene.json',scene)
