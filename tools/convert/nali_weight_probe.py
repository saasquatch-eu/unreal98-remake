"""Stress-test Blender auto weights on the checked four-arm geometry probe.

The deliberately exaggerated pose exposes deformation problems. It does not
produce or endorse a rig for UE5. Run via Blender with arguments after `--`.
"""
import argparse
import bpy
from pathlib import Path
from mathutils import Vector
from hashlib import sha256
import json
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True, help='new private diagnostic directory')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if args.output_dir.exists() or args.output_dir.resolve() == args.source.resolve():
    parser.error('output directory must be new and distinct from source')
source = args.source
source_hash = sha256(source.read_bytes()).hexdigest()
if source_hash != '2e7a0f8b7850c8906dea54cb5c33caaf5ccb9c97a3bc3653530a98b44dc73e6f':
    parser.error('geometry probe differs from checked private output')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(meshes) != 1:
    raise ValueError('expected one geometry-probe mesh')
mesh_obj, = meshes
if len(mesh_obj.data.vertices) != 40002 or len(mesh_obj.data.polygons) != 80000:
    raise ValueError('geometry-probe counts differ')
mesh_obj.name = 'Nali_deform_probe_ue5'

armature = bpy.data.armatures.new('Nali_four_arm_test_ue5')
rig = bpy.data.objects.new('Nali_four_arm_test_ue5', armature)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')

def bone(name, head, tail, parent=None):
    item = armature.edit_bones.new(name)
    item.head, item.tail = head, tail
    if parent:
        item.parent = armature.edit_bones[parent]
    return item

bone('pelvis', (0, 0, -0.20), (0, 0, 0.05))
bone('spine', (0, 0, 0.05), (0, 0, 0.56), 'pelvis')
bone('neck', (0, 0, 0.56), (0, 0, 0.75), 'spine')
bone('head', (0, 0, 0.75), (0, 0, 0.92), 'neck')
for side, sign in [('L', -1), ('R', 1)]:
    bone(f'leg_upper_{side}', (sign*.16, 0, -0.16), (sign*.18, 0, -0.52), 'pelvis')
    bone(f'leg_lower_{side}', (sign*.18, 0, -0.52), (sign*.18, 0, -0.82), f'leg_upper_{side}')
    bone(f'foot_{side}', (sign*.18, 0, -0.82), (sign*.18, -.12, -0.91), f'leg_lower_{side}')
    bone(f'upper_shoulder_{side}', (sign*.17, 0, .61), (sign*.29, 0, .56), 'spine')
    bone(f'upper_arm_{side}', (sign*.29, 0, .56), (sign*.42, 0, .29), f'upper_shoulder_{side}')
    bone(f'upper_forearm_{side}', (sign*.42, 0, .29), (sign*.50, 0, -.01), f'upper_arm_{side}')
    bone(f'upper_hand_{side}', (sign*.50, 0, -.01), (sign*.53, 0, -.20), f'upper_forearm_{side}')
    bone(f'lower_shoulder_{side}', (sign*.17, 0, .38), (sign*.24, 0, .32), 'spine')
    bone(f'lower_arm_{side}', (sign*.24, 0, .32), (sign*.32, 0, .07), f'lower_shoulder_{side}')
    bone(f'lower_forearm_{side}', (sign*.32, 0, .07), (sign*.39, 0, -.15), f'lower_arm_{side}')
    bone(f'lower_hand_{side}', (sign*.39, 0, -.15), (sign*.42, 0, -.28), f'lower_forearm_{side}')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
groups = {g.name: 0 for g in mesh_obj.vertex_groups}
unweighted = 0
for vertex in mesh_obj.data.vertices:
    if not vertex.groups:
        unweighted += 1
    for group in vertex.groups:
        if group.weight > .01:
            groups[mesh_obj.vertex_groups[group.group].name] += 1
print('WEIGHT_REPORT', json.dumps({'unweighted_vertices': unweighted, 'group_vertices': groups}), flush=True)
if unweighted or not all(groups.values()):
    raise ValueError('automatic weights did not cover the expected bones')

for side, sign in [('L', -1), ('R', 1)]:
    rig.pose.bones[f'upper_shoulder_{side}'].rotation_mode = 'XYZ'
    rig.pose.bones[f'upper_shoulder_{side}'].rotation_euler[0] = sign*.6
    rig.pose.bones[f'lower_shoulder_{side}'].rotation_mode = 'XYZ'
    rig.pose.bones[f'lower_shoulder_{side}'].rotation_euler[0] = -sign*.5
bpy.context.view_layer.update()

evaluated = mesh_obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
hand_motion = {}
for side in ('L', 'R'):
    for level in ('upper', 'lower'):
        name = f'{level}_hand_{side}'
        index = mesh_obj.vertex_groups[name].index
        selected = [(v.index, g.weight) for v in mesh_obj.data.vertices for g in v.groups if g.group == index and g.weight > .01]
        if not selected:
            raise ValueError('hand has no significant automatic weights: ' + name)
        total = sum(weight for _, weight in selected)
        before = sum((mesh_obj.data.vertices[i].co * weight for i, weight in selected), Vector()) / total
        after = sum((evaluated.vertices[i].co * weight for i, weight in selected), Vector()) / total
        hand_motion[name] = dict(vertices=len(selected), max_weight=max(w for _, w in selected), distance_m=(after-before).length)
print('HAND_MOTION', json.dumps(hand_motion), flush=True)
if any(info['distance_m'] < .05 for info in hand_motion.values()):
    raise ValueError('one or more hands failed to move in the pose test')

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 800
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
world = bpy.data.worlds.new('Studio')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.18, .18, .18, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = .8
camera_data = bpy.data.cameras.new('Camera')
camera = bpy.data.objects.new('Camera', camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 2.2
camera.location = (0, -3.5, 0)
camera.rotation_euler = (Vector((0,0,0)) - camera.location).to_track_quat('-Z','Y').to_euler()
light_data = bpy.data.lights.new('Light', 'AREA')
light_data.energy = 500
light_data.size = 3
light = bpy.data.objects.new('Light', light_data)
scene.collection.objects.link(light)
light.location = (0, -3, 2)
light.rotation_euler = (Vector((0,0,0)) - light.location).to_track_quat('-Z','Y').to_euler()
args.output_dir.mkdir(parents=True, exist_ok=False)
previews = []
for name, direction, light_offset in [('front', Vector((0, -3.5, 0)), Vector((0, -3, 2))),
                                      ('right', Vector((3.5, 0, 0)), Vector((3, 0, 2)))]:
    camera.location = direction
    camera.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
    light.location = light_offset
    light.rotation_euler = (-light_offset).to_track_quat('-Z', 'Y').to_euler()
    path = args.output_dir / f'Nali_auto_weight_pose_{name}_ue5.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    previews.append(dict(path=path.name, sha256=sha256(path.read_bytes()).hexdigest()))
report = dict(schema='nali-auto-weight-stress-v1', source=str(source.resolve()),
              source_sha256=source_hash, blender_version=bpy.app.version_string,
              test_bones=len(armature.bones), vertices=len(mesh_obj.data.vertices),
              unweighted_vertices=unweighted, group_vertices_over_001=groups,
              upper_shoulder_x_radians=0.6, lower_shoulder_x_radians=0.5,
              hand_motion=hand_motion, previews=previews,
              conclusion='Mechanical coverage only; inspect images for deformation quality. This pose is not a usable rig or animation.')
(args.output_dir / 'Nali_auto_weight_pose_ue5.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(output_dir=str(args.output_dir), unweighted_vertices=unweighted,
                      hand_motion=hand_motion, previews=previews), indent=2), flush=True)
