"""Add checked source moons with camera-centered, source-rate yaw previews."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import shutil
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ue1_converter.sky_prepare import digest
from ue1_converter.ue5_prepare import validate_buffers

PARENT = '/Game/Unreal/Materials/UE5/Unreal_Moons_ue5'
BASE = '/Game/Unreal/Materials/UE5/Unreal_sky_stars_ue5'


def checked_plan(path):
    path = Path(path); plan = json.loads(path.read_text())
    if plan['schema_version'] != 1 or digest(plan['sky_plan']) != plan['sky_sha256']: raise RuntimeError('moon sky provenance differs')
    for package in plan['packages']:
        if digest(package['file']) != package['sha256']: raise RuntimeError('moon package provenance differs')
    for entry in plan['textures'] + plan['meshes']:
        if digest(path.parent / entry['source_file']) != entry['source_sha256']: raise RuntimeError('moon buffer/image provenance differs')
    for entry in plan['meshes']: validate_buffers(json.loads((path.parent / entry['source_file']).read_text()))
    return plan


def create_parent():
    # Reuse the checked sky's source-image and camera-follow graph.
    material = unreal.EditorAssetLibrary.duplicate_asset(BASE, PARENT)
    if not material: raise RuntimeError('moon parent duplication failed')
    edit = unreal.MaterialEditingLibrary
    centered = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    def node(cls):
        value = edit.create_material_expression(material, cls)
        if not value: raise RuntimeError('moon expression creation failed')
        return value
    def link(a, output, b, input_name):
        if not edit.connect_material_expressions(a, output, b, input_name): raise RuntimeError('moon material connection failed: ' + input_name)
    def scalar(name, default):
        value = node(unreal.MaterialExpressionScalarParameter); value.set_editor_property('parameter_name', name)
        value.set_editor_property('default_value', default); value.set_editor_property('group', 'Moon Animation'); return value
    time = node(unreal.MaterialExpressionTime); clock = node(unreal.MaterialExpressionMultiply)
    link(time, '', clock, 'A'); link(scalar('PlaybackRate', 1), '', clock, 'B')
    preview = node(unreal.MaterialExpressionAdd); link(clock, '', preview, 'A'); link(scalar('PreviewTime', 0), '', preview, 'B')
    angle = node(unreal.MaterialExpressionMultiply); link(preview, '', angle, 'A'); link(scalar('YawTurnsPerSecond', 0), '', angle, 'B')
    axis = node(unreal.MaterialExpressionConstant3Vector); axis.set_editor_property('constant', unreal.LinearColor(0, 0, 1, 0))
    pivot = node(unreal.MaterialExpressionVectorParameter); pivot.set_editor_property('parameter_name', 'RotationPivot'); pivot.set_editor_property('group', 'Moon Animation')
    pivot.set_editor_property('default_value', unreal.LinearColor(0, 0, 0, 0))
    position = node(unreal.MaterialExpressionWorldPosition)
    rotate = node(unreal.MaterialExpressionRotateAboutAxis)
    link(axis, '', rotate, 'NormalizedRotationAxis'); link(angle, '', rotate, 'RotationAngle'); link(pivot, '', rotate, 'PivotPoint'); link(position, '', rotate, 'Position')
    total = node(unreal.MaterialExpressionAdd); link(centered, '', total, 'A'); link(rotate, '', total, 'B')
    if not edit.connect_material_property(total, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET): raise RuntimeError('moon WPO connection failed')
    edit.layout_material_expressions(material); edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('moon parent save failed')
    return material


def apply(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_sky.py'))['verify'](plan['sky_plan'], ROOT / '.local/logs/unreal-sky-verified.json')
    paths = [PARENT] + [e['asset_path'] for e in plan['textures'] + plan['meshes']] + [e['material_path'] for e in plan['meshes']]
    if any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in paths): raise RuntimeError('moon destination exists; inspect partial state')
    if not level.save_current_level(): raise RuntimeError('pre-edit save failed')
    backup = ROOT / '.local/moons-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    shutil.copy2(Path(unreal.Paths.project_content_dir()) / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    runpy.run_path(str(ROOT / 'tools/editor/apply_intro_materials.py'))['create_resources'](dict(textures=plan['textures'], materials=[]), plan_path.parent)
    assets = unreal.AssetToolsHelpers.get_asset_tools(); parent = create_parent(); edit = unreal.MaterialEditingLibrary
    build_asset = runpy.run_path(str(ROOT / 'tools/editor/import_intro.py'))['build_asset']
    smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem); actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for entry in plan['meshes']:
        folder, name = entry['material_path'].rsplit('/', 1)
        material = assets.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()); edit.set_material_instance_parent(material, parent)
        texture = unreal.load_asset(next(t['asset_path'] for t in plan['textures'] if t['path'] == entry['texture']))
        edit.set_material_instance_texture_parameter_value(material, 'OriginalColor', texture)
        if edit.get_material_instance_texture_parameter_value(material, 'OriginalColor') != texture: raise RuntimeError('moon texture assignment failed')
        edit.set_material_instance_scalar_parameter_value(material, 'SkyBrightness', plan['preview_brightness'])
        edit.set_material_instance_scalar_parameter_value(material, 'YawTurnsPerSecond', entry['yaw_turns_per_second'])
        edit.set_material_instance_vector_parameter_value(material, 'RotationPivot', unreal.LinearColor(*entry['rotation_pivot'], 0))
        edit.update_material_instance(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('moon instance save failed')
        data = json.loads((plan_path.parent / entry['source_file']).read_text()); mesh = build_asset(data, entry['asset_path'], entry['triangle_count'])
        build = smes.get_lod_build_settings(mesh, 0); build.use_full_precision_u_vs = True; build.distance_field_resolution_scale = 0; build.max_lumen_mesh_cards = 0
        smes.set_lod_build_settings(mesh, 0, build); mesh.set_material(0, material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(mesh): raise RuntimeError('moon mesh save failed')
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector()); actor.set_actor_label(entry['name']); c = actor.static_mesh_component
        c.set_static_mesh(mesh); c.set_collision_profile_name('NoCollision'); c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        for key in ('cast_shadow', 'affect_distance_field_lighting', 'visible_in_real_time_sky_captures', 'visible_in_reflection_captures', 'visible_in_ray_tracing'): c.set_editor_property(key, False)
        c.set_editor_property('bounds_scale', 10.0)
    if not level.save_current_level(): raise RuntimeError('moon map save failed')
    report = dict(status='success', backup=str(backup), plan_sha256=digest(plan_path), moon_triangles=sum(e['triangle_count'] for e in plan['meshes']))
    (ROOT / '.local/logs/unreal-moons-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_MOONS_APPLIED')
    return report


if __name__ == '__main__':
    apply(ROOT / 'data/converted/Unreal/Maps/Unreal/moons-ready/Unreal.moons.json')
