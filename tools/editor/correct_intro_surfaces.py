"""Correct far-sky fog compositing and the source-flagged additive bridge floor."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import unreal

ROOT = Path(__file__).resolve().parents[2]
FLOOR = '/Game/Unreal/Materials/NaliCast/Floor/translucent/n-floor6_ue5'
OPAQUE = '/Game/Unreal/Materials/UE5/Original_opaque_ue5'


def apply():
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    edit = unreal.MaterialEditingLibrary; parents = {mode: unreal.load_asset('/Game/Unreal/Materials/UE5/Unreal_sky_' + mode + '_ue5') for mode in ('stars', 'cloud')}
    floor = unreal.load_asset(FLOOR)
    if floor.parent == unreal.load_asset(OPAQUE): raise RuntimeError('surface correction already applied')
    if floor.parent.get_path_name().split('.')[0] != '/Game/Unreal/Materials/UE5/Original_translucent_ue5': raise RuntimeError('unexpected bridge parent')
    for material in parents.values():
        if not any(isinstance(n, unreal.MaterialExpressionScalarParameter) and str(n.get_editor_property('parameter_name')) == 'BackdropDistanceScale' and n.get_editor_property('default_value') == 64 for n in edit.get_material_expressions(material)): raise RuntimeError('extend backdrop before correcting surfaces')
    backup = ROOT / '.local/intro-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    content = Path(unreal.Paths.project_content_dir())
    for asset in [floor, *parents.values()]: shutil.copy2(content / (asset.get_path_name().split('.')[0].removeprefix('/Game/') + '.uasset'), backup / (asset.get_name() + '.uasset'))
    shutil.copy2(content / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    stars = parents['stars']; stars.modify(); stars.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    one = edit.create_material_expression(stars, unreal.MaterialExpressionConstant); one.set_editor_property('r', 1)
    if not edit.connect_material_property(one, '', unreal.MaterialProperty.MP_OPACITY): raise RuntimeError('sky opacity connection failed')
    for material in parents.values():
        material.modify(); material.set_editor_property('use_translucency_vertex_fog', False); edit.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('sky compositing save failed')
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_actor_label().startswith('SkyZoneInfo1_Surface'):
            actor.modify(); actor.static_mesh_component.modify(); actor.static_mesh_component.set_editor_property('translucency_sort_priority', -99 if actor.get_actor_label().endswith('03_ue5') else -100)
    color = edit.get_material_instance_texture_parameter_value(floor, 'OriginalColor'); floor.modify(); edit.set_material_instance_parent(floor, unreal.load_asset(OPAQUE)); edit.update_material_instance(floor)
    if edit.get_material_instance_texture_parameter_value(floor, 'OriginalColor') != color: raise RuntimeError('bridge source texture changed')
    if not unreal.EditorAssetLibrary.save_loaded_asset(floor) or not level.save_current_level(): raise RuntimeError('surface correction save failed')
    report = dict(status='success', backup=str(backup), bridge_triangles=39, sky_fogging=False, sky_sort_priorities=[-100, -99], environment_rig_unchanged=True)
    (ROOT / '.local/logs/unreal-intro-surfaces-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_INTRO_SURFACES_APPLIED'); return report


if __name__ == '__main__': apply()
