"""Read back a saved intro map and verify geometry, placement and collision state.

Run in Unreal's existing Python console after import_intro.py. Reports stay private.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

import unreal


def triangle_key(vertices):
    """Match cyclic order independently of triangle IDs, at StaticMesh float precision."""
    points=tuple(tuple(struct.unpack('<f',struct.pack('<f',v))[0] for v in p) for p in vertices)
    return min(points,points[1:]+points[:1],points[2:]+points[:2])


def verify(recipe_path,report_path):
    recipe_path=Path(recipe_path)
    plan=json.loads(recipe_path.read_text())
    if Path(unreal.Paths.get_project_file_path()).stem!=plan['project_name']:
        raise RuntimeError('wrong project')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor():raise RuntimeError('stop PIE before verification')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():raise RuntimeError('save map before verification')
    # Switch away first so verification observes the saved map's actors.
    unreal.EditorLoadingAndSavingUtils.load_map('/Engine/Maps/Entry')
    world=unreal.EditorLoadingAndSavingUtils.load_map(plan['map_path'])
    if not world or world.get_path_name()!=plan['map_path']+'.'+plan['map_path'].rsplit('/',1)[1]:
        raise RuntimeError('saved map did not reload')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    report=dict(status='success',map=world.get_path_name(),recipe_sha256=hashlib.sha256(recipe_path.read_bytes()).hexdigest(),meshes=[])
    for entry in plan['meshes']:
        raw=(recipe_path.parent/entry['source_file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['source_sha256']:raise RuntimeError('buffer checksum changed')
        source=json.loads(raw)
        expected=Counter(triangle_key([source['vertices'][i] for i in t]) for t in source['triangles'])
        asset=unreal.load_asset(entry['asset_path'])
        options=unreal.GeometryScriptCopyMeshFromAssetOptions();options.apply_build_settings=False
        lod=unreal.GeometryScriptMeshReadLOD();lod.lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL
        mesh,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(asset,unreal.DynamicMesh(),options,lod)
        if outcome!=unreal.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError('mesh readback failed')
        count=asset.get_num_triangles(0)
        if count!=entry['triangle_count'] or mesh.get_triangle_count()!=count:raise RuntimeError('saved triangle count changed')
        actual=Counter()
        for index in range(count):
            valid,a,b,c=unreal.GeometryScript_MeshQueries.get_triangle_positions(mesh,index)
            if not valid:raise RuntimeError('invalid readback triangle')
            actual[triangle_key([(v.x,v.y,v.z) for v in (a,b,c)])]+=1
        if actual!=expected:raise RuntimeError('saved triangle positions or winding changed')
        actor=next(a for a in actors if a.get_actor_label()==entry['name'])
        position=actor.get_actor_location()
        if any(abs(a-b)>0.02 for a,b in zip((position.x,position.y,position.z),entry['actor_location'])):
            raise RuntimeError('saved actor placement changed')
        rotation=actor.get_actor_rotation();scale=actor.get_actor_scale3d()
        if any(abs(v)>0.001 for v in (rotation.pitch,rotation.yaw,rotation.roll)) or any(abs(v-1)>0.001 for v in (scale.x,scale.y,scale.z)):
            raise RuntimeError('unexpected actor rotation or scale')
        component=actor.static_mesh_component
        if component.static_mesh!=asset or component.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION:
            raise RuntimeError('saved mesh assignment or collision mode changed')
        uv_count=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_num_uv_channels(asset,0)
        if uv_count<1:raise RuntimeError('saved mesh has no UV channel')
        report['meshes'].append(dict(name=entry['name'],triangle_count=count,positions_and_winding_match=True,uv_channels=uv_count))
    camera=next(a for a in actors if a.get_actor_label()==plan['camera']['name'])
    level.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation(),level.get_active_viewport_config_key())
    level.set_level_viewport_fov(plan['camera']['diagnostic_fov'],level.get_active_viewport_config_key())
    report['dirty_maps']=[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    Path(report_path).write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('UR_VERIFY_SUCCESS '+str(report_path))
    return report


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    verify(root/'data/converted/Unreal/Maps/Unreal/ue5-import-ready/Unreal.import.json',
           root/'.local/logs/unreal-ue5-verified.json')
