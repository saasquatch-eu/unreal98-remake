"""Create a native looping flyby camera and independent original-audio emitters."""
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

SEQUENCE = '/Game/Unreal/Cinematics/Unreal_ue5'
CAMERA = 'Unreal_FlybyCamera_ue5'
DIRECTOR = 'Unreal_Intro_ue5'
MUSIC = 'Flyby_Music_ue5'


def checked_plan(path):
    path = Path(path); plan = json.loads(path.read_text())
    if plan['schema_version'] != 1: raise RuntimeError('unsupported intro plan')
    for file, checksum in [(plan['lightning_plan'], plan['lightning_sha256']), *[(plan[k + '_file'], plan[k + '_sha256']) for k in ('source', 'package')], *[(e['file'], e['sha256']) for e in plan['packages'].values()], *[(path.parent / e['source_file'], e['source_sha256']) for e in plan['audio']]]:
        if digest(file) != checksum: raise RuntimeError('intro provenance changed: ' + str(file))
    return plan


def build_presentation(plan, resources, actors, camera=None):
    assets = unreal.AssetToolsHelpers.get_asset_tools()
    camera_plan = plan['camera']; first = camera_plan['samples'][0]
    camera = camera or actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*first['location']), unreal.Rotator(*first['rotation'])); camera.set_actor_label(CAMERA)
    c = camera.camera_component; c.set_field_of_view(plan['horizontal_fov']); c.set_aspect_ratio(plan['aspect_ratio']); c.set_constraint_aspect_ratio(True); c.set_editor_property('post_process_blend_weight', 0)
    folder, name = SEQUENCE.rsplit('/', 1); sequence = assets.create_asset(name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if not sequence: raise RuntimeError('intro sequence creation failed')
    sequence.set_display_rate(unreal.FrameRate(camera_plan['fps'], 1)); sequence.set_tick_resolution_directly(unreal.FrameRate(60000, 1)); sequence.set_playback_start(0); sequence.set_playback_end(camera_plan['playback_frames'])
    binding = sequence.add_possessable(camera); binding.set_name(CAMERA); track = binding.add_track(unreal.MovieScene3DTransformTrack); section = track.add_section(); section.set_range(0, camera_plan['playback_frames'])
    channels = section.get_all_channels()
    if len(channels) != 9: raise RuntimeError('intro transform channel count differs')
    for channel in channels[6:]: channel.set_default(1)
    for sample in camera_plan['samples']:
        pitch, yaw, roll = sample['rotation']; values = sample['location'] + [roll, pitch, yaw]
        for channel, value in zip(channels[:6], values): channel.add_key(unreal.FrameNumber(sample['frame']), value, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    cut = sequence.add_track(unreal.MovieSceneCameraCutTrack).add_section(); cut.set_range(0, camera_plan['playback_frames']); binding_id = unreal.MovieSceneObjectBindingID(); binding_id.set_editor_property('guid', binding.get_id()); cut.set_camera_binding_id(binding_id)
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence): raise RuntimeError('intro sequence save failed')
    director = actors.spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector()); director.set_actor_label(DIRECTOR); director.set_sequence(sequence)
    playback = director.get_editor_property('playback_settings'); playback.auto_play = True; playback.loop_count = unreal.MovieSceneSequenceLoopCount(-1); playback.disable_movement_input = True; playback.disable_look_at_input = True; playback.hide_hud = True; playback.hide_player = True; director.set_editor_property('playback_settings', playback)
    music = actors.spawn_actor_from_class(unreal.AmbientSound, unreal.Vector()); music.set_actor_label(MUSIC); component = music.get_component_by_class(unreal.AudioComponent)
    component.set_sound(resources['Flyby.Flyby']); component.set_volume_multiplier(plan['music_volume']); component.set_editor_property('allow_spatialization', False)
    for entry in plan['emitters']:
        actor = actors.spawn_actor_from_class(unreal.AmbientSound, unreal.Vector(*entry['location'])); actor.set_actor_label(entry['name']); component = actor.get_component_by_class(unreal.AudioComponent)
        component.set_sound(resources[entry['sound']]); component.set_volume_multiplier(entry['volume']); component.set_pitch_multiplier(entry['pitch']); component.set_editor_property('allow_spatialization', True); component.set_editor_property('override_attenuation', True)
        attenuation = unreal.SoundAttenuationSettings(); attenuation.attenuate = True; attenuation.spatialize = True; attenuation.distance_algorithm = unreal.AttenuationDistanceModel.LINEAR; attenuation.attenuation_shape = unreal.AttenuationShape.SPHERE; attenuation.attenuation_shape_extents = unreal.Vector(); attenuation.falloff_distance = entry['radius']; component.set_editor_property('attenuation_overrides', attenuation)


def apply(plan_path):
    plan_path = Path(plan_path); plan = checked_plan(plan_path)
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_lightning.py'))['verify'](plan['lightning_plan'], ROOT / '.local/logs/unreal-lightning-verified.json')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); labels = {a.get_actor_label() for a in actors.get_all_level_actors()}
    names = {CAMERA, DIRECTOR, MUSIC} | {e['name'] for e in plan['emitters']}
    if names & labels or any(unreal.EditorAssetLibrary.does_asset_exist(p) for p in [SEQUENCE] + [e['asset_path'] for e in plan['audio']]): raise RuntimeError('intro destination exists; inspect partial state')
    if not level.save_current_level(): raise RuntimeError('intro pre-edit save failed')
    backup = ROOT / '.local/intro-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    shutil.copy2(Path(unreal.Paths.project_content_dir()) / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    assets = unreal.AssetToolsHelpers.get_asset_tools(); resources = {}
    for entry in plan['audio']:
        task = unreal.AssetImportTask(); task.filename = str(plan_path.parent / entry['source_file']); task.destination_path, task.destination_name = entry['asset_path'].rsplit('/', 1)
        task.automated = True; task.replace_existing = False; task.save = False; assets.import_asset_tasks([task])
        if len(task.imported_object_paths) != 1: raise RuntimeError('intro sound import failed')
        sound = unreal.load_asset(entry['asset_path'])
        if not isinstance(sound, unreal.SoundWave) or sound != unreal.load_asset(task.imported_object_paths[0]): raise RuntimeError('intro sound destination differs')
        sound.set_editor_property('looping', True); sound.set_editor_property('virtualization_mode', unreal.VirtualizationMode.PLAY_WHEN_SILENT)
        if entry['metadata']['kind'] == 'Music': sound.set_editor_property('sound_group', unreal.SoundGroup.SOUNDGROUP_MUSIC)
        if not unreal.EditorAssetLibrary.save_loaded_asset(sound): raise RuntimeError('intro sound save failed')
        resources[entry['requested_path']] = sound
    build_presentation(plan, resources, actors)
    if not level.save_current_level(): raise RuntimeError('intro map save failed')
    report = dict(status='success', backup=str(backup), plan_sha256=digest(plan_path), camera_frames=camera_plan['playback_frames'], duration_seconds=camera_plan['duration_seconds'], sounds=len(resources), ambient_emitters=len(plan['emitters']))
    (ROOT / '.local/logs/unreal-intro-apply.json').write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_INTRO_APPLIED'); return report


if __name__ == '__main__': apply(ROOT / 'data/converted/Unreal/Maps/Unreal/intro-ready/Unreal.intro.json')
