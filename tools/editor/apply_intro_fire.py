"""Add source-palette flame previews through explicit raster-actor material overrides."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shutil

import unreal

ROOT = Path(__file__).resolve().parents[2]
PARENT = '/Game/Unreal/Materials/UE5/Unreal_FireFlipbook_ue5'
FUNCTION = '/Engine/Functions/Engine_MaterialFunctions02/Texturing/FlipBook'


def checked_plan(path):
    path = Path(path); plan = json.loads(path.read_text())
    for key in ('material', 'lighting'):
        if hashlib.sha256(Path(plan[key + '_plan']).read_bytes()).hexdigest() != plan[key + '_sha256']:
            raise RuntimeError(key + ' provenance changed')
    for entry in plan['textures']:
        if hashlib.sha256((path.parent / entry['source_file']).read_bytes()).hexdigest() != entry['source_sha256']:
            raise RuntimeError('flame atlas checksum changed')
    return plan


def new_parent(atlas):
    assets = unreal.AssetToolsHelpers.get_asset_tools(); folder, name = PARENT.rsplit('/', 1)
    material = assets.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if not material: raise RuntimeError('fire parent creation failed')
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    edit = unreal.MaterialEditingLibrary
    def node(kind):
        value = edit.create_material_expression(material, kind)
        if not value: raise RuntimeError('material expression creation failed')
        return value
    def link(a, output, b, input_name):
        if not edit.connect_material_expressions(a, output, b, input_name):
            raise RuntimeError('material connection failed: ' + input_name)
    def scalar(name, default):
        value = node(unreal.MaterialExpressionScalarParameter)
        value.set_editor_property('parameter_name', name); value.set_editor_property('default_value', default)
        value.set_editor_property('group', 'Flame Animation')
        return value
    texture = node(unreal.MaterialExpressionTextureObjectParameter)
    texture.set_editor_property('parameter_name', 'FlameAtlas'); texture.set_editor_property('texture', atlas)
    texture.set_editor_property('group', 'Flame Animation')
    function = node(unreal.MaterialExpressionMaterialFunctionCall)
    if not function.set_material_function(unreal.load_asset(FUNCTION)):
        raise RuntimeError('FlipBook function assignment failed')
    link(texture, '', function, 'Texture')
    clock = node(unreal.MaterialExpressionTime); speed = scalar('PlaybackRate', 0.25)
    rate = node(unreal.MaterialExpressionMultiply); link(clock, '', rate, 'A'); link(speed, '', rate, 'B')
    phase = node(unreal.MaterialExpressionAdd); link(rate, '', phase, 'A'); link(scalar('PhaseOffset', 0), '', phase, 'B')
    loop = node(unreal.MaterialExpressionFrac); link(phase, '', loop, '')
    link(loop, '', function, 'Animation  Phase (0-1)')
    for name in ('Rows', 'Columns'):
        link(scalar(name, 8), '', function, 'Number of ' + name)
    uv = node(unreal.MaterialExpressionTextureCoordinate); repeat = node(unreal.MaterialExpressionFrac)
    link(uv, '', repeat, '')
    scale = node(unreal.MaterialExpressionMultiply); link(repeat, '', scale, 'A')
    link(scalar('InnerScale', 128 / 132), '', scale, 'B')
    padded = node(unreal.MaterialExpressionAdd); link(scale, '', padded, 'A')
    link(scalar('InnerBias', 2 / 132), '', padded, 'B'); link(padded, '', function, 'UVs')
    # Palette index zero has alpha zero; no additive light comes from the padded background.
    masked = node(unreal.MaterialExpressionMultiply)
    link(function, 'Result', masked, 'A'); link(function, 'Alpha', masked, 'B')
    emissive = node(unreal.MaterialExpressionMultiply)
    link(masked, '', emissive, 'A'); link(scalar('EmissiveStrength', 64), '', emissive, 'B')
    if not edit.connect_material_property(emissive, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError('fire emissive connection failed')
    edit.layout_material_expressions(material); edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('fire parent save failed')
    return material


def run(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_lumen_lighting.py'))['verify'](plan['lighting_plan'], ROOT / '.local/logs/unreal-lumen-verified.json')
    paths = [PARENT] + [e[k] for e in plan['textures'] for k in ('texture_path', 'material_path')]
    if any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in paths): raise RuntimeError('new fire destination already exists')
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    for binding in plan['bindings']:
        component = actors[binding['actor']].static_mesh_component
        if component.get_material(binding['slot']) != unreal.load_asset(binding['original_material']):
            raise RuntimeError('existing flame slot differs')
        if any(component.get_editor_property('override_materials')): raise RuntimeError('existing actor material overrides')
    backup = ROOT / '.local/fire-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True)
    map_file = Path(unreal.Paths.project_content_dir()).resolve() / 'Unreal/Maps/Unreal_ue5.umap'
    shutil.copy2(map_file, backup / map_file.name)
    resources = {}; parent = None; assets = unreal.AssetToolsHelpers.get_asset_tools()
    for entry in plan['textures']:
        task = unreal.AssetImportTask(); task.filename = str(plan_path.parent / entry['source_file'])
        task.destination_path, task.destination_name = entry['texture_path'].rsplit('/', 1)
        task.automated = True; task.replace_existing = False; task.save = False
        assets.import_asset_tasks([task])
        if len(task.imported_object_paths) != 1: raise RuntimeError('fire import did not produce one texture')
        texture = unreal.load_asset(entry['texture_path'])
        if texture != unreal.load_asset(task.imported_object_paths[0]): raise RuntimeError('fire texture path differs')
        texture.set_editor_property('srgb', True)
        texture.set_editor_property('mip_gen_settings', unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        texture.set_editor_property('filter', unreal.TextureFilter.TF_BILINEAR)
        texture.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property('address_y', unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property('never_stream', True)
        if not unreal.EditorAssetLibrary.save_loaded_asset(texture): raise RuntimeError('fire texture save failed')
        if parent is None: parent = new_parent(texture)
        folder, name = entry['material_path'].rsplit('/', 1)
        material = assets.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        if not material: raise RuntimeError('fire instance creation failed')
        edit = unreal.MaterialEditingLibrary; edit.set_material_instance_parent(material, parent)
        edit.set_material_instance_texture_parameter_value(material, 'FlameAtlas', texture)
        if edit.get_material_instance_texture_parameter_value(material, 'FlameAtlas') != texture: raise RuntimeError('fire atlas assignment differs')
        if entry['uv_scale'][0] != entry['uv_scale'][1] or entry['uv_bias'][0] != entry['uv_bias'][1]:
            raise RuntimeError('shared fire material requires square frames')
        for key, value in [('Rows', entry['rows']), ('Columns', entry['columns']), ('PlaybackRate', entry['fps'] / entry['frames']),
                           ('EmissiveStrength', entry['emissive_strength']), ('InnerScale', entry['uv_scale'][0]), ('InnerBias', entry['uv_bias'][0])]:
            edit.set_material_instance_scalar_parameter_value(material, key, value)
        edit.update_material_instance(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('fire instance save failed')
        resources[entry['material_path']] = material
    for binding in plan['bindings']:
        actor = actors[binding['actor']]; actor.modify(); component = actor.static_mesh_component; component.modify()
        component.set_material(binding['slot'], resources[binding['material']])
    if not level.save_current_level(): raise RuntimeError('fire map save failed')
    report = dict(status='success', backup=str(backup), textures=len(plan['textures']), bindings=len(plan['bindings']),
                  flame_triangles=sum(b['triangles'] for b in plan['bindings']))
    (ROOT / '.local/logs/unreal-fire-apply.json').write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_FIRE_APPLIED')
    return report


if __name__ == '__main__':
    run(ROOT / 'data/converted/Unreal/Maps/Unreal/fire-ready/Unreal.fire.json')
