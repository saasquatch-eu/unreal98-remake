"""Create an in-place four-arm walk timing preview from the Nali blockout.

The authored joint angles are motion cues, not source frame retargeting.
"""
import argparse
from hashlib import sha256
import json
from math import cos, pi, sin
from pathlib import Path
import sys

import bpy
from mathutils import Vector

EXPECTED='cc1ded75bf7c7d17bda59d015cc40bda585e20379eb03eec2382903acdfc94da'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if args.output_dir.exists():
    raise FileExistsError(args.output_dir)
if sha256(args.source.read_bytes()).hexdigest()!=EXPECTED:
    raise ValueError('blockout Blender scene hash differs from checked input')
bpy.ops.wm.open_mainfile(filepath=str(args.source))
rig=bpy.data.objects['Nali1_skeleton_ue5']
if len(rig.data.bones)!=91:
    raise ValueError('expected 91 bones')
parts=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('Nali1_')
       and o.name!='Nali1_visual_guide_ue5']
if len(parts)!=25 or not all(all(v.groups for v in o.data.vertices) for o in parts):
    raise ValueError('expected 25 weighted blockout parts')
guide=bpy.data.objects['Nali1_visual_guide_ue5']
guide.hide_set(True)
guide.hide_render=True
scene=bpy.context.scene
scene.render.fps=15
scene.frame_start=0
scene.frame_end=20

for frame in range(21):
    phase=2*pi*frame/20
    for side,side_phase in [('L',0),('R',pi)]:
        leg=sin(phase+side_phase)
        thigh=rig.pose.bones[f'leg_{side}_thigh']
        shin=rig.pose.bones[f'leg_{side}_shin']
        foot=rig.pose.bones[f'leg_{side}_foot']
        for bone in (thigh,shin,foot): bone.rotation_mode='XYZ'
        thigh.rotation_euler.x=.27*leg
        shin.rotation_euler.x=.10+.20*max(0,-leg)
        foot.rotation_euler.x=-.12*leg
        for bone in (thigh,shin,foot):
            bone.keyframe_insert(data_path='rotation_euler',frame=frame)
        for tier,amplitude,offset in [('upper',.22,pi),('lower',.18,pi+.65)]:
            clavicle=rig.pose.bones[f'arm_{tier}_{side}_clavicle']
            elbow=rig.pose.bones[f'arm_{tier}_{side}_forearm']
            clavicle.rotation_mode='XYZ'
            elbow.rotation_mode='XYZ'
            clavicle.rotation_euler.x=amplitude*sin(phase+side_phase+offset)
            elbow.rotation_euler.x=.07+.08*max(0,sin(phase+side_phase+offset))
            clavicle.keyframe_insert(data_path='rotation_euler',frame=frame)
            elbow.keyframe_insert(data_path='rotation_euler',frame=frame)
    pelvis=rig.pose.bones['pelvis']
    pelvis.location.z=.012*(1-cos(2*phase))
    pelvis.keyframe_insert(data_path='location',frame=frame)

if not rig.animation_data or not rig.animation_data.action:
    raise ValueError('animation keyframes were not saved')
action=rig.animation_data.action
action.name='Nali1_WalkPreview_ue5'
scene.frame_set(0)
bpy.context.view_layer.update()

camera_data=bpy.data.cameras.new('Nali1_WalkPreview_camera_ue5')
camera=bpy.data.objects.new('Nali1_WalkPreview_camera_ue5',camera_data)
scene.collection.objects.link(camera)
scene.camera=camera
camera_data.type='ORTHO'
camera_data.ortho_scale=2.3
camera.location=(2.5,-3.5,.2)
camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
light_data=bpy.data.lights.new('Nali1_WalkPreview_light_ue5','AREA')
light_data.energy=500
light_data.size=3
light=bpy.data.objects.new('Nali1_WalkPreview_light_ue5',light_data)
scene.collection.objects.link(light)
light.location=(-2,-3,3)
light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
world=bpy.data.worlds.new('Nali1_WalkPreview_world_ue5')
world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.25,.25,1)
scene.world=world
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=480
scene.render.resolution_y=600
scene.render.resolution_percentage=100

args.output_dir.mkdir(parents=True,exist_ok=False)
previews=[]
scene.render.image_settings.file_format='PNG'
for frame in range(20):
    scene.frame_set(frame)
    path=args.output_dir/f'Nali1_WalkPreview_frame{frame:02d}_ue5.png'
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    previews.append({'frame':frame,'file':path.name,'sha256':sha256(path.read_bytes()).hexdigest()})
scene.frame_set(0)
blend=args.output_dir/'Nali1_WalkPreview_ue5.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))

bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
for obj in parts: obj.select_set(True)
glb=args.output_dir/'Nali1_WalkPreview_ue5.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                          export_animations=True,export_skins=True)

report={'schema':'nali1-walk-blockout-v1','source':str(args.source.resolve()),
        'source_sha256':EXPECTED,'fps':15,'frames':21,'loop_period_frames':20,
        'loop_period_seconds':20/15,'action':action.name,
        'authored_motion_not_source_retarget':True,
        'blend_sha256':sha256(blend.read_bytes()).hexdigest(),
        'glb_sha256':sha256(glb.read_bytes()).hexdigest(),
        'previews':previews}
(args.output_dir/'Nali1_WalkPreview_ue5.json').write_text(json.dumps(report,indent=2)+'\n')
print('WALK_REPORT',json.dumps(report),flush=True)
