"""Push the source backdrop beyond the castle without changing its mesh buffers."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import shutil

import unreal

ROOT = Path(__file__).resolve().parents[2]
PARENTS = ['/Game/Unreal/Materials/UE5/Unreal_sky_' + mode + '_ue5' for mode in ('stars', 'cloud')]
DISTANCE_SCALE = 64.0


def apply():
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    edit = unreal.MaterialEditingLibrary
    for path in PARENTS:
        if 'BackdropDistanceScale' in [str(n.get_editor_property('parameter_name')) for n in edit.get_material_expressions(unreal.load_asset(path)) if isinstance(n, unreal.MaterialExpressionScalarParameter)]: raise RuntimeError('backdrop extension already exists')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_lightning.py'))['verify'](ROOT / 'data/converted/Unreal/Maps/Unreal/lightning-ready/Unreal.lightning.json', ROOT / '.local/logs/unreal-lightning-verified.json')
    backup = ROOT / '.local/intro-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    content = Path(unreal.Paths.project_content_dir())
    for path in PARENTS: shutil.copy2(content / (path.removeprefix('/Game/') + '.uasset'), backup / (path.rsplit('/', 1)[1] + '.uasset'))
    shutil.copy2(content / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    for path in PARENTS:
        material = unreal.load_asset(path); material.modify()
        original = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        follow = next(n for n in edit.get_material_expressions(material) if isinstance(n, unreal.MaterialExpressionScalarParameter) and str(n.get_editor_property('parameter_name')) == 'FollowCamera')
        # Locate the existing source-coordinate divide before adding any other nodes.
        source_divide = None
        if 'cloud' in path:
            for n in edit.get_material_expressions(material):
                if isinstance(n, unreal.MaterialExpressionDivide):
                    inputs = edit.get_inputs_for_material_expression(material, n)
                    if len(inputs) == 2 and isinstance(inputs[1], unreal.MaterialExpressionConstant) and inputs[1].get_editor_property('r') == 128: source_divide = n
            if source_divide is None: raise RuntimeError('source sky coordinate projection missing')
        def node(kind):
            n = edit.create_material_expression(material, kind)
            if not n: raise RuntimeError('backdrop expression creation failed')
            return n
        def link(a, b, pin):
            if not edit.connect_material_expressions(a, '', b, pin): raise RuntimeError('backdrop graph connection failed')
        def constant(value):
            n = node(unreal.MaterialExpressionConstant); n.set_editor_property('r', value); return n
        scale = node(unreal.MaterialExpressionScalarParameter); scale.set_editor_property('parameter_name', 'BackdropDistanceScale'); scale.set_editor_property('group', 'Sky Projection'); scale.set_editor_property('default_value', DISTANCE_SCALE)
        delta = node(unreal.MaterialExpressionSubtract); link(scale, delta, 'A'); link(constant(1), delta, 'B')
        amount = node(unreal.MaterialExpressionMultiply); link(delta, amount, 'A'); link(follow, amount, 'B')
        world = node(unreal.MaterialExpressionWorldPosition); world.set_editor_property('world_position_shader_offset', unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
        relative = node(unreal.MaterialExpressionSubtract); link(world, relative, 'A'); link(node(unreal.MaterialExpressionActorPositionWS), relative, 'B')
        expansion = node(unreal.MaterialExpressionMultiply); link(relative, expansion, 'A'); link(amount, expansion, 'B')
        result = node(unreal.MaterialExpressionAdd); link(original, result, 'A'); link(expansion, result, 'B')
        if not edit.connect_material_property(result, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET): raise RuntimeError('backdrop projection output failed')
        if source_divide:
            effective = node(unreal.MaterialExpressionAdd); link(constant(1), effective, 'A'); link(amount, effective, 'B')
            denominator = node(unreal.MaterialExpressionMultiply); link(constant(128), denominator, 'A'); link(effective, denominator, 'B'); link(denominator, source_divide, 'B')
        edit.layout_material_expressions(material); edit.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('backdrop save failed')
    report = dict(status='success', distance_scale=DISTANCE_SCALE, nearest_lower_surface_cm=4096 * DISTANCE_SCALE, backup=str(backup))
    (ROOT / '.local/logs/unreal-sky-distance-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_SKY_DISTANCE_APPLIED'); return report


if __name__ == '__main__': apply()
