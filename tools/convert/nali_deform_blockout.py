"""Private diagnostic: build a segmented, skinned four-arm Nali blockout."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

EXPECTED='42114b492e06f4e318c6c39b6f4f93d8bc1dc4fa489d43efd4565484c41f87f9'
p=argparse.ArgumentParser()
p.add_argument('--skeleton',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
if a.output_dir.exists():
    raise FileExistsError(f'output directory already exists: {a.output_dir}')
if sha256(a.skeleton.read_bytes()).hexdigest()!=EXPECTED:
    raise ValueError('skeleton template differs from checked source SHA-256')
bpy.ops.wm.open_mainfile(filepath=str(a.skeleton))
rig=bpy.data.objects['Nali1_skeleton_ue5']
if len(rig.data.bones)!=91:
    raise ValueError('skeleton template does not have 91 bones')
guide=bpy.data.objects['Nali1_visual_guide_ue5']
guide.hide_set(True)
guide.hide_render=True
scene=bpy.context.scene

mat=bpy.data.materials.new('Nali1_blockout_ue5')
mat.diffuse_color=(.38,.25,.15,1)
mat.use_nodes=True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.38,.25,.15,1)
meshes=[]

def bind(obj,weights):
    obj.parent=rig
    modifier=obj.modifiers.new('Nali1_skin_ue5','ARMATURE')
    modifier.object=rig
    modifier.use_deform_preserve_volume=True
    names={name for row in weights for name in row}
    groups={name:obj.vertex_groups.new(name=name) for name in names}
    for i,row in enumerate(weights):
        for name,value in row.items():
            if value>0: groups[name].add([i],value,'REPLACE')
    if not all(v.groups for v in obj.data.vertices):
        raise ValueError(f'unweighted vertices in {obj.name}')
    meshes.append(obj)

def tube(name,points,radii,rows,sections=16):
    points=[Vector(x) for x in points]
    if not (len(points)==len(radii)==len(rows) and len(points)>=2):
        raise ValueError(f'invalid tube profile: {name}')
    verts=[]; faces=[]; weights=[]
    for j,(point,radius,weight) in enumerate(zip(points,radii,rows)):
        tangent=(points[min(j+1,len(points)-1)]-points[max(j-1,0)]).normalized()
        side=tangent.cross(Vector((0,1,0))).normalized()
        if side.length<.001: side=tangent.cross(Vector((1,0,0))).normalized()
        up=tangent.cross(side).normalized()
        for k in range(sections):
            from math import cos,sin,pi
            theta=2*pi*k/sections
            verts.append(point+radius*(cos(theta)*side+sin(theta)*up))
            weights.append(weight)
    for j in range(len(points)-1):
        for k in range(sections):
            k2=(k+1)%sections
            faces.append((j*sections+k,j*sections+k2,(j+1)*sections+k2,(j+1)*sections+k))
    start=len(verts); verts.append(points[0]); weights.append(rows[0])
    end=len(verts); verts.append(points[-1]); weights.append(rows[-1])
    for k in range(sections):
        k2=(k+1)%sections
        faces.append((start,k2,k))
        last=(len(points)-1)*sections
        faces.append((end,last+k,last+k2))
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    uv=mesh.uv_layers.new(name='UVMap')
    side_faces=(len(points)-1)*sections
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index=mesh.loops[loop_index].vertex_index
            if poly.index<side_faces:
                ring=vertex_index//sections
                around=vertex_index%sections
                seam=poly.index%sections==sections-1 and around==0
                uv.data[loop_index].uv=(1.0 if seam else around/sections,
                                       ring/(len(points)-1))
            else:
                from math import cos,sin,pi
                if vertex_index>=len(points)*sections:
                    uv.data[loop_index].uv=(.5,.5)
                else:
                    around=vertex_index%sections
                    uv.data[loop_index].uv=(.5+.5*cos(2*pi*around/sections),
                                           .5+.5*sin(2*pi*around/sections))
    mesh.materials.append(mat)
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    bind(obj,weights)
    for poly in mesh.polygons: poly.use_smooth=True
    return obj

def sphere(name,center,scale,bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16)
    obj=bpy.context.object
    obj.name=name
    obj.data.name=name
    obj.location=center
    obj.scale=scale
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    obj.data.materials.append(mat)
    bind(obj,[{bone:1.0} for _ in obj.data.vertices])
    for poly in obj.data.polygons: poly.use_smooth=True
    return obj

def mix(u,v,t): return tuple(u[i]*(1-t)+v[i]*t for i in range(3))

sphere('Nali1_torso_ue5',(0,0,.29),(.27,.145,.37),'spine_upper')
sphere('Nali1_pelvis_ue5',(0,0,-.13),(.21,.14,.18),'pelvis')
sphere('Nali1_head_ue5',(0,-.005,.79),(.105,.10,.145),'head')
for side,sgn in [('L',-1),('R',1)]:
    hip=(sgn*.16,0,-.16); knee=(sgn*.18,0,-.52)
    ankle=(sgn*.18,0,-.82); ball=(sgn*.18,-.12,-.91)
    thigh=f'leg_{side}_thigh'; shin=f'leg_{side}_shin'; foot=f'leg_{side}_foot'
    tube(f'Nali1_leg_{side}_ue5',
         [hip,mix(hip,knee,.4),mix(hip,knee,.85),knee,mix(knee,ankle,.2),mix(knee,ankle,.7),ankle,ball],
         [.09,.085,.069,.06,.057,.047,.045,.06],
         [{thigh:1},{thigh:1},{thigh:1},{thigh:.5,shin:.5},{shin:1},{shin:1},{shin:.5,foot:.5},{foot:1}])
    for tier in ('upper','lower'):
        if tier=='upper':
            shoulder=(sgn*.29,0,.56); elbow=(sgn*.42,0,.29)
            wrist=(sgn*.50,0,-.01); palm=(sgn*.53,0,-.12)
            radii=[.075,.07,.06,.054,.053,.047,.044,.05]
        else:
            shoulder=(sgn*.24,0,.32); elbow=(sgn*.32,0,.07)
            wrist=(sgn*.39,0,-.15); palm=(sgn*.42,0,-.22)
            radii=[.06,.055,.05,.045,.043,.038,.036,.044]
        prefix=f'arm_{tier}_{side}'
        clav=f'{prefix}_clavicle'; upper=f'{prefix}_upper'; fore=f'{prefix}_forearm'; hand=f'{prefix}_hand'
        points=[shoulder,mix(shoulder,elbow,.35),mix(shoulder,elbow,.8),elbow,
                mix(elbow,wrist,.2),mix(elbow,wrist,.7),wrist,palm]
        rows=[{clav:.6,upper:.4},{upper:1},{upper:1},{upper:.5,fore:.5},
              {fore:1},{fore:1},{fore:.5,hand:.5},{hand:1}]
        tube(f'Nali1_{prefix}_ue5',points,radii,rows)
        for digit,offset in enumerate((-.025,0,.025),start=1):
            base=(palm[0]+sgn*.006*(digit-2),palm[1]+offset,palm[2]-.007)
            length=.08 if tier=='upper' else .065
            finger=[(base[0],base[1],base[2]-length*i/3) for i in range(4)]
            bones=[f'{prefix}_finger{digit}_{i}' for i in range(1,4)]
            tube(f'Nali1_{prefix}_finger{digit}_ue5',finger,[.016,.014,.012,.009],
                 [{hand:1},{bones[0]:1},{bones[1]:1},{bones[2]:1}],sections=8)
        thumb_start=(palm[0]-sgn*.025,palm[1]-.035,palm[2]+.025)
        thumb_mid=(thumb_start[0]-sgn*.026,thumb_start[1]-.01,thumb_start[2]-.025)
        thumb_end=(thumb_mid[0]-sgn*.012,thumb_mid[1]-.005,thumb_mid[2]-.025)
        tube(f'Nali1_{prefix}_thumb_ue5',[thumb_start,thumb_mid,thumb_end],
             [.018,.014,.01],[{hand:1},{f'{prefix}_thumb_1':1},{f'{prefix}_thumb_2':1}],sections=8)

if len(meshes)!=25:
    raise ValueError(f'expected 25 mesh parts, got {len(meshes)}')

def hand_centroids():
    result={}
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for side in ('L','R'):
        for tier in ('upper','lower'):
            prefix=f'arm_{tier}_{side}'
            obj=bpy.data.objects[f'Nali1_{prefix}_ue5']
            group_index=obj.vertex_groups[f'{prefix}_hand'].index
            selected=[v.index for v in obj.data.vertices if any(
                g.group==group_index and g.weight>.5 for g in v.groups)]
            if not selected:
                raise ValueError(f'no weighted hand vertices: {prefix}')
            evaluated=obj.evaluated_get(depsgraph).to_mesh()
            result[prefix]=sum((evaluated.vertices[i].co for i in selected),Vector())/len(selected)
            obj.evaluated_get(depsgraph).to_mesh_clear()
    return result

def render_pose(label,camera_position=(0,-3.5,0)):
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=900;scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    world=bpy.data.worlds.new('Nali1_studio_ue5')
    scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.25,.25,1)
    camera_data=bpy.data.cameras.new('Nali1_camera_ue5')
    camera=bpy.data.objects.new('Nali1_camera_ue5',camera_data)
    scene.collection.objects.link(camera)
    scene.camera=camera
    camera_data.type='ORTHO';camera_data.ortho_scale=2.3
    camera.location=camera_position
    camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
    light_data=bpy.data.lights.new('Nali1_light_ue5','AREA')
    light_data.energy=500;light_data.size=3
    light=bpy.data.objects.new('Nali1_light_ue5',light_data)
    scene.collection.objects.link(light)
    light.location=(-2,-3,3)
    light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
    path=a.output_dir/f'Nali1_blockout_{label}_ue5.png'
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera,do_unlink=True)
    bpy.data.objects.remove(light,do_unlink=True)
    return path

a.output_dir.mkdir(parents=True,exist_ok=False)
rest_centroids=hand_centroids()
rest=render_pose('rest')
for side,sgn in [('L',-1),('R',1)]:
    for tier,angle in [('upper',sgn*.6),('lower',-sgn*.5)]:
        bone=rig.pose.bones[f'arm_{tier}_{side}_clavicle']
        bone.rotation_mode='XYZ';bone.rotation_euler[0]=angle
bpy.context.view_layer.update()
stress_centroids=hand_centroids()
hand_motion={name:(stress_centroids[name]-rest_centroids[name]).length
             for name in rest_centroids}
if not all(distance>.05 for distance in hand_motion.values()):
    raise ValueError(f'one or more hands failed to move: {hand_motion}')
stress=render_pose('stress')
stress_oblique=render_pose('stress_oblique',(3,-3,0))
for bone in rig.pose.bones: bone.rotation_euler=(0,0,0)
bpy.context.view_layer.update()
scene.camera=None
blend=a.output_dir/'Nali1_blockout_ue5.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
for obj in meshes:obj.select_set(True)
glb=a.output_dir/'Nali1_blockout_ue5.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                          export_animations=False,export_skins=True)
report={'schema':'nali1-deform-blockout-v1',
                  'skeleton':str(a.skeleton.resolve()),
                  'skeleton_sha256':EXPECTED,
                  'mesh_objects':len(meshes),'bones':len(rig.data.bones),
                  'vertices':sum(len(x.data.vertices) for x in meshes),
                  'triangles':sum(sum(len(p.vertices)-2 for p in x.data.polygons) for x in meshes),
                  'all_meshes_have_uv0':all(x.data.uv_layers for x in meshes),
                  'hand_motion_m':hand_motion,
                  'blend_sha256':sha256(blend.read_bytes()).hexdigest(),
                  'glb_sha256':sha256(glb.read_bytes()).hexdigest(),
                  'rest':str(rest),'stress':str(stress),'stress_oblique':str(stress_oblique)}
(a.output_dir/'Nali1_blockout_ue5.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
