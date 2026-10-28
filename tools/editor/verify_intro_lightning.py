"""Verify saved lightning bindings, exact curves, idle sky parity and PIE evaluation."""
import json
import math
from pathlib import Path
import runpy

import unreal

ROOT = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_lightning.py'))
from ue1_converter.lightning_prepare import value_at


def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=2e-6, abs_tol=1e-5)


def check_channel(channel, keys, scale=1):
    actual = sorted(channel.get_keys(), key=lambda k: k.get_time().frame_number.value)
    if len(actual) != len(keys): raise RuntimeError('lightning key count differs')
    for key, (time, value) in zip(actual, keys):
        if key.get_time().frame_number.value != time or not close(key.get_value(), value * scale): raise RuntimeError('lightning key time/value differs')
        if key.get_interpolation_mode() != unreal.RichCurveInterpMode.RCIM_CONSTANT: raise RuntimeError('lightning key interpolation differs')


def verify(plan_path, report_path):
    plan_path = Path(plan_path); plan = HELPER['checked_plan'](plan_path)
    if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(): raise RuntimeError('stop PIE before saved verification')
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_moons.py'))['verify'](plan['moons_plan'], ROOT / '.local/logs/unreal-moons-verified.json')
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    collection = unreal.load_asset(HELPER['COLLECTION']); sequence = unreal.load_asset(HELPER['SEQUENCE']); director = actors['DistanceLightning_ue5']
    parameters = {str(p.get_editor_property('parameter_name')): p.get_editor_property('default_value') for p in collection.get_editor_property('scalar_parameters')}
    if parameters != {e['collection_parameter']: 0 for e in plan['lights'] if e['sky']}: raise RuntimeError('saved collection parameters differ')
    if director.get_sequence() != sequence: raise RuntimeError('director sequence differs')
    playback = director.get_editor_property('playback_settings')
    if not playback.auto_play or playback.loop_count.value != -1 or playback.play_rate != 1 or playback.random_start_time: raise RuntimeError('lightning playback settings differ')
    for rate in (sequence.get_tick_resolution(), sequence.get_display_rate()):
        if (rate.numerator, rate.denominator) != (plan['frame_rate'], 1): raise RuntimeError('lightning frame rate differs')
    if sequence.get_playback_start() != 0 or sequence.get_playback_end() != plan['duration_ms']: raise RuntimeError('lightning sequence range differs')
    bindings = {b.get_name(): b for b in sequence.get_bindings() if b.get_tracks()}
    if len(sequence.get_bindings()) != len(plan['lights']) * 2 or set(bindings) != {e['name'] for e in plan['lights']}: raise RuntimeError('lightning binding inventory differs')
    # Component possessables can add parent actor bindings; inspect the intended component binding by label.
    for entry in plan['lights']:
        actor = actors[entry['name']]; c = actor.get_component_by_class(unreal.PointLightComponent)
        if any(not close(getattr(actor.get_actor_location(), axis), value) for axis, value in zip('xyz', entry['location'])): raise RuntimeError('lightning source location differs')
        if c.mobility != unreal.ComponentMobility.MOVABLE or c.get_editor_property('intensity_units') != unreal.LightUnits.LUMENS or c.get_editor_property('intensity') != 0: raise RuntimeError('saved lightning units/intensity/mobility differ')
        if not close(c.get_editor_property('attenuation_radius'), entry['radius']) or c.get_editor_property('cast_shadows') != entry['cast_shadows']: raise RuntimeError('lightning radius/shadows differ')
        color = c.get_light_color()
        if any(not close(v, e) for v, e in zip((color.r, color.g, color.b), entry['color_linear'])): raise RuntimeError('lightning color differs')
        binding = bindings[entry['name']]
        if list(unreal.MovieSceneSequenceExtensions.locate_bound_objects(sequence, binding, world)) != [c]: raise RuntimeError('lightning component binding unresolved')
        if list(unreal.MovieSceneSequenceExtensions.locate_bound_objects(sequence, binding.get_parent(), world)) != [actor]: raise RuntimeError('lightning parent binding unresolved')
        tracks = binding.get_tracks()
        if len(tracks) != 1 or not isinstance(tracks[0], unreal.MovieSceneFloatTrack) or str(tracks[0].get_property_path()) != 'Intensity': raise RuntimeError('lightning intensity track differs')
        sections = tracks[0].get_sections()
        if len(sections) != 1 or sections[0].get_start_frame() != 0 or sections[0].get_end_frame() != plan['duration_ms']: raise RuntimeError('lightning section range differs')
        channels = sections[0].get_all_channels()
        if len(channels) != 1 or channels[0].get_default() != 0: raise RuntimeError('lightning default channel differs')
        check_channel(channels[0], entry['schedule']['keys'], entry['peak_lumens'])
    tracks = sequence.get_tracks()
    if len(tracks) != 1 or tracks[0].get_editor_property('mpc') != collection: raise RuntimeError('lightning collection track differs')
    sections = tracks[0].get_sections()
    if len(sections) != 1: raise RuntimeError('lightning collection section differs')
    channels = {str(c.get_editor_property('channel_name')): c for c in sections[0].get_all_channels()}
    if set(channels) != set(parameters): raise RuntimeError('lightning collection channels differ: ' + str(list(channels)))
    for entry in (e for e in plan['lights'] if e['sky']):
        check_channel(channels[entry['collection_parameter']], entry['schedule']['keys'])
        if unreal.MaterialLibrary.get_scalar_parameter_value(world, collection, entry['collection_parameter']) != 0: raise RuntimeError('idle cloud flash remains active')
    material = unreal.load_asset(HELPER['CLOUD']); edit = unreal.MaterialEditingLibrary
    pending = [edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)]; visited = set(); pulses = {}; gain = None
    while pending:
        node = pending.pop()
        if not node or node.get_path_name() in visited: continue
        visited.add(node.get_path_name())
        if isinstance(node, unreal.MaterialExpressionCollectionParameter): pulses[str(node.get_editor_property('parameter_name'))] = node.get_editor_property('collection')
        if isinstance(node, unreal.MaterialExpressionScalarParameter) and str(node.get_editor_property('parameter_name')) == 'LightningGain': gain = node.get_editor_property('default_value')
        pending.extend(edit.get_inputs_for_material_expression(material, node))
    if pulses != {name: collection for name in parameters} or gain != plan['cloud_gain']: raise RuntimeError('connected cloud flash graph differs')
    applied = json.loads((ROOT / '.local/logs/unreal-lightning-apply.json').read_text())
    if applied['plan_sha256'] != HELPER['digest'](plan_path): raise RuntimeError('applied lightning plan changed')
    before = json.loads((Path(applied['backup']) / 'sky-before.json').read_text())['gpu']; after = json.loads((ROOT / '.local/logs/unreal-sky-verified.json').read_text())['gpu']
    if before != after: raise RuntimeError('zero-flash sky GPU output changed')
    report = dict(status='success', plan_sha256=HELPER['digest'](plan_path), light_count=len(plan['lights']), sky_light_count=len(parameters),
                  world_triangles=baseline['world_triangles'], mover_triangles=baseline['mover_triangles'], sky_triangles=baseline['sky_triangles'], moon_triangles=baseline['moon_triangles'], idle_sky_gpu_identical=True, cloud_gpu=verify_gpu(plan))
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_LIGHTNING_VERIFY_SUCCESS'); return report


def verify_pie(plan_path, report_path):
    """Run with PIE active: read autoplay, then pause/seek every authored transition."""
    plan = HELPER['checked_plan'](plan_path)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world: raise RuntimeError('PIE world unavailable')
    actors = {a.get_actor_label(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)}
    player = actors['DistanceLightning_ue5'].get_editor_property('sequence_player'); autoplay = player.is_playing(); initial_time = player.get_current_time().time.frame_number.value
    if not autoplay or initial_time <= 0: raise RuntimeError('lightning did not autoplay')
    collection = unreal.load_asset(HELPER['COLLECTION']); player.pause()
    samples = sorted({0, plan['preview_time_ms'], plan['duration_ms'] - 1} | {time for e in plan['lights'] for time, value in e['schedule']['keys'] if time < plan['duration_ms']})
    try:
        for time in samples:
            player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(frame=unreal.FrameTime(unreal.FrameNumber(time)), position_type=unreal.MovieScenePositionType.FRAME, update_method=unreal.UpdatePositionMethod.JUMP))
            for entry in plan['lights']:
                value = value_at(entry['schedule']['keys'], time)
                c = actors[entry['name']].get_component_by_class(unreal.PointLightComponent)
                if not close(c.get_editor_property('intensity'), value * entry['peak_lumens']): raise RuntimeError('PIE lightning intensity differs: ' + entry['name'] + ' at ' + str(time))
                if entry['sky'] and not close(unreal.MaterialLibrary.get_scalar_parameter_value(world, collection, entry['collection_parameter']), value): raise RuntimeError('PIE lightning cloud pulse differs')
    finally:
        player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(time=0, position_type=unreal.MovieScenePositionType.TIME, update_method=unreal.UpdatePositionMethod.JUMP))
    report = dict(status='success', autoplay=True, initial_frame=initial_time, sample_times=len(samples), light_values_checked=len(samples) * len(plan['lights']), cloud_values_checked=len(samples) * sum(e['sky'] for e in plan['lights']))
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_LIGHTNING_PIE_SUCCESS'); return report


def verify_gpu(plan):
    """Exercise each sky pulse on the real cloud mesh and material, with a frozen UV clock."""
    from collections import Counter
    import hashlib
    import struct
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before = Counter(a.get_path_name() for a in actors.get_all_level_actors())
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    collection = unreal.load_asset(HELPER['COLLECTION'])
    moons = json.loads(Path(plan['moons_plan']).read_text()); sky = json.loads(Path(moons['sky_plan']).read_text())
    entry = next(e for e in sky['meshes'] if e['mode'] == 'sky_cloud'); data = json.loads((Path(moons['sky_plan']).parent / entry['source_file']).read_text())
    height = data['vertices'][0][2]
    preview = capture = target = None; reports = []
    try:
        preview = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(), transient=True)
        preview.static_mesh_component.set_static_mesh(unreal.load_asset(entry['asset_path']))
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, unreal.load_asset(entry['material_path']))
        mid.set_scalar_parameter_value('FollowCamera', 0); mid.set_vector_parameter_value('PanRate', unreal.LinearColor(0, 0, 0, 0))
        preview.static_mesh_component.set_material(0, mid)
        capture = actors.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(), transient=True)
        component = capture.get_component_by_class(unreal.SceneCaptureComponent2D)
        component.set_editor_property('capture_every_frame', False); component.set_editor_property('capture_on_movement', False)
        component.set_editor_property('primitive_render_mode', unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST); component.show_only_actor_components(preview)
        component.set_editor_property('fov_angle', 10); component.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
        component.set_editor_property('show_flag_settings', [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in ('Fog', 'VolumetricFog', 'Atmosphere', 'PostProcessing', 'TemporalAA', 'AntiAliasing', 'MotionBlur')])
        target = unreal.RenderingLibrary.create_render_target2d(world, 128, 128, unreal.TextureRenderTargetFormat.RTF_RGBA16F); component.set_editor_property('texture_target', target)
        for light in (e for e in plan['lights'] if e['sky']):
            point = unreal.Vector(*[(light['location'][i] - plan['sky_origin'][i]) * plan['projection_scale'] for i in (0, 1)], height)
            capture.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(), point), False)
            hashes = []; energies = []
            for value in (0, 1, 0):
                unreal.MaterialLibrary.set_scalar_parameter_value(world, collection, light['collection_parameter'], value)
                unreal.RenderingLibrary.clear_render_target2d(world, target, unreal.LinearColor(0, 0, 0, 1)); component.capture_scene()
                colors = unreal.RenderingLibrary.read_render_target_raw(world, target, False)
                if len(colors) != 128 * 128: raise RuntimeError('cloud lightning GPU dimensions differ')
                energies.append(sum(c.r + c.g + c.b for c in colors)); hashes.append(hashlib.sha256(b''.join(struct.pack('<fff', c.r, c.g, c.b) for c in colors)).hexdigest())
            if energies[0] <= 0 or energies[1] <= energies[0] * 1.05 or hashes[0] != hashes[2]: raise RuntimeError('cloud pulse GPU response/reset differs: ' + light['name'] + ' ' + str(energies))
            reports.append(dict(name=light['name'], off_on_off_energy=energies, off_reset_identical=True))
    finally:
        for light in (e for e in plan['lights'] if e['sky']): unreal.MaterialLibrary.set_scalar_parameter_value(world, collection, light['collection_parameter'], 0)
        if capture and not actors.destroy_actor(capture): raise RuntimeError('cloud capture cleanup failed')
        if preview and not actors.destroy_actor(preview): raise RuntimeError('cloud preview cleanup failed')
        if target: unreal.RenderingLibrary.release_render_target2d(target)
    if Counter(a.get_path_name() for a in actors.get_all_level_actors()) != before: raise RuntimeError('cloud diagnostic actors leaked')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise RuntimeError('cloud diagnostic cleanup save failed')
    return reports


def verify_loop(plan_path, report_path):
    """Schedule a one-second native playback check across the loop boundary."""
    import time
    plan = HELPER['checked_plan'](plan_path)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world: raise RuntimeError('PIE world unavailable')
    director = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.LevelSequenceActor) if a.get_actor_label() == 'DistanceLightning_ue5')
    player = director.get_editor_property('sequence_player'); player.pause()
    player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(time=plan['duration_ms'] / 1000 - 0.2, position_type=unreal.MovieScenePositionType.TIME, update_method=unreal.UpdatePositionMethod.JUMP))
    player.set_play_rate(1); player.play(); started = time.monotonic()
    def check(delta):
        if time.monotonic() - started < 1: return
        try:
            frame = player.get_current_time().time.frame_number.value
            if not player.is_playing() or not 0 < frame < 10000: raise RuntimeError('lightning player did not wrap: ' + str(frame))
            Path(report_path).write_text(json.dumps(dict(status='success', started_frame=plan['duration_ms'] - 200, wrapped_frame=frame, still_playing=True), indent=2) + '\n')
            unreal.log('UR_LIGHTNING_LOOP_SUCCESS')
        finally:
            player.pause(); player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(time=0, position_type=unreal.MovieScenePositionType.TIME, update_method=unreal.UpdatePositionMethod.JUMP))
            unreal.unregister_slate_post_tick_callback(handle)
    handle = unreal.register_slate_post_tick_callback(check)
    return 'pending; inspect the report after editor ticks'


if __name__ == '__main__':
    verify(ROOT / 'data/converted/Unreal/Maps/Unreal/lightning-ready/Unreal.lightning.json', ROOT / '.local/logs/unreal-lightning-verified.json')
