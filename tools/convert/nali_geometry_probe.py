"""Make a private, geometry-only four-arm Nali deformation probe in Blender.

Run with Blender's --background --python interface and arguments after `--`.
The source GLB is never modified. This is a topology experiment, not a rig,
retopologized production mesh, texture transfer or UE5 import.
"""

import argparse
import bmesh
import bpy
from collections import Counter
from hashlib import sha256
import json
from mathutils import Vector
from pathlib import Path
import sys


SOURCE_SHA256 = '7420903cc74d03838a196ac20028848738c5b898970f5aab9602c6151dc5cc18'
SOURCE_COUNTS = (481942, 892194)
OUTPUT_NAME = 'Nali_deform_probe_ue5.glb'


def topology(obj):
    mesh = obj.data
    parent = list(range(len(mesh.vertices)))
    sizes = [1] * len(parent)

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for edge in mesh.edges:
        a, b = (root(index) for index in edge.vertices)
        if a == b:
            continue
        if sizes[a] < sizes[b]:
            a, b = b, a
        parent[b] = a
        sizes[a] += sizes[b]

    components = Counter(root(index) for index in range(len(parent)))
    bm = bmesh.new()
    bm.from_mesh(mesh)
    boundary = sum(edge.is_boundary for edge in bm.edges)
    other_nonmanifold = sum(not edge.is_manifold and not edge.is_boundary for edge in bm.edges)
    bm.free()
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = [min(c[i] for c in corners) for i in range(3)]
    maximum = [max(c[i] for c in corners) for i in range(3)]
    return dict(vertices=len(mesh.vertices), polygons=len(mesh.polygons),
                triangles=sum(len(poly.vertices) - 2 for poly in mesh.polygons),
                connected_components=len(components),
                largest_component_vertices=max(components.values()),
                boundary_edges=boundary, other_nonmanifold_edges=other_nonmanifold,
                uv_layers=len(mesh.uv_layers), materials=len(mesh.materials),
                bounds_min=minimum, bounds_max=maximum)


def load_one_mesh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if len(meshes) != 1:
        raise ValueError(f'expected one mesh in {path}, found {len(meshes)}')
    return meshes[0]


def render_clay(obj, output_dir):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center = sum(corners, Vector()) / len(corners)
    height = max(c.z for c in corners) - min(c.z for c in corners)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    world = bpy.data.worlds.new('Neutral studio')
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.18, 0.18, 0.18, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
    camera_data = bpy.data.cameras.new('Review camera')
    camera = bpy.data.objects.new('Review camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = height * 1.18
    light_data = bpy.data.lights.new('Review light', 'AREA')
    light_data.energy = 500
    light_data.shape = 'DISK'
    light_data.size = 3
    light = bpy.data.objects.new('Review light', light_data)
    scene.collection.objects.link(light)
    for name, direction in [('front', (0, -1, 0)), ('right', (1, 0, 0)),
                            ('back', (0, 1, 0)), ('left', (-1, 0, 0))]:
        camera.location = center + Vector(direction) * height * 1.8 + Vector((0, 0, height * 0.04))
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        light.location = camera.location + Vector((0, 0, height * 0.5))
        light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(output_dir / f'Nali_deform_probe_{name}_ue5.png')
        bpy.ops.render.render(write_still=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='checked private Meshy GLB')
    parser.add_argument('--output-dir', type=Path, required=True, help='new private directory')
    parser.add_argument('--voxel-size', type=float, default=0.008, help='metres; default 0.008')
    parser.add_argument('--target-triangles', type=int, default=80000)
    args = parser.parse_args(argv)
    if args.output_dir.exists() or args.output_dir.resolve() == args.source.resolve():
        parser.error('output directory must be new and distinct from source')
    if not 0.004 <= args.voxel_size <= 0.02 or not 20000 <= args.target_triangles <= 120000:
        parser.error('probe settings outside checked range')
    source_hash = sha256(args.source.read_bytes()).hexdigest()
    if source_hash != SOURCE_SHA256:
        parser.error('source GLB SHA-256 differs from checked Meshy prototype')

    obj = load_one_mesh(args.source)
    source = topology(obj)
    if (source['vertices'], source['triangles']) != SOURCE_COUNTS:
        raise ValueError('source GLB import counts differ from checked prototype')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.remesh_voxel_size = args.voxel_size
    bpy.ops.object.voxel_remesh()
    remesh_triangles = sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
    if remesh_triangles > args.target_triangles:
        modifier = obj.modifiers.new('Reduce probe triangles', 'DECIMATE')
        modifier.ratio = args.target_triangles / remesh_triangles
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    # Voxel remeshing does not provide a trustworthy PBR UV transfer. Save a
    # geometry-only reference, leaving the source GLB as the visual master.
    obj.data.materials.clear()
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])
    obj.name = obj.data.name = 'Nali_deform_probe_ue5'
    candidate = topology(obj)
    if candidate['triangles'] != args.target_triangles or candidate['connected_components'] != 1 or candidate['boundary_edges'] or candidate['other_nonmanifold_edges']:
        raise ValueError('probe topology does not meet exact geometry checks')
    for axis in range(3):
        if abs(source['bounds_min'][axis] - candidate['bounds_min'][axis]) > 0.03 or abs(source['bounds_max'][axis] - candidate['bounds_max'][axis]) > 0.03:
            raise ValueError('probe bounds differ from source by over 3 cm')

    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / OUTPUT_NAME
    bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB',
                              use_selection=True, export_apply=True)
    output_hash = sha256(output.read_bytes()).hexdigest()
    saved_obj = load_one_mesh(output)
    saved = topology(saved_obj)
    if saved['triangles'] != args.target_triangles or saved['vertices'] != candidate['vertices'] or saved['connected_components'] != 1 or saved['boundary_edges'] or saved['other_nonmanifold_edges'] or saved['materials'] or saved['uv_layers']:
        raise ValueError('saved GLB failed geometry-only readback checks')
    render_clay(saved_obj, args.output_dir)
    report = dict(schema='nali-geometry-probe-v1', source_glb=str(args.source.resolve()),
                  source_sha256=source_hash, blender_version=bpy.app.version_string,
                  voxel_size_m=args.voxel_size, target_triangles=args.target_triangles,
                  source=source, pre_export_candidate=candidate, saved_candidate=saved,
                  output_glb=OUTPUT_NAME, output_sha256=output_hash,
                  preview_files=[f'Nali_deform_probe_{name}_ue5.png'
                                 for name in ('front', 'right', 'back', 'left')],
                  limitations=['Geometry-only experiment, not a skinning-ready retopology',
                               'No UVs, PBR materials, animation, skeleton, cloth or physics',
                               'Automated topology checks do not prove four-arm deformation quality'])
    (args.output_dir / 'Nali_deform_probe_ue5.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(output=str(output), sha256=output_hash, source=source,
                          saved_candidate=saved), indent=2), flush=True)


if __name__ == '__main__':
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(arguments)
