"""Reload and check the authored mood, source light colors and complete castle."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/src'))
from ue1_converter.mood_profile import load_profile


def close(actual, expected, label):
    if abs(actual - expected) > max(1e-5, abs(expected) * 1e-5):
        raise RuntimeError('mood setting differs: ' + label)


def linear(channel):
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def verify(profile_path, report_path):
    profile_path = Path(profile_path); profile = load_profile(profile_path); settings = profile['lighting']
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_water.py'))['verify'](
        ROOT / 'data/converted/Unreal/Maps/Unreal/water-ready/Unreal.water.json',
        ROOT / '.local/logs/unreal-water-verified.json', lighting_profile=profile_path)
    actors = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_mood.py'))['scene']()
    sun = actors['Unreal_KeyLight_ue5'].get_component_by_class(unreal.DirectionalLightComponent)
    for name, value in [('intensity', settings['sun_lux']), ('light_source_angle', settings['sun_source_angle']),
                        ('light_source_soft_angle', profile['sun_soft_angle']), ('cloud_shadow_strength', profile['cloud_shadow_strength'])]:
        close(sun.get_editor_property(name), value, name)
    rotation = sun.get_world_rotation()
    for name, value in settings['sun_rotation'].items(): close(getattr(rotation, name), value, 'sun ' + name)
    sky = actors['Unreal_SkyLight_ue5'].get_component_by_class(unreal.SkyLightComponent)
    close(sky.get_editor_property('intensity'), profile['sky_intensity'], 'sky intensity')
    for component in (sun, sky):
        color = component.get_editor_property('light_color')
        if (color.r, color.g, color.b, color.a) != (255, 255, 255, 255):
            raise RuntimeError('environment light tint differs')
    if sun.get_editor_property('use_temperature'): raise RuntimeError('sun temperature tint enabled')
    cloud = actors['Unreal_Clouds_ue5'].get_component_by_class(unreal.VolumetricCloudComponent)
    for prop, key in [('layer_bottom_altitude', 'cloud_bottom_km'), ('layer_height', 'cloud_height_km')]:
        close(cloud.get_editor_property(prop), profile[key], prop)
    atmosphere = actors['Unreal_Atmosphere_ue5'].get_component_by_class(unreal.SkyAtmosphereComponent)
    close(atmosphere.get_editor_property('mie_scattering_scale'), profile['mie_scattering_scale'], 'Mie scattering')
    fog = actors['Unreal_Fog_ue5'].get_component_by_class(unreal.ExponentialHeightFogComponent)
    for prop, value in [('fog_density', settings['fog_density']), ('start_distance', profile['fog_start_cm']),
                        ('fog_height_falloff', profile['fog_height_falloff'])]: close(fog.get_editor_property(prop), value, prop)
    pp = actors['Unreal_LumenExposure_ue5'].get_editor_property('settings')
    if not pp.get_editor_property('override_auto_exposure_bias') or any(pp.get_editor_property(k) for k in
            ('override_auto_exposure_min_brightness', 'override_auto_exposure_max_brightness')):
        raise RuntimeError('manual exposure overrides differ')
    lighting = json.loads((ROOT / 'data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json').read_text())
    colors = []
    for entry in lighting['lights']:
        color = actors[entry['name']].get_component_by_class(unreal.PointLightComponent).get_editor_property('light_color')
        # Allow only the existing 8-bit sRGB quantization of the recorded linear color.
        if color.a != 255 or any(abs(linear(v) - expected) > 0.009 for v, expected in zip((color.r, color.g, color.b), entry['color_linear'])):
            raise RuntimeError('source light color differs: ' + entry['name'])
        colors.append(dict(name=entry['name'], rgba=[color.r, color.g, color.b, color.a]))
    report = dict(status='success', profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                  settings=profile, source_light_colors=colors, world_triangles=baseline['world_triangles'],
                  mover_triangles=baseline['mover_triangles'], flame_triangles=baseline['flame_triangles'],
                  water_triangles=baseline['water_triangles'], water_gpu=baseline['gpu'])
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_MOOD_VERIFY_SUCCESS')
    return report


if __name__ == '__main__':
    verify(ROOT / 'tools/presets/Unreal_Gloom_ue5.json', ROOT / '.local/logs/unreal-mood-verified.json')
