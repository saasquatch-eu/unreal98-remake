"""Apply the private modern lighting plan using the installed UE5 editor."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
from datetime import datetime, timezone
import sys

import unreal

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/editor'))


def component(actor,kind):
    components=actor.get_components_by_class(kind)
    if len(components)!=1:raise RuntimeError('expected one lighting component')
    return components[0]


def configure_chunk(asset,entry,meshes):
    build=meshes.get_lod_build_settings(asset,0)
    build.max_lumen_mesh_cards=64 if entry['nanite'] else 0
    build.distance_field_resolution_scale=2.0 if entry['nanite'] else 0.0
    build.generate_distance_field_as_if_two_sided=entry['nanite']
    meshes.set_lod_build_settings(asset,0,build)
    if entry['nanite']:
        nanite=meshes.get_nanite_settings(asset)
        nanite.enabled=True;nanite.keep_percent_triangles=1.0;nanite.trim_relative_error=0.0
        nanite.fallback_target=unreal.NaniteFallbackTarget.PERCENT_TRIANGLES
        nanite.fallback_percent_triangles=1.0;nanite.fallback_relative_error=0.0;nanite.position_precision=8
        meshes.set_nanite_settings(asset,nanite,True)


def mesh_chunks(plan,folder,report,report_path):
    build_asset=runpy.run_path(str(ROOT/'tools/editor/import_intro.py'))['build_asset']
    apply_meshes=runpy.run_path(str(ROOT/'tools/editor/apply_intro_materials.py'))['apply_meshes']
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    meshes=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for entry in plan['chunks']:
        data=json.loads((folder/entry['source_file']).read_text())
        asset=build_asset(data,entry['asset_path'],entry['triangle_count'])
        materials=[unreal.load_asset(path) for path in entry['materials']]
        if not all(materials):raise RuntimeError('chunk material missing')
        record=dict(entry,materials=list(range(len(materials))))
        apply_meshes(dict(meshes=[record]),folder,materials)
        configure_chunk(asset,entry,meshes)
        if asset.get_num_triangles(0)!=entry['triangle_count']:raise RuntimeError('Nanite fallback changed triangle count')
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset):raise RuntimeError('chunk save failed')
        actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
        actor.set_actor_label(entry['name']);actor.set_folder_path('Unreal_ue5/LumenGeometry')
        c=actor.static_mesh_component;c.set_static_mesh(asset);c.set_collision_profile_name('NoCollision')
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_cast_shadow(entry['nanite'])
        c.set_editor_property('affect_distance_field_lighting',entry['nanite'])
        report['chunks'].append(dict(name=entry['name'],triangles=asset.get_num_triangles(0)))
        report_path.write_text(json.dumps(report,indent=2))
    reference=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Unreal_ue5')
    reference.modify();reference.static_mesh_component.modify()
    reference.static_mesh_component.set_visibility(False)
    reference.static_mesh_component.set_editor_property('affect_distance_field_lighting',False)
    reference.set_folder_path('Unreal_ue5/SourceReference')


def lighting(plan):
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors=actors.get_all_level_actors();settings=plan['lighting']
    sun=next(a for a in all_actors if a.get_actor_label()=='Unreal_InspectionSun_ue5')
    c=component(sun,unreal.DirectionalLightComponent);c.modify()
    unreal.log('UR_SUN_BEFORE '+str(c.get_editor_property('intensity')))
    c.set_intensity(settings['sun_lux']);c.set_world_rotation(unreal.Rotator(**settings['sun_rotation']),False,False)
    c.set_light_source_angle(settings['sun_source_angle']);c.set_light_source_soft_angle(5)
    c.set_editor_property('cast_cloud_shadows',True);c.set_editor_property('cloud_shadow_strength',0.5)
    sun.set_actor_label('Unreal_KeyLight_ue5')
    sky=next(a for a in all_actors if a.get_actor_label()=='Unreal_InspectionSky_ue5')
    c=component(sky,unreal.SkyLightComponent);c.modify();c.set_intensity(1.0)
    c.set_editor_property('real_time_capture',True);sky.set_actor_label('Unreal_SkyLight_ue5')
    atmosphere=next(a for a in all_actors if a.get_actor_label()=='Unreal_InspectionAtmosphere_ue5')
    component(atmosphere,unreal.SkyAtmosphereComponent);atmosphere.set_actor_label('Unreal_Atmosphere_ue5')
    cloud=actors.spawn_actor_from_class(unreal.VolumetricCloud,unreal.Vector())
    cloud.set_actor_label('Unreal_Clouds_ue5');c=component(cloud,unreal.VolumetricCloudComponent)
    source=c.get_editor_property('material')
    cloud_path='/Game/Unreal/Materials/UE5/Unreal_Clouds_ue5'
    if unreal.EditorAssetLibrary.does_asset_exist(cloud_path):raise RuntimeError('cloud material destination exists')
    material=unreal.EditorAssetLibrary.duplicate_asset(source.get_path_name().split('.')[0],cloud_path)
    if not material:raise RuntimeError('cloud instance duplication failed')
    for name,value in [('Cloud_GlobalCoverage',settings['cloud_coverage']),('Cloud_GlobalDensity',settings['cloud_density'])]:
        before=unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material,name)
        unreal.log('UR_CLOUD_BEFORE '+name+' '+str(before))
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material,name,value)
        if abs(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material,name)-value)>1e-5:raise RuntimeError('cloud parameter readback differs')
    if not unreal.EditorAssetLibrary.save_loaded_asset(material):raise RuntimeError('cloud save failed')
    c.set_editor_property('material',material);c.set_layer_bottom_altitude(3);c.set_layer_height(5)
    volume=next(a for a in all_actors if a.get_actor_label()=='Unreal_InspectionExposure_ue5')
    volume.modify();pp=volume.get_editor_property('settings')
    unreal.log('UR_EXPOSURE_BEFORE '+str({p:pp.get_editor_property(p) for p in ('auto_exposure_min_brightness','auto_exposure_max_brightness','override_auto_exposure_min_brightness','override_auto_exposure_max_brightness','auto_exposure_bias')}))
    pp.set_editor_property('override_auto_exposure_bias',True);pp.set_editor_property('auto_exposure_bias',settings['exposure_bias'])
    for name,value in [('dynamic_global_illumination_method',unreal.DynamicGlobalIlluminationMethod.LUMEN),('reflection_method',unreal.ReflectionMethod.LUMEN),('lumen_scene_lighting_quality',2.0),('lumen_final_gather_quality',2.0),('lumen_reflection_quality',2.0),('motion_blur_amount',0.0)]:
        pp.set_editor_property('override_'+name,True);pp.set_editor_property(name,value)
    volume.set_editor_property('settings',pp);volume.set_actor_label('Unreal_LumenExposure_ue5')
    fog=actors.spawn_actor_from_class(unreal.ExponentialHeightFog,unreal.Vector(0,0,1800))
    fog.set_actor_label('Unreal_Fog_ue5');c=component(fog,unreal.ExponentialHeightFogComponent)
    unreal.log('UR_FOG_BEFORE '+str(c.get_editor_property('fog_density')))
    c.set_fog_density(settings['fog_density']);c.set_fog_height_falloff(0.2);c.set_start_distance(1500)
    c.set_volumetric_fog(True);c.set_volumetric_fog_scattering_distribution(0.2)
    c.set_volumetric_fog_extinction_scale(1.0)
    for entry in plan['lights']:
        actor=actors.spawn_actor_from_class(unreal.PointLight,unreal.Vector(*entry['location']))
        actor.set_actor_label(entry['name']);actor.set_folder_path('Unreal_ue5/SourceLights')
        c=component(actor,unreal.PointLightComponent);c.set_mobility(unreal.ComponentMobility.MOVABLE)
        c.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
        c.set_use_inverse_squared_falloff(True);c.set_intensity(entry['intensity_lumens'])
        c.set_attenuation_radius(entry['attenuation_radius']);c.set_source_radius(15)
        c.set_light_color(unreal.LinearColor(*entry['color_linear'],1.0),True)
        c.set_cast_shadows(entry['cast_shadows'])


def run(plan_path):
    plan_path=Path(plan_path);plan=json.loads(plan_path.read_text());folder=plan_path.parent
    if Path(unreal.Paths.get_project_file_path()).stem!='UnrealGoldRemake':raise RuntimeError('wrong project')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():raise RuntimeError('stop PIE and save first')
    expected={'r.DynamicGlobalIlluminationMethod':1,'r.ReflectionMethod':1,'r.GenerateMeshDistanceFields':1,'r.Lumen.HardwareRayTracing':0,'r.Shadow.Virtual.Enable':1}
    for name,value in expected.items():
        if unreal.SystemLibrary.get_console_variable_int_value(name)!=value:raise RuntimeError('restart with the configured renderer: '+name)
    material_path=Path(plan['material_plan'])
    if hashlib.sha256(material_path.read_bytes()).hexdigest()!=plan['material_sha256']:raise RuntimeError('material provenance changed')
    runpy.run_path(str(ROOT/'tools/editor/verify_intro_materials.py'))['verify'](material_path,ROOT/'.local/logs/unreal-materials-verified.json')
    names={a.get_actor_label() for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    if 'Unreal_KeyLight_ue5' in names:raise RuntimeError('lighting already applied')
    for entry in plan['chunks']:
        if unreal.EditorAssetLibrary.does_asset_exist(entry['asset_path']):raise RuntimeError('chunk destination already exists')
        if hashlib.sha256((folder/entry['source_file']).read_bytes()).hexdigest()!=entry['source_sha256']:raise RuntimeError('chunk checksum changed')
    # Copy the saved baseline before creating assets; never replace a recovery point.
    backup=ROOT/'.local/lighting-recovery'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True)
    content=Path(unreal.Paths.project_content_dir()).resolve()/'Unreal'
    for directory in ('Maps','Meshes'):
        shutil.copytree(content/directory,backup/directory)
    shutil.copy2(ROOT/'ue5/UnrealGoldRemake/Config/DefaultEngine.ini',backup/'DefaultEngine.ini')
    report_path=ROOT/'.local/logs/unreal-lumen-apply.json';report=dict(status='running',backup=str(backup),chunks=[])
    report_path.write_text(json.dumps(report))
    mesh_chunks(plan,folder,report,report_path)
    lighting(plan)
    if not level.save_current_level():raise RuntimeError('lighting map save failed')
    report['status']='success';report['point_lights']=len(plan['lights']);report_path.write_text(json.dumps(report,indent=2))
    unreal.log('UR_LUMEN_APPLIED')


if __name__=='__main__':
    run(ROOT/'data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json')
