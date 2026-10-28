"""Create source-position lightning lights and a looping Sequencer preview."""
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

COLLECTION = '/Game/Unreal/Materials/UE5/DistanceLightning_ue5'
SEQUENCE = '/Game/Unreal/Cinematics/DistanceLightning_ue5'
CLOUD = '/Game/Unreal/Materials/UE5/Unreal_sky_cloud_ue5'


def checked_plan(path):
    plan = json.loads(Path(path).read_text())
    if plan['schema_version'] != 1: raise RuntimeError('unsupported lightning plan')
    for key in ('moons',):
        if digest(plan[key + '_plan']) != plan[key + '_sha256']: raise RuntimeError('lightning prior-stage provenance differs')
    for key in ('source', 'package'):
        if digest(plan[key + '_file']) != plan[key + '_sha256']: raise RuntimeError('lightning original provenance differs')
    return plan


def cloud_graph(plan, collection):
    material = unreal.load_asset(CLOUD); material.modify(); edit = unreal.MaterialEditingLibrary
    original = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    def node(cls):
        value = edit.create_material_expression(material, cls)
        if not value: raise RuntimeError('lightning expression creation failed')
        return value
    def link(a, output, b, input_name):
        if not edit.connect_material_expressions(a, output, b, input_name): raise RuntimeError('lightning material connection failed: ' + input_name)
    def vector(values):
        value = node(unreal.MaterialExpressionConstant3Vector); value.set_editor_property('constant', unreal.LinearColor(*values, 0)); return value
    def scalar(number):
        value = node(unreal.MaterialExpressionConstant); value.set_editor_property('r', number); return value
    world = node(unreal.MaterialExpressionWorldPosition); camera = node(unreal.MaterialExpressionCameraPositionWS)
    relative = node(unreal.MaterialExpressionSubtract); link(world, '', relative, 'A'); link(camera, '', relative, 'B')
    unscaled = node(unreal.MaterialExpressionDivide); link(relative, '', unscaled, 'A'); link(scalar(plan['projection_scale']), '', unscaled, 'B')
    source = node(unreal.MaterialExpressionAdd); link(unscaled, '', source, 'A'); link(vector(plan['sky_origin']), '', source, 'B')
    total = None
    for entry in (e for e in plan['lights'] if e['sky']):
        distance = node(unreal.MaterialExpressionDistance); link(source, '', distance, 'A'); link(vector(entry['location']), '', distance, 'B')
        normalized = node(unreal.MaterialExpressionDivide); link(distance, '', normalized, 'A'); link(scalar(entry['radius']), '', normalized, 'B')
        inverse = node(unreal.MaterialExpressionOneMinus); link(normalized, '', inverse, '')
        clamp = node(unreal.MaterialExpressionSaturate); link(inverse, '', clamp, '')
        squared = node(unreal.MaterialExpressionMultiply); link(clamp, '', squared, 'A'); link(clamp, '', squared, 'B')
        pulse = node(unreal.MaterialExpressionCollectionParameter); pulse.set_editor_property('collection', collection); pulse.set_editor_property('parameter_name', entry['collection_parameter'])
        weighted = node(unreal.MaterialExpressionMultiply); link(squared, '', weighted, 'A'); link(pulse, '', weighted, 'B')
        if total:
            add = node(unreal.MaterialExpressionAdd); link(total, '', add, 'A'); link(weighted, '', add, 'B'); total = add
        else: total = weighted
    capped = node(unreal.MaterialExpressionSaturate); link(total, '', capped, '')
    gain = node(unreal.MaterialExpressionScalarParameter); gain.set_editor_property('parameter_name', 'LightningGain'); gain.set_editor_property('default_value', plan['cloud_gain']); gain.set_editor_property('group', 'Lightning')
    boost = node(unreal.MaterialExpressionMultiply); link(capped, '', boost, 'A'); link(gain, '', boost, 'B')
    factor = node(unreal.MaterialExpressionAdd); link(scalar(1), '', factor, 'A'); link(boost, '', factor, 'B')
    result = node(unreal.MaterialExpressionMultiply); link(original, '', result, 'A'); link(factor, '', result, 'B')
    if not edit.connect_material_property(result, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR): raise RuntimeError('cloud flash output failed')
    edit.layout_material_expressions(material); edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material): raise RuntimeError('cloud flash material save failed')


def apply(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_moons.py'))['verify'](plan['moons_plan'], ROOT / '.local/logs/unreal-moons-verified.json')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {a.get_actor_label() for a in actors.get_all_level_actors()}
    if any(e['name'] in labels for e in plan['lights']) or 'DistanceLightning_ue5' in labels or any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in (COLLECTION, SEQUENCE)):
        raise RuntimeError('lightning destination exists; inspect partial state')
    if not level.save_current_level(): raise RuntimeError('pre-edit save failed')
    backup = ROOT / '.local/lightning-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    content = Path(unreal.Paths.project_content_dir())
    shutil.copy2(content / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    shutil.copy2(content / (CLOUD.removeprefix('/Game/') + '.uasset'), backup / 'Unreal_sky_cloud_ue5.uasset')
    shutil.copy2(ROOT / '.local/logs/unreal-sky-verified.json', backup / 'sky-before.json')
    assets = unreal.AssetToolsHelpers.get_asset_tools(); folder, name = COLLECTION.rsplit('/', 1)
    collection = assets.create_asset(name, folder, unreal.MaterialParameterCollection, unreal.MaterialParameterCollectionFactoryNew())
    parameters = []
    for entry in (e for e in plan['lights'] if e['sky']):
        value = unreal.CollectionScalarParameter(); value.set_editor_property('parameter_name', entry['collection_parameter']); value.set_editor_property('default_value', 0); parameters.append(value)
    collection.set_editor_property('scalar_parameters', parameters)
    if not unreal.EditorAssetLibrary.save_loaded_asset(collection): raise RuntimeError('lightning collection save failed')
    cloud_graph(plan, collection)
    folder, name = SEQUENCE.rsplit('/', 1); sequence = assets.create_asset(name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    rate = unreal.FrameRate(plan['frame_rate'], 1); sequence.set_tick_resolution_directly(rate); sequence.set_display_rate(rate)
    sequence.set_playback_start(0); sequence.set_playback_end(plan['duration_ms'])
    track = sequence.add_track(unreal.MovieSceneMaterialParameterCollectionTrack); track.set_editor_property('mpc', collection)
    section = track.add_section(); section.set_range(0, plan['duration_ms'])
    for entry in plan['lights']:
        actor = actors.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*entry['location'])); actor.set_actor_label(entry['name'])
        component = actor.get_component_by_class(unreal.PointLightComponent); component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property('intensity_units', unreal.LightUnits.LUMENS); component.set_intensity(0); component.set_attenuation_radius(entry['radius'])
        component.set_light_color(unreal.LinearColor(*entry['color_linear'], 1), True); component.set_cast_shadows(entry['cast_shadows'])
        binding = sequence.add_possessable(component); binding.set_name(entry['name'])
        light_track = binding.add_track(unreal.MovieSceneFloatTrack); light_track.set_property_name_and_path('Intensity', 'Intensity')
        light_section = light_track.add_section(); light_section.set_range(0, plan['duration_ms']); channel = light_section.get_all_channels()[0]; channel.set_default(0)
        for frame, value in entry['schedule']['keys']:
            channel.add_key(unreal.FrameNumber(frame), value * entry['peak_lumens'], interpolation=unreal.MovieSceneKeyInterpolation.CONSTANT)
            if entry['sky']: section.add_scalar_parameter_key(entry['collection_parameter'], unreal.FrameNumber(frame), value, unreal.MovieSceneKeyInterpolation.CONSTANT)
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence): raise RuntimeError('lightning sequence save failed')
    director = actors.spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector()); director.set_actor_label('DistanceLightning_ue5'); director.set_sequence(sequence)
    playback = director.get_editor_property('playback_settings'); playback.auto_play = True; playback.loop_count = unreal.MovieSceneSequenceLoopCount(-1); director.set_editor_property('playback_settings', playback)
    if not level.save_current_level(): raise RuntimeError('lightning map save failed')
    report = dict(status='success', backup=str(backup), plan_sha256=digest(plan_path), light_count=len(plan['lights']), sky_light_count=len(parameters))
    (ROOT / '.local/logs/unreal-lightning-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_LIGHTNING_APPLIED')
    return report


if __name__ == '__main__':
    apply(ROOT / 'data/converted/Unreal/Maps/Unreal/lightning-ready/Unreal.lightning.json')
