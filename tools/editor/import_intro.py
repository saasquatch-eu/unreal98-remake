"""Run inside the existing Unreal Editor Python console. Creates new assets only.

py import runpy; runpy.run_path('/absolute/repo/tools/editor/import_intro.py',run_name='__main__')
"""

import hashlib
import json
from pathlib import Path
import traceback
import sys

import unreal

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ue1_converter.ue5_prepare import validate_buffers


def build_asset(data,path,expected_count):
    validate_buffers(data)
    buffers=unreal.GeometryScriptSimpleMeshBuffers()
    buffers.vertices=[unreal.Vector(*v) for v in data["vertices"]]
    buffers.normals=[unreal.Vector(*n) for n in data["normals"]]
    buffers.uv0=[unreal.Vector2D(*uv) for uv in data["uv0"]]
    buffers.triangles=[unreal.IntVector(*t) for t in data["triangles"]]
    dynamic=unreal.DynamicMesh()
    unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic,buffers)
    if dynamic.get_triangle_count()!=expected_count:raise RuntimeError("dynamic mesh lost triangles")
    options=unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.enable_recompute_normals=False;options.enable_recompute_tangents=False
    options.enable_nanite=False;options.enable_collision=False;options.use_original_vertex_order=True
    asset,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic,path,options)
    if outcome!=unreal.GeometryScriptOutcomePins.SUCCESS:raise RuntimeError(f"mesh creation failed: {outcome}")
    if not isinstance(asset,unreal.StaticMesh):raise RuntimeError("import produced a non-mesh")
    smes=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    build=smes.get_lod_build_settings(asset,0)
    build.remove_degenerates=False;build.recompute_normals=False;build.recompute_tangents=False
    build.generate_lightmap_u_vs=False
    smes.set_lod_build_settings(asset,0,build)
    if asset.get_num_triangles(0)!=expected_count:raise RuntimeError("static mesh triangle count changed")
    return asset


def smoke_test(report_path):
    path='/Game/Unreal/Meshes/Diagnostics/DirectBuildProbe_ue5'
    if unreal.EditorAssetLibrary.does_asset_exist(path):raise RuntimeError("smoke probe already exists")
    data=dict(vertices=[[11,23,47],[101,23,47],[11,211,47]],normals=[[0,0,1]]*3,
              uv0=[[0,0],[1,0],[0,1]],triangles=[[0,1,2]])
    asset=build_asset(data,path,1)
    bounds=asset.get_bounding_box()
    result=dict(status='success',triangle_count=asset.get_num_triangles(0),
                bounds=dict(minimum=[bounds.min.x,bounds.min.y,bounds.min.z],maximum=[bounds.max.x,bounds.max.y,bounds.max.z]))
    Path(report_path).write_text(json.dumps(result,indent=2))
    unreal.log('UR_DIRECT_SMOKE_SUCCESS')


def add_inspection_lighting():
    """Temporary neutral lighting; never intended to reproduce the original mood."""
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(),unreal.Rotator(pitch=-45,yaw=80,roll=0));sun.set_actor_label('Unreal_InspectionSun_ue5')
    c=sun.get_component_by_class(unreal.DirectionalLightComponent)
    unreal.log('UR_SUN_BASELINE '+str(c.get_editor_property('intensity')))
    c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_intensity(100000);c.set_editor_property('atmosphere_sun_light',True)
    a=actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector());a.set_actor_label('Unreal_InspectionAtmosphere_ue5')
    s=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector());s.set_actor_label('Unreal_InspectionSky_ue5')
    c=s.get_component_by_class(unreal.SkyLightComponent)
    unreal.log('UR_SKY_BASELINE '+str(c.get_editor_property('intensity')))
    c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_editor_property('real_time_capture',True);c.set_intensity(1)
    p=actors.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector());p.set_actor_label('Unreal_InspectionExposure_ue5')
    settings=p.get_editor_property('settings')
    unreal.log('UR_EXPOSURE_BASELINE '+str({k:settings.get_editor_property(k) for k in ('auto_exposure_min_brightness','auto_exposure_max_brightness','override_auto_exposure_min_brightness','override_auto_exposure_max_brightness','auto_exposure_bias')}))
    p.set_editor_property('unbound',True)
    settings.set_editor_property('override_auto_exposure_min_brightness',True);settings.set_editor_property('override_auto_exposure_max_brightness',True)
    extended=unreal.SystemLibrary.get_console_variable_int_value('r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange')!=0
    settings.set_editor_property('auto_exposure_min_brightness',10 if extended else 2**10)
    settings.set_editor_property('auto_exposure_max_brightness',16 if extended else 2**16)
    p.set_editor_property('settings',settings)


def run(recipe_path,report_path):
    recipe_path=Path(recipe_path);report_path=Path(report_path)
    plan=json.loads(recipe_path.read_text())
    project=Path(unreal.Paths.get_project_file_path())
    if project.stem!=plan["project_name"]:raise RuntimeError("wrong Unreal project")
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor():raise RuntimeError("stop PIE before importing")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():raise RuntimeError("save open map work before importing")
    geometry=Path(plan["geometry_file"])
    if hashlib.sha256(geometry.read_bytes()).hexdigest()!=plan["geometry_sha256"]:
        raise RuntimeError("geometry checksum changed")
    paths=[plan["map_path"]]+[m["asset_path"] for m in plan["meshes"]]
    if any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in paths):
        raise RuntimeError("destination map or mesh exists; no assets are overwritten")
    for mesh in plan["meshes"]:
        source=recipe_path.parent/mesh["source_file"]
        if hashlib.sha256(source.read_bytes()).hexdigest()!=mesh["source_sha256"]:
            raise RuntimeError("mesh source checksum changed")
        validate_buffers(json.loads(source.read_text()))
    material=unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial')
    if material is None:raise RuntimeError("required existing neutral material is unavailable")
    smes=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report=dict(status="running",project=str(project),map=plan["map_path"],meshes=[],scale=plan["centimeters_per_source_unit"])
    report_path.write_text(json.dumps(report,indent=2))
    loaded=[]
    for mesh in plan["meshes"]:
        data=json.loads((recipe_path.parent/mesh["source_file"]).read_text())
        asset=build_asset(data,mesh["asset_path"],mesh["triangle_count"])
        count=asset.get_num_triangles(0)
        if count!=mesh["triangle_count"]:raise RuntimeError(f"triangle count changed: {mesh['name']} {count} vs {mesh['triangle_count']}")
        bounds=asset.get_bounding_box()
        observed=dict(minimum=[bounds.min.x,bounds.min.y,bounds.min.z],maximum=[bounds.max.x,bounds.max.y,bounds.max.z])
        for key in observed:
            if any(abs(a-b)>0.02 for a,b in zip(observed[key],mesh["expected_bounds"][key])):
                raise RuntimeError(f"import coordinate mismatch: {mesh['name']} {observed}")
        smes.remove_collisions(asset)
        if not asset.static_materials:asset.add_material(material)
        for index in range(len(asset.static_materials)):asset.set_material(index,material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset):raise RuntimeError("mesh save failed")
        loaded.append((mesh,asset))
        report["meshes"].append(dict(name=mesh["name"],path=asset.get_path_name(),triangle_count=count,bounds=observed))
    if not level.new_level(plan["map_path"]):raise RuntimeError("new level creation failed")
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for mesh,asset in loaded:
        actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*mesh["actor_location"]))
        actor.set_actor_label(mesh["name"])
        component=actor.static_mesh_component
        component.set_static_mesh(asset)
        component.set_collision_profile_name('NoCollision')
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_mobility(unreal.ComponentMobility.MOVABLE if mesh["role"]=="mover" else unreal.ComponentMobility.STATIC)
    camera=plan["camera"]
    pose=unreal.Rotator(**camera["rotation"])
    actor=actors.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*camera["location"]),pose)
    actor.set_actor_label(camera["name"]);actor.camera_component.set_field_of_view(camera["diagnostic_fov"])
    add_inspection_lighting()
    if not level.save_current_level():raise RuntimeError("level save failed")
    unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).spawn_registered_tab_by_id('LevelEditorViewport')
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(unreal.Vector(*camera["location"]),pose)
    level.set_level_viewport_fov(camera['diagnostic_fov'],level.get_active_viewport_config_key())
    level.editor_set_viewport_realtime(True)
    report["status"]="success"
    report["limitations"]=plan["limitations"]
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    unreal.log('UR_IMPORT_SUCCESS '+str(report_path))
    return report


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    recipe=root/'data/converted/Unreal/Maps/Unreal/ue5-import-ready/Unreal.import.json'
    report=root/'.local/logs/unreal-ue5-import-result.json'
    try:run(recipe,report)
    except Exception:
        report.write_text(json.dumps(dict(status='failed',traceback=traceback.format_exc()),indent=2))
        unreal.log_error('UR_IMPORT_FAILED '+traceback.format_exc())
        raise
