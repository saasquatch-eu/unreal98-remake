"""Verify saved camera curves, source PCM, spatial audio and the complete castle."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import runpy

import unreal

ROOT = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_experience.py'))
from ue1_converter.audio61 import compare_pcm


def close(a, b): return math.isclose(a, b, abs_tol=1e-5, rel_tol=2e-6)


def verify(plan_path, report_path):
    plan_path = Path(plan_path); plan = HELPER['checked_plan'](plan_path)
    if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(): raise RuntimeError('stop PIE before saved verification')
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_lightning.py'))['verify'](plan['lightning_plan'], ROOT / '.local/logs/unreal-lightning-verified.json')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(); actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    camera = actors[HELPER['CAMERA']]; component = camera.camera_component; sequence = unreal.load_asset(HELPER['SEQUENCE']); director = actors[HELPER['DIRECTOR']]
    for actual, expected in [(component.field_of_view, plan['horizontal_fov']), (component.aspect_ratio, plan['aspect_ratio']), (component.post_process_blend_weight, 0)]:
        if not close(actual, expected): raise RuntimeError('intro camera framing/exposure override differs')
    if not component.constrain_aspect_ratio or director.get_sequence() != sequence: raise RuntimeError('intro camera/director differs')
    settings = director.get_editor_property('playback_settings')
    if not settings.auto_play or settings.loop_count.value != -1 or not settings.disable_movement_input or not settings.disable_look_at_input or not settings.hide_hud or not settings.hide_player or settings.play_rate != 1: raise RuntimeError('intro playback settings differ')
    rate = sequence.get_display_rate(); tick = sequence.get_tick_resolution(); cp = plan['camera']
    if (rate.numerator, rate.denominator, tick.numerator, tick.denominator, sequence.get_playback_start(), sequence.get_playback_end()) != (cp['fps'], 1, 60000, 1, 0, cp['playback_frames']): raise RuntimeError('intro sequence timing differs')
    bindings = sequence.get_bindings()
    if len(bindings) != 1 or bindings[0].get_name() != HELPER['CAMERA'] or list(unreal.MovieSceneSequenceExtensions.locate_bound_objects(sequence, bindings[0], world)) != [camera]: raise RuntimeError('intro camera binding unresolved')
    tracks = bindings[0].get_tracks()
    if len(tracks) != 1 or not isinstance(tracks[0], unreal.MovieScene3DTransformTrack) or len(tracks[0].get_sections()) != 1: raise RuntimeError('intro transform track differs')
    section = tracks[0].get_sections()[0]; channels = section.get_all_channels()
    if section.get_start_frame() != 0 or section.get_end_frame() != cp['playback_frames'] or len(channels) != 9: raise RuntimeError('intro transform section differs')
    keys = [sorted(c.get_keys(), key=lambda k: k.get_time().frame_number.value) for c in channels[:6]]
    if any(len(k) != len(cp['samples']) for k in keys) or any(c.get_default() != 1 for c in channels[6:]): raise RuntimeError('intro transform key inventory/default scale differs')
    for sample in cp['samples']:
        pitch, yaw, roll = sample['rotation']; values = sample['location'] + [roll, pitch, yaw]
        for axis, value in enumerate(values):
            key = keys[axis][sample['frame']]
            if key.get_time().frame_number.value != sample['frame'] or not close(key.get_value(), value) or key.get_interpolation_mode() != unreal.RichCurveInterpMode.RCIM_LINEAR: raise RuntimeError('intro camera sample differs')
    cuts = sequence.get_tracks()
    if len(cuts) != 1 or not isinstance(cuts[0], unreal.MovieSceneCameraCutTrack) or len(cuts[0].get_sections()) != 1: raise RuntimeError('intro camera-cut track differs')
    cut = cuts[0].get_sections()[0]
    if cut.get_start_frame() != 0 or cut.get_end_frame() != cp['playback_frames'] or cut.get_camera_binding_id().get_editor_property('guid').export_text() != bindings[0].get_id().export_text(): raise RuntimeError('intro camera cut binding/range differs')
    floor = unreal.load_asset('/Game/Unreal/Materials/NaliCast/Floor/translucent/n-floor6_ue5')
    if floor.parent != unreal.load_asset('/Game/Unreal/Materials/UE5/Original_opaque_ue5'): raise RuntimeError('bridge floor presentation differs')
    folder = ROOT / '.local/intro-audio-readback' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); folder.mkdir(parents=True)
    sounds = {}; pcm_reports = []
    for e in plan['audio']:
        sound = unreal.load_asset(e['asset_path']); sounds[e['requested_path']] = sound
        metadata = e['metadata'].get('rendered', e['metadata'])
        if sound.get_editor_property('num_channels') != metadata['channels'] or sound.get_editor_property('sample_rate') != metadata['sample_rate'] or abs(sound.get_editor_property('duration') - metadata['duration_seconds']) > 0.001 or not sound.get_editor_property('looping') or sound.get_editor_property('virtualization_mode') != unreal.VirtualizationMode.PLAY_WHEN_SILENT: raise RuntimeError('intro imported sound properties differ')
        filename = folder / (sound.get_name() + '.wav'); task = unreal.AssetExportTask(); task.object = sound; task.exporter = unreal.SoundExporterWAV(); task.filename = str(filename); task.automated = True; task.prompt = False
        if not unreal.Exporter.run_asset_export_task(task): raise RuntimeError('intro PCM readback failed')
        comparison = compare_pcm((plan_path.parent / e['source_file']).read_bytes(), filename.read_bytes())
        pcm_reports.append(dict(asset=e['asset_path'], **comparison))
    music = actors[HELPER['MUSIC']].get_component_by_class(unreal.AudioComponent)
    if music.get_editor_property('sound') != sounds['Flyby.Flyby'] or music.allow_spatialization or not close(music.volume_multiplier, plan['music_volume']) or not music.get_editor_property('auto_activate'): raise RuntimeError('intro music component differs')
    for e in plan['emitters']:
        actor = actors[e['name']]; c = actor.get_component_by_class(unreal.AudioComponent); attenuation = c.attenuation_overrides
        if any(not close(getattr(actor.get_actor_location(), k), v) for k, v in zip('xyz', e['location'])): raise RuntimeError('intro ambient source position differs')
        if c.get_editor_property('sound') != sounds[e['sound']] or not c.allow_spatialization or not c.override_attenuation or not c.get_editor_property('auto_activate') or not close(c.volume_multiplier, e['volume']) or not close(c.pitch_multiplier, e['pitch']): raise RuntimeError('intro ambient component differs')
        if not attenuation.attenuate or not attenuation.spatialize or attenuation.distance_algorithm != unreal.AttenuationDistanceModel.LINEAR or attenuation.attenuation_shape != unreal.AttenuationShape.SPHERE or not close(attenuation.falloff_distance, e['radius']) or any(getattr(attenuation.attenuation_shape_extents, k) != 0 for k in 'xyz'): raise RuntimeError('intro ambient attenuation differs')
    report = dict(status='success', plan_sha256=HELPER['digest'](plan_path), camera_keys=len(cp['samples']) * 6, duration_seconds=cp['duration_seconds'], pcm=pcm_reports, ambient_emitters=len(plan['emitters']), world_triangles=baseline['world_triangles'], mover_triangles=baseline['mover_triangles'], sky_triangles=baseline['sky_triangles'], moon_triangles=baseline['moon_triangles'])
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_INTRO_VERIFY_SUCCESS'); return report



def verify_playback(plan_path, report_path):
    """In Play mode, check sample transforms, record output and observe a real loop."""
    import time
    plan = HELPER['checked_plan'](plan_path)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world: raise RuntimeError('Play world unavailable')
    actors = {a.get_actor_label(): a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)}
    camera = actors[HELPER['CAMERA']]; director = actors[HELPER['DIRECTOR']]; player = director.get_editor_property('sequence_player'); controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if not player.is_playing() or player.get_current_time().time.frame_number.value <= 0 or controller.get_view_target() != camera: raise RuntimeError('intro did not autoplay/control the player camera')
    audio = [actors[HELPER['MUSIC']].get_component_by_class(unreal.AudioComponent)] + [actors[e['name']].get_component_by_class(unreal.AudioComponent) for e in plan['emitters']]
    if not all(c.is_playing() for c in audio): raise RuntimeError('intro audio did not autoplay')
    player.pause(); samples = plan['camera']['samples']; frames = sorted({0, 60, 360, 720, 1140, 1740, 2280, 2880, plan['camera']['playback_frames'] - 1})
    for frame in frames:
        player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(frame=unreal.FrameTime(unreal.FrameNumber(frame)), position_type=unreal.MovieScenePositionType.FRAME, update_method=unreal.UpdatePositionMethod.JUMP))
        expected = samples[frame]; actual = camera.get_actor_location(); rotation = camera.get_actor_rotation()
        if any(not close(getattr(actual, k), v) for k, v in zip('xyz', expected['location'])) or any(abs((getattr(rotation, k) - v + 180) % 360 - 180) > 0.002 for k, v in zip(('pitch', 'yaw', 'roll'), expected['rotation'])): raise RuntimeError('live intro camera differs at frame ' + str(frame))
    player.set_playback_position(unreal.MovieSceneSequencePlaybackParams(time=0, position_type=unreal.MovieScenePositionType.TIME, update_method=unreal.UpdatePositionMethod.JUMP)); player.play()
    capture_name = 'unreal-intro-mix-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); unreal.AudioMixerLibrary.start_recording_output(world, 6)
    state = dict(previous_frame=0, recorded=False, progress=-1, started=time.monotonic(), ticks=0)
    def check(delta):
        try:
            state['ticks'] += 1; frame = player.get_current_time().time.frame_number.value; elapsed = time.monotonic() - state['started']
            if not state['recorded'] and elapsed >= 6:
                unreal.AudioMixerLibrary.stop_recording_output(world, unreal.AudioRecordingExportType.WAV_FILE, capture_name, str(ROOT / '.local')); state['recorded'] = True
            if int(elapsed // 10) > state['progress']:
                state['progress'] = int(elapsed // 10); unreal.log('UR_INTRO_PLAY_PROGRESS ' + str(round(elapsed, 1)) + ' seconds, frame ' + str(frame))
            if elapsed > 80: raise RuntimeError('intro player failed to complete its loop')
            if frame < state['previous_frame']:
                if not player.is_playing() or controller.get_view_target() != camera or not all(c.is_playing() for c in audio): raise RuntimeError('camera/audio did not continue across loop')
                report = dict(status='success', autoplay=True, player_camera_target=True, sampled_frames=frames, native_loop_wrap=True, wrapped_frame=frame, wall_seconds=elapsed, ticks=state['ticks'], playing_audio_components=len(audio), recorded_mix=str(ROOT / '.local' / (capture_name + '.wav')))
                Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_INTRO_PLAY_SUCCESS'); unreal.unregister_slate_post_tick_callback(handle)
                return
            state['previous_frame'] = frame
        except Exception as error:
            Path(report_path).write_text(json.dumps(dict(status='failure', error=str(error)), indent=2) + '\n'); unreal.log_error('UR_INTRO_PLAY_FAILURE ' + str(error)); unreal.unregister_slate_post_tick_callback(handle)
    handle = unreal.register_slate_post_tick_callback(check)
    return 'pending; keep Play running until the loop report is written'


if __name__ == '__main__': verify(ROOT / 'data/converted/Unreal/Maps/Unreal/intro-ready/Unreal.intro.json', ROOT / '.local/logs/unreal-intro-verified.json')
