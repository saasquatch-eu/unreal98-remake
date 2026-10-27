"""Create a lit source-image water preview and bind only its recorded raster slots."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import shutil

import unreal

ROOT = Path(__file__).resolve().parents[2]
PARENT = '/Game/Unreal/Materials/UE5/Unreal_WaterFlipbook_ue5'


def checked_plan(path):
    path = Path(path); plan = json.loads(path.read_text())
    for key in ('material', 'lighting', 'fire'):
        if hashlib.sha256(Path(plan[key + '_plan']).read_bytes()).hexdigest() != plan[key + '_sha256']:
            raise RuntimeError(key + ' provenance changed')
    for entry in plan['textures']:
        for filename, checksum in [('source_file', 'source_sha256'), ('source_image_file', 'source_image_sha256')]:
            if hashlib.sha256((path.parent / entry[filename]).read_bytes()).hexdigest() != entry[checksum]:
                raise RuntimeError('water image checksum changed')
    for package in plan['packages'].values():
        if hashlib.sha256(Path(package['file']).read_bytes()).hexdigest() != package['sha256']:
            raise RuntimeError('original water dependency changed')
    return plan


def new_parent():
    # Reuse the authored animation graph without changing the flame parent.
    source = '/Game/Unreal/Materials/UE5/Unreal_FireFlipbook_ue5'
    material = unreal.EditorAssetLibrary.duplicate_asset(source, PARENT)
    if not material: raise RuntimeError('water animation graph duplication failed')
    edit = unreal.MaterialEditingLibrary
    color = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if not color: raise RuntimeError('source animation graph has no color output')
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    for node in edit.get_material_expressions(material):
        if isinstance(node, (unreal.MaterialExpressionScalarParameter, unreal.MaterialExpressionTextureObjectParameter)):
            node.set_editor_property('group', 'Water Animation')
            name = str(node.get_editor_property('parameter_name'))
            if name == 'FlameAtlas': node.set_editor_property('parameter_name', 'WaterAtlas')
            if name == 'EmissiveStrength':
                node.set_editor_property('parameter_name', 'ColorStrength'); node.set_editor_property('default_value', 1.0)
    if not edit.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR): raise RuntimeError('water color connection failed')
    def scalar(name, value):
        node = edit.create_material_expression(material, unreal.MaterialExpressionScalarParameter)
        node.set_editor_property('parameter_name', name); node.set_editor_property('default_value', value)
        node.set_editor_property('group', 'Water Surface')
        return node
    for name, value, prop in [('Opacity', 0.7, unreal.MaterialProperty.MP_OPACITY), ('Roughness', 0.2, unreal.MaterialProperty.MP_ROUGHNESS)]:
        if not edit.connect_material_property(scalar(name, value), '', prop): raise RuntimeError('water surface connection failed')
    # Canvas render-target checks use emissive output. Saved scene value stays zero.
    diagnostic = edit.create_material_expression(material, unreal.MaterialExpressionMultiply)
    if not edit.connect_material_expressions(color, '', diagnostic, 'A') or not edit.connect_material_expressions(scalar('PreviewEmissive', 0), '', diagnostic, 'B'):
        raise RuntimeError('water diagnostic connection failed')
    if not edit.connect_material_property(diagnostic, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR): raise RuntimeError('water diagnostic output failed')
    edit.layout_material_expressions(material); edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('water parent save failed')
    return material


def import_image(path, filename, *, atlas):
    task = unreal.AssetImportTask(); task.filename = str(filename)
    task.destination_path, task.destination_name = path.rsplit('/', 1)
    task.automated = True; task.replace_existing = False; task.save = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if len(task.imported_object_paths) != 1: raise RuntimeError('water image import failed')
    texture = unreal.load_asset(path)
    if texture != unreal.load_asset(task.imported_object_paths[0]): raise RuntimeError('water import destination differs')
    texture.set_editor_property('srgb', True)
    texture.set_editor_property('address_x', unreal.TextureAddress.TA_WRAP); texture.set_editor_property('address_y', unreal.TextureAddress.TA_WRAP)
    if atlas:
        texture.set_editor_property('mip_gen_settings', unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        texture.set_editor_property('filter', unreal.TextureFilter.TF_BILINEAR); texture.set_editor_property('never_stream', True)
    if not unreal.EditorAssetLibrary.save_loaded_asset(texture): raise RuntimeError('water image save failed')
    return texture


def run(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_fire.py'))['verify'](plan['fire_plan'], ROOT / '.local/logs/unreal-fire-verified.json')
    paths = [PARENT] + [e[k] for e in plan['textures'] for k in ('texture_path', 'material_path', 'source_image_asset')]
    if any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in paths): raise RuntimeError('water destination already exists')
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    for binding in plan['bindings']:
        c = actors[binding['actor']].static_mesh_component
        if c.get_material(binding['slot']) != unreal.load_asset(binding['original_material']): raise RuntimeError('existing water slot differs')
    backup = ROOT / '.local/water-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    saved = Path(unreal.Paths.project_content_dir()).resolve() / 'Unreal/Maps/Unreal_ue5.umap'
    shutil.copy2(saved, backup / saved.name)
    parent = new_parent(); resources = {}; edit = unreal.MaterialEditingLibrary
    for entry in plan['textures']:
        import_image(entry['source_image_asset'], plan_path.parent / entry['source_image_file'], atlas=False)
        texture = import_image(entry['texture_path'], plan_path.parent / entry['source_file'], atlas=True)
        folder, name = entry['material_path'].rsplit('/', 1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        if not material: raise RuntimeError('water material instance creation failed')
        edit.set_material_instance_parent(material, parent)
        edit.set_material_instance_texture_parameter_value(material, 'WaterAtlas', texture)
        if edit.get_material_instance_texture_parameter_value(material, 'WaterAtlas') != texture: raise RuntimeError('water atlas assignment differs')
        values = dict(Rows=entry['rows'], Columns=entry['columns'], PlaybackRate=entry['fps'] / entry['frames'], PhaseOffset=0,
                      InnerScale=entry['uv_scale'], InnerBias=entry['uv_bias'], ColorStrength=entry['color_strength'],
                      Opacity=entry['opacity'], Roughness=entry['roughness'], PreviewEmissive=0)
        for key, value in values.items(): edit.set_material_instance_scalar_parameter_value(material, key, value)
        edit.update_material_instance(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('water material save failed')
        resources[entry['material_path']] = material
    for binding in plan['bindings']:
        actor = actors[binding['actor']]; actor.modify(); c = actor.static_mesh_component; c.modify()
        c.set_material(binding['slot'], resources[binding['material']])
    if not level.save_current_level(): raise RuntimeError('water map save failed')
    report = dict(status='success', backup=str(backup), bindings=len(plan['bindings']), water_triangles=sum(e['triangles'] for e in plan['bindings']))
    (ROOT / '.local/logs/unreal-water-apply.json').write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_WATER_APPLIED')
    return report


if __name__ == '__main__':
    run(ROOT / 'data/converted/Unreal/Maps/Unreal/water-ready/Unreal.water.json')
