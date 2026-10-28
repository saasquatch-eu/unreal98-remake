"""Create a camera-centered original-image sky without changing world geometry."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ue1_converter.ue5_prepare import validate_buffers
from ue1_converter.sky_prepare import digest

PARENTS = {mode: '/Game/Unreal/Materials/UE5/Unreal_' + mode + '_ue5' for mode in ('sky_stars', 'sky_cloud')}


def checked_plan(path):
    path = Path(path); plan = json.loads(path.read_text())
    if plan['schema_version'] != 1: raise RuntimeError('unsupported sky plan')
    for key in ('geometry', 'source', 'package'):
        if digest(plan[key + '_file']) != plan[key + '_sha256']: raise RuntimeError('sky source provenance differs')
    for package in plan['packages'].values():
        if digest(package['file']) != package['sha256']: raise RuntimeError('sky texture package differs')
    for entry in plan['textures'] + plan['meshes']:
        if digest(path.parent / entry['source_file']) != entry['source_sha256']: raise RuntimeError('sky buffer/image differs')
    for entry in plan['meshes']: validate_buffers(json.loads((path.parent / entry['source_file']).read_text()))
    return plan


def parent(mode, assets):
    folder, name = PARENTS[mode].rsplit('/', 1)
    material = assets.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    cloud = mode == 'sky_cloud'
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE if cloud else unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('two_sided', True)
    # Keep the original-image backdrop independent of atmospheric sky capture.
    material.set_editor_property('is_sky', False)
    edit = unreal.MaterialEditingLibrary
    def node(cls): return edit.create_material_expression(material, cls)
    def link(a, output, b, input):
        if not edit.connect_material_expressions(a, output, b, input): raise RuntimeError('sky graph connection failed')
    sample = node(unreal.MaterialExpressionTextureSampleParameter2D)
    sample.set_editor_property('parameter_name', 'OriginalColor'); sample.set_editor_property('texture', unreal.load_asset('/Engine/EngineResources/WhiteSquareTexture'))
    strength = node(unreal.MaterialExpressionScalarParameter); strength.set_editor_property('parameter_name', 'SkyBrightness'); strength.set_editor_property('default_value', 1.0)
    multiply = node(unreal.MaterialExpressionMultiply); link(sample, 'RGB', multiply, 'A'); link(strength, '', multiply, 'B')
    if not edit.connect_material_property(multiply, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR): raise RuntimeError('sky emission connection failed')
    camera = node(unreal.MaterialExpressionCameraPositionWS); actor = node(unreal.MaterialExpressionActorPositionWS)
    offset = node(unreal.MaterialExpressionSubtract); link(camera, '', offset, 'A'); link(actor, '', offset, 'B')
    follow = node(unreal.MaterialExpressionScalarParameter); follow.set_editor_property('parameter_name', 'FollowCamera'); follow.set_editor_property('default_value', 1.0)
    centered = node(unreal.MaterialExpressionMultiply); link(offset, '', centered, 'A'); link(follow, '', centered, 'B')
    if not edit.connect_material_property(centered, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET): raise RuntimeError('sky camera-centering failed')
    if cloud:
        uv = node(unreal.MaterialExpressionTextureCoordinate); time = node(unreal.MaterialExpressionTime)
        rate = node(unreal.MaterialExpressionVectorParameter); rate.set_editor_property('parameter_name', 'PanRate'); rate.set_editor_property('default_value', unreal.LinearColor(0, 0, 0, 0))
        mask = node(unreal.MaterialExpressionComponentMask); mask.set_editor_property('r', True); mask.set_editor_property('g', True)
        link(rate, '', mask, ''); motion = node(unreal.MaterialExpressionMultiply); link(mask, '', motion, 'A'); link(time, '', motion, 'B')
        phase = node(unreal.MaterialExpressionVectorParameter); phase.set_editor_property('parameter_name', 'PreviewOffset'); phase.set_editor_property('default_value', unreal.LinearColor(0, 0, 0, 0))
        phase_mask = node(unreal.MaterialExpressionComponentMask); phase_mask.set_editor_property('r', True); phase_mask.set_editor_property('g', True); link(phase, '', phase_mask, '')
        add = node(unreal.MaterialExpressionAdd); link(uv, '', add, 'A'); link(motion, '', add, 'B')
        preview = node(unreal.MaterialExpressionAdd); link(add, '', preview, 'A'); link(phase_mask, '', preview, 'B'); link(preview, '', sample, 'UVs')
    edit.layout_material_expressions(material); edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('sky parent save failed')
    return material


def apply(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path); level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_mood.py'))['verify'](ROOT / 'tools/presets/Unreal_Gloom_ue5.json', ROOT / '.local/logs/unreal-mood-verified.json')
    destinations = set(PARENTS.values()) | {e['asset_path'] for e in plan['textures'] + plan['meshes']} | {e['material_path'] for e in plan['meshes']}
    if any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in destinations): raise RuntimeError('sky destination already exists; inspect partial state before retrying')
    if not level.save_current_level(): raise RuntimeError('pre-edit save failed')
    backup = ROOT / '.local/sky-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    shutil.copy2(Path(unreal.Paths.project_content_dir()) / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    assets = unreal.AssetToolsHelpers.get_asset_tools(); helper = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_materials.py'))
    # Existing source-color importer checks create-only destinations and readback.
    helper['create_resources'](dict(textures=plan['textures'], materials=[]), plan_path.parent)
    parents = {mode: parent(mode, assets) for mode in PARENTS}; materials = {}
    for entry in plan['meshes']:
        if entry['material_path'] in materials: continue
        folder, name = entry['material_path'].rsplit('/', 1)
        material = assets.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        edit = unreal.MaterialEditingLibrary; edit.set_material_instance_parent(material, parents[entry['mode']])
        texture = unreal.load_asset(next(t['asset_path'] for t in plan['textures'] if t['path'] == entry['texture']))
        edit.set_material_instance_texture_parameter_value(material, 'OriginalColor', texture)
        if edit.get_material_instance_texture_parameter_value(material, 'OriginalColor') != texture: raise RuntimeError('sky texture binding failed')
        edit.set_material_instance_scalar_parameter_value(material, 'SkyBrightness', 1.0)
        if entry['mode'] == 'sky_cloud':
            edit.set_material_instance_vector_parameter_value(material, 'PanRate', unreal.LinearColor(*entry['pan_uv_per_second'], 0, 0))
        edit.update_material_instance(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('sky instance save failed')
        materials[entry['material_path']] = material
    build = runpy.run_path(str(ROOT / 'tools/editor/import_intro.py'))['build_asset']
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for entry in plan['meshes']:
        data = json.loads((plan_path.parent / entry['source_file']).read_text()); asset = build(data, entry['asset_path'], entry['triangle_count'])
        settings = meshes.get_lod_build_settings(asset, 0); settings.use_full_precision_u_vs = True; settings.distance_field_resolution_scale = 0; settings.max_lumen_mesh_cards = 0
        meshes.set_lod_build_settings(asset, 0, settings); asset.set_material(0, materials[entry['material_path']])
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset): raise RuntimeError('sky mesh save failed')
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector()); actor.set_actor_label(entry['name']); component = actor.static_mesh_component
        component.set_static_mesh(asset); component.set_collision_profile_name('NoCollision'); component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        for key in ('cast_shadow', 'affect_distance_field_lighting', 'visible_in_real_time_sky_captures', 'visible_in_reflection_captures', 'visible_in_ray_tracing'):
            component.set_editor_property(key, False)
        # Allow the shader's camera translation without viewport-frustum clipping.
        component.set_editor_property('bounds_scale', 10.0)
    if not level.save_current_level(): raise RuntimeError('sky map save failed')
    report = dict(status='success', backup=str(backup), plan_sha256=digest(plan_path), sky_triangles=sum(e['triangle_count'] for e in plan['meshes']))
    (ROOT / '.local/logs/unreal-sky-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_SKY_APPLIED')
    return report


if __name__ == '__main__':
    apply(ROOT / 'data/converted/Unreal/Maps/Unreal/sky-ready/Unreal.sky.json')
