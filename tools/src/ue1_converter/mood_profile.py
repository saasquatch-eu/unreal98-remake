"""Read an authored lighting correction without changing source recipes."""
import json
import math
from pathlib import Path


def load_profile(path):
    profile = json.loads(Path(path).read_text())
    fields = {'sky_intensity', 'sun_soft_angle', 'cloud_shadow_strength', 'cloud_bottom_km', 'cloud_height_km',
              'fog_start_cm', 'fog_height_falloff', 'mie_scattering_scale', 'point_shadowed_scale', 'point_fill_scale'}
    light_fields = {'sun_lux', 'sun_rotation', 'sun_source_angle', 'exposure_bias', 'cloud_coverage', 'cloud_density', 'fog_density'}
    if set(profile) != fields | {'schema_version', 'lighting'} or profile['schema_version'] != 1 or set(profile['lighting']) != light_fields:
        raise ValueError('unsupported mood profile schema')
    lighting = profile['lighting']; rotation = lighting['sun_rotation']
    if set(rotation) != {'pitch', 'yaw', 'roll'}: raise ValueError('invalid key-light rotation')
    values = [profile[k] for k in fields] + [v for k, v in lighting.items() if k != 'sun_rotation'] + list(rotation.values())
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
        raise ValueError('mood profile requires finite numeric settings')
    for key in ('sky_intensity', 'cloud_shadow_strength', 'point_shadowed_scale', 'point_fill_scale'):
        if not 0 <= profile[key] <= 1: raise ValueError('invalid conservative light scale: ' + key)
    if not (0 < lighting['sun_lux'] <= 1000 and -14 <= lighting['exposure_bias'] <= 2 and -1 <= lighting['cloud_coverage'] <= 1):
        raise ValueError('invalid key/exposure/cloud setting')
    if any(lighting[k] < 0 for k in ('cloud_density', 'fog_density', 'sun_source_angle')) or any(profile[k] < 0 for k in fields):
        raise ValueError('negative lighting setting')
    return profile


def point_scale(entry, profile):
    return 1.0 if profile is None else profile['point_shadowed_scale' if entry['cast_shadows'] else 'point_fill_scale']
