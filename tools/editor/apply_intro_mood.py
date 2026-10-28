"""Apply a reversible source-informed lighting correction to the checked castle."""
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
from ue1_converter.mood_profile import load_profile, point_scale


def scene():
    if Path(unreal.Paths.get_project_file_path()).stem != 'UnrealGoldRemake': raise RuntimeError('wrong project')
    return {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}


def apply(profile_path, *, previous_profile=None):
    profile_path = Path(profile_path); profile = load_profile(profile_path); settings = profile['lighting']
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    scene()
    if level.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('stop PIE and save first')
    runpy.run_path(str(ROOT / 'tools/editor/verify_intro_water.py'))['verify'](
        ROOT / 'data/converted/Unreal/Maps/Unreal/water-ready/Unreal.water.json', ROOT / '.local/logs/unreal-water-verified.json', lighting_profile=previous_profile)
    actors = scene(); lighting_path = ROOT / 'data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json'
    lighting = json.loads(lighting_path.read_text())
    clouds = actors['Unreal_Clouds_ue5'].get_component_by_class(unreal.VolumetricCloudComponent)
    material = clouds.get_editor_property('material'); material_path = material.get_path_name().split('.')[0]
    if not material_path.startswith('/Game/Unreal/'): raise RuntimeError('cloud instance must be project-local')
    if not level.save_current_level() or not unreal.EditorAssetLibrary.save_loaded_asset(material, False): raise RuntimeError('pre-edit save failed')
    backup = ROOT / '.local/gloom-recovery' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup.mkdir(parents=True)
    content = Path(unreal.Paths.project_content_dir()).resolve()
    shutil.copy2(content / 'Unreal/Maps/Unreal_ue5.umap', backup / 'Unreal_ue5.umap')
    shutil.copy2(content / (material_path.removeprefix('/Game/') + '.uasset'), backup / 'Unreal_Clouds_ue5.uasset')
    shutil.copy2(profile_path, backup / 'applied-profile.json')
    before = {}
    for entry in lighting['lights']:
        c = actors[entry['name']].get_component_by_class(unreal.PointLightComponent); color = c.get_editor_property('light_color')
        before[entry['name']] = dict(intensity=c.get_editor_property('intensity'), color=[color.r, color.g, color.b, color.a])
    (backup / 'point-lights-before.json').write_text(json.dumps(before, indent=2) + '\n')
    # Remove the sunset direction before adjusting sky, clouds and exposure.
    sun = actors['Unreal_KeyLight_ue5'].get_component_by_class(unreal.DirectionalLightComponent); sun.modify()
    sun.set_intensity(settings['sun_lux']); sun.set_world_rotation(unreal.Rotator(**settings['sun_rotation']), False, False)
    sun.set_light_source_angle(settings['sun_source_angle']); sun.set_light_source_soft_angle(profile['sun_soft_angle'])
    sun.set_editor_property('cloud_shadow_strength', profile['cloud_shadow_strength'])
    sky = actors['Unreal_SkyLight_ue5'].get_component_by_class(unreal.SkyLightComponent); sky.modify(); sky.set_intensity(profile['sky_intensity'])
    for name, value in [('Cloud_GlobalCoverage', settings['cloud_coverage']), ('Cloud_GlobalDensity', settings['cloud_density'])]:
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material, name, value)
    clouds.modify(); clouds.set_layer_bottom_altitude(profile['cloud_bottom_km']); clouds.set_layer_height(profile['cloud_height_km'])
    atmo = actors['Unreal_Atmosphere_ue5'].get_component_by_class(unreal.SkyAtmosphereComponent); atmo.modify()
    atmo.set_editor_property('mie_scattering_scale', profile['mie_scattering_scale'])
    fog = actors['Unreal_Fog_ue5'].get_component_by_class(unreal.ExponentialHeightFogComponent); fog.modify()
    fog.set_fog_density(settings['fog_density']); fog.set_start_distance(profile['fog_start_cm']); fog.set_fog_height_falloff(profile['fog_height_falloff'])
    volume = actors['Unreal_LumenExposure_ue5']; volume.modify(); pp = volume.get_editor_property('settings')
    pp.set_editor_property('override_auto_exposure_bias', True); pp.set_editor_property('auto_exposure_bias', settings['exposure_bias'])
    volume.set_editor_property('settings', pp)
    for entry in lighting['lights']:
        c = actors[entry['name']].get_component_by_class(unreal.PointLightComponent); c.modify()
        # Absolute source-recipe calibration prevents cumulative dimming on refinement.
        c.set_intensity(entry['intensity_lumens'] * point_scale(entry, profile))
        color = c.get_editor_property('light_color')
        if [color.r, color.g, color.b, color.a] != before[entry['name']]['color']: raise RuntimeError('source light hue changed')
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False) or not level.save_current_level(): raise RuntimeError('mood save failed')
    report = dict(status='success', backup=str(backup), profile=str(profile_path.resolve()),
                  applied_profile=str(backup / 'applied-profile.json'), profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest())
    (ROOT / '.local/logs/unreal-mood-apply.json').write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_MOOD_APPLIED')
    return report


if __name__ == '__main__':
    apply(ROOT / 'tools/presets/Unreal_Gloom_ue5.json')
