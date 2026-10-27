"""Verify saved geometry, full UV0 and triangle material assignments after reload."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import struct

import unreal

ROOT=Path(__file__).resolve().parents[2]


def float32(value):return struct.unpack('<f',struct.pack('<f',value))[0]


def record(points,uvs,material_id):
    corners=tuple(tuple(float32(x) for x in list(p)+list(uv)) for p,uv in zip(points,uvs))
    return material_id,min(corners,corners[1:]+corners[:1],corners[2:]+corners[:2])


def verify(plan_path,report_path):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());folder=plan_path.parent
    if Path(unreal.Paths.get_project_file_path()).stem!='UnrealGoldRemake':raise RuntimeError('wrong project')
    # Existing verifier switches away, reloads, and checks every position/winding/actor.
    runpy.run_path(str(ROOT/'tools/editor/verify_intro.py'))['verify'](plan['original_recipe'],ROOT/'.local/logs/unreal-ue5-verified.json')
    report=dict(status='success',plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),textures=[],meshes=[],deferred=plan['deferred'])
    for entry in plan['textures']:
        texture=unreal.load_asset(entry['asset_path'])
        if (int(texture.blueprint_get_size_x()),int(texture.blueprint_get_size_y()))!=(entry['width'],entry['height']):raise RuntimeError('saved texture size differs')
        if not texture.get_editor_property('srgb'):raise RuntimeError('texture color space differs')
        report['textures'].append(dict(path=entry['asset_path'],width=entry['width'],height=entry['height']))
    for entry in plan['materials']:
        if entry.get('deferred'):
            material=unreal.load_asset(entry['path'])
            if unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material,'PreviewOpacity')!=0:raise RuntimeError('deferred effect is not transparent')
            continue
        if not entry['texture']:continue
        material=unreal.load_asset(entry['path'])
        value=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material,'OriginalColor')
        expected=next(t['asset_path'] for t in plan['textures'] if t['path']==entry['texture'])
        if not value or value.get_path_name().split('.')[0]!=expected:raise RuntimeError('saved material texture differs')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for entry in plan['meshes']:
        data=json.loads((folder/entry['source_file']).read_text());expected=Counter()
        for tri,material_id in zip(data['triangles'],data['material_ids']):
            expected[record([data['vertices'][i] for i in tri],[data['uv0'][i] for i in tri],material_id)]+=1
        asset=unreal.load_asset(entry['asset_path']);options=unreal.GeometryScriptCopyMeshFromAssetOptions();options.apply_build_settings=False
        lod=unreal.GeometryScriptMeshReadLOD();lod.lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL
        mesh,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(asset,unreal.DynamicMesh(),options,lod)
        if outcome!=unreal.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError('mesh readback failed')
        actual=Counter()
        for i in range(mesh.get_triangle_count()):
            valid,a,b,c=unreal.GeometryScript_MeshQueries.get_triangle_positions(mesh,i)
            u,v,w,uv_valid=unreal.GeometryScript_MeshQueries.get_triangle_u_vs(mesh,0,i)
            material_id,material_valid=unreal.GeometryScript_Materials.get_triangle_material_id(mesh,i)
            if not (valid and uv_valid and material_valid):raise RuntimeError('missing mesh readback attribute')
            actual[record([(p.x,p.y,p.z) for p in (a,b,c)],[(p.x,p.y) for p in (u,v,w)],material_id)]+=1
        if actual!=expected:raise RuntimeError('saved UVs or material IDs differ for '+entry['name'])
        paths=[str(s.material_interface.get_path_name()).split('.')[0] for s in asset.static_materials]
        expected_paths=[plan['materials'][i]['path'] for i in entry['materials']]
        if paths!=expected_paths:raise RuntimeError('saved material slots differ')
        actor=next(a for a in actors if a.get_actor_label()==entry['name'])
        overrides=actor.static_mesh_component.get_editor_property('override_materials')
        if any(overrides):raise RuntimeError('actor overrides hide original material slots')
        report['meshes'].append(dict(name=entry['name'],triangle_count=mesh.get_triangle_count(),uvs_and_material_ids_match=True,material_slots=len(paths)))
    exposure=next(a for a in actors if a.get_actor_label()=='Unreal_InspectionExposure_ue5').get_editor_property('settings')
    if exposure.get_editor_property('auto_exposure_method')!=unreal.AutoExposureMethod.AEM_MANUAL or exposure.get_editor_property('auto_exposure_bias')!=-13:raise RuntimeError('fixed exposure did not persist')
    report['exposure']=dict(method='manual',bias=-13)
    Path(report_path).write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('UR_MATERIAL_VERIFY_SUCCESS')
    return report


if __name__=='__main__':
    verify(ROOT/'data/converted/Unreal/Maps/Unreal/materials-ready/Unreal.materials.json',ROOT/'.local/logs/unreal-materials-verified.json')
