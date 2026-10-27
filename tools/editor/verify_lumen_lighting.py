"""Reload and verify the active Lumen pass and its lossless render representation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy

import unreal

ROOT=Path(__file__).resolve().parents[2]


def verify(plan_path,report_path):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());folder=plan_path.parent
    material_path=Path(plan['material_plan'])
    if hashlib.sha256(material_path.read_bytes()).hexdigest()!=plan['material_sha256']:raise RuntimeError('material provenance changed')
    for entry in plan['chunks']:
        if hashlib.sha256((folder/entry['source_file']).read_bytes()).hexdigest()!=entry['source_sha256']:raise RuntimeError('chunk checksum changed')
    stage=runpy.run_path(str(ROOT/'tools/editor/verify_intro_materials.py'))
    baseline=stage['verify'](plan['material_plan'],ROOT/'.local/logs/unreal-materials-verified.json',check_inspection_exposure=False,exposure_actor_label='Unreal_LumenExposure_ue5')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_name={a.get_actor_label():a for a in actors}
    reference=by_name['Unreal_ue5'].static_mesh_component
    if reference.is_visible() or reference.get_editor_property('affect_distance_field_lighting'):raise RuntimeError('reference mesh renders twice')
    material_plan=json.loads(material_path.read_text())
    world=next(m for m in material_plan['meshes'] if m['role']=='world')
    data=json.loads((material_path.parent/world['source_file']).read_text())
    paths=[material_plan['materials'][i]['path'] for i in world['materials']]
    # UObject identity resolves harmless FName display-case aliases after restart.
    materials=[unreal.load_asset(p) for p in paths]
    expected=Counter()
    for tri,index in zip(data['triangles'],data['material_ids']):expected[stage['record']([data['vertices'][i] for i in tri],[data['uv0'][i] for i in tri],materials[index].get_path_name().casefold())]+=1
    actual=Counter();meshes=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report=dict(status='success',plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),chunks=[],source_lights=[])
    for entry in plan['chunks']:
        actor=by_name[entry['name']];c=actor.static_mesh_component;asset=c.static_mesh
        if not c.is_visible() or c.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION:raise RuntimeError('chunk visibility/collision changed')
        if c.get_editor_property('cast_shadow')!=entry['nanite']:raise RuntimeError('transparent chunk casts shadows')
        pos=actor.get_actor_location();rot=actor.get_actor_rotation();scale=actor.get_actor_scale3d()
        if any(abs(v)>1e-6 for v in (pos.x,pos.y,pos.z,rot.pitch,rot.yaw,rot.roll)) or any(abs(v-1)>1e-6 for v in (scale.x,scale.y,scale.z)):raise RuntimeError('chunk transform changed')
        if asset.get_num_triangles(0)!=entry['triangle_count']:raise RuntimeError('fallback triangle count changed')
        nanite=meshes.get_nanite_settings(asset)
        if bool(nanite.enabled)!=entry['nanite']:raise RuntimeError('Nanite configuration differs')
        if entry['nanite'] and (nanite.fallback_target!=unreal.NaniteFallbackTarget.PERCENT_TRIANGLES or nanite.fallback_percent_triangles!=1 or nanite.keep_percent_triangles!=1 or nanite.trim_relative_error!=0):raise RuntimeError('Nanite full-detail settings differ')
        if c.get_editor_property('affect_distance_field_lighting')!=entry['nanite']:raise RuntimeError('distance-field participation differs')
        build=meshes.get_lod_build_settings(asset,0)
        if not build.use_full_precision_u_vs or build.max_lumen_mesh_cards!=(64 if entry['nanite'] else 0) or build.distance_field_resolution_scale!=(2 if entry['nanite'] else 0):raise RuntimeError('chunk build settings differ')
        options=unreal.GeometryScriptCopyMeshFromAssetOptions();options.apply_build_settings=False
        lod=unreal.GeometryScriptMeshReadLOD();lod.lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL
        mesh,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(asset,unreal.DynamicMesh(),options,lod)
        if outcome!=unreal.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError('chunk readback failed')
        slots=[s.material_interface for s in asset.static_materials]
        if slots!=[unreal.load_asset(p) for p in entry['materials']]:raise RuntimeError('chunk material slots differ')
        for i in range(mesh.get_triangle_count()):
            valid,a,b,d=unreal.GeometryScript_MeshQueries.get_triangle_positions(mesh,i)
            u,v,w,uv_valid=unreal.GeometryScript_MeshQueries.get_triangle_u_vs(mesh,0,i)
            index,mat_valid=unreal.GeometryScript_Materials.get_triangle_material_id(mesh,i)
            if not (valid and uv_valid and mat_valid):raise RuntimeError('chunk triangle attribute missing')
            actual[stage['record']([(p.x,p.y,p.z) for p in (a,b,d)],[(p.x,p.y) for p in (u,v,w)],slots[index].get_path_name().casefold())]+=1
        report['chunks'].append(dict(name=entry['name'],triangles=mesh.get_triangle_count(),nanite=entry['nanite']))
    if actual!=expected:raise RuntimeError('visible world positions, winding, UVs or material assignment changed')
    for entry in plan['lights']:
        actor=by_name[entry['name']];c=actor.get_component_by_class(unreal.PointLightComponent)
        p=actor.get_actor_location()
        if any(abs(a-b)>0.02 for a,b in zip((p.x,p.y,p.z),entry['location'])):raise RuntimeError('source light moved')
        if c.get_editor_property('mobility')!=unreal.ComponentMobility.MOVABLE or abs(c.get_editor_property('attenuation_radius')-entry['attenuation_radius'])>0.02:raise RuntimeError('source light mobility/radius differs')
        if abs(c.get_editor_property('intensity')-entry['intensity_lumens'])>0.05 or c.get_editor_property('cast_shadows')!=entry['cast_shadows']:raise RuntimeError('source light intensity/shadow differs')
        report['source_lights'].append(dict(name=entry['name'],cast_shadows=entry['cast_shadows']))
    expected_cvars={'r.DynamicGlobalIlluminationMethod':1,'r.ReflectionMethod':1,'r.GenerateMeshDistanceFields':1,'r.Lumen.HardwareRayTracing':0,'r.Shadow.Virtual.Enable':1,'r.AntiAliasingMethod':4,'r.Nanite':1}
    report['renderer']={k:unreal.SystemLibrary.get_console_variable_int_value(k) for k in expected_cvars}
    if report['renderer']!=expected_cvars:raise RuntimeError('renderer configuration differs')
    volume=by_name['Unreal_LumenExposure_ue5'];pp=volume.get_editor_property('settings')
    if not pp.get_editor_property('override_motion_blur_amount') or pp.get_editor_property('motion_blur_amount')!=0:raise RuntimeError('static inspection motion blur differs')
    if pp.get_editor_property('auto_exposure_method')!=unreal.AutoExposureMethod.AEM_MANUAL or pp.get_editor_property('reflection_method')!=unreal.ReflectionMethod.LUMEN:raise RuntimeError('manual exposure or Lumen reflections differ')
    if pp.get_editor_property('auto_exposure_bias')!=plan['lighting']['exposure_bias'] or pp.get_editor_property('dynamic_global_illumination_method')!=unreal.DynamicGlobalIlluminationMethod.LUMEN:raise RuntimeError('Lumen post process differs')
    if not by_name['Unreal_Fog_ue5'].get_component_by_class(unreal.ExponentialHeightFogComponent).get_editor_property('enable_volumetric_fog'):raise RuntimeError('volumetric fog is disabled')
    cloud=by_name['Unreal_Clouds_ue5'].get_component_by_class(unreal.VolumetricCloudComponent).get_editor_property('material')
    if not cloud.get_path_name().startswith('/Game/Unreal/'):raise RuntimeError('cloud material was not localized')
    for name,value in [('Cloud_GlobalCoverage',plan['lighting']['cloud_coverage']),('Cloud_GlobalDensity',plan['lighting']['cloud_density'])]:
        if abs(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(cloud,name)-value)>1e-5:raise RuntimeError('cloud parameters differ')
    sun=by_name['Unreal_KeyLight_ue5'].get_component_by_class(unreal.DirectionalLightComponent)
    if sun.get_editor_property('intensity')!=plan['lighting']['sun_lux'] or not sun.get_editor_property('cast_cloud_shadows'):raise RuntimeError('key light differs')
    sky=by_name['Unreal_SkyLight_ue5'].get_component_by_class(unreal.SkyLightComponent)
    if not sky.get_editor_property('real_time_capture'):raise RuntimeError('skylight capture is disabled')
    report['visible_world_triangles']=sum(actual.values());report['movable_mover_triangles']=sum(m['triangle_count'] for m in baseline['meshes'] if m['name']!='Unreal_ue5')
    Path(report_path).write_text(json.dumps(report,indent=2)+'\n');unreal.log('UR_LUMEN_VERIFY_SUCCESS')
    return report


if __name__=='__main__':
    verify(ROOT/'data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json',ROOT/'.local/logs/unreal-lumen-verified.json')
