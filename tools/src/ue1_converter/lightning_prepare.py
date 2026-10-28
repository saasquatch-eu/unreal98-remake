"""Prepare source-position lightning lights and a reproducible timer-range preview."""
from bisect import bisect_right
from collections import Counter
import colorsys
import json
import math
from pathlib import Path
import random

from .native_bsp import read_world_bsp
from .package61 import Package61
from .sky_prepare import digest
from .t3d import number, parse_struct, parse_t3d

REFERENCE = 'https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/DistanceLightning.uc'
DEFAULTS = dict(LightType='LT_Flicker', LightBrightness='255', LightHue='0', LightSaturation='255', LightRadius='56', LightPeriod='128', LightPhase='32')


def flash_schedule(seed, duration_ms=128000):
    """Source timer ranges; authored 40 ms flicker and a checked periodic boundary."""
    if not isinstance(duration_ms, int) or not 60000 <= duration_ms <= 600000: raise ValueError('invalid lightning preview duration')
    rng = random.Random(seed); first = rng.randrange(5000, 15000); start = first; bursts = []; keys = [[0, 0.0]]
    while True:
        end = start + rng.randrange(400, 450); bursts.append([start, end]); keys.append([start, 1.0])
        for time in range(start + 40, end, 40): keys.append([time, rng.choice([0.0, 0.2, 0.5, 0.8, 1.0])])
        keys.append([end, 0.0]); seam_gap = duration_ms - end + first
        if 9000 <= seam_gap < 29000: break
        maximum = min(28999, duration_ms - end - 449, seam_gap - 9000 - 449)
        if maximum < 9000: raise ValueError('cannot close lightning preview within source timer range')
        start = end + rng.randint(9000, maximum)
    keys.append([duration_ms, 0.0])
    return dict(bursts=bursts, keys=keys)


def value_at(keys, time_ms):
    times = [k[0] for k in keys]; index = bisect_right(times, time_ms) - 1
    return keys[max(0, index)][1]


def sky_attenuation(position, light_position, radius):
    if not math.isfinite(radius) or radius <= 0: raise ValueError('invalid sky lightning radius')
    if len(position) != 3 or len(light_position) != 3 or not all(math.isfinite(v) for v in (*position, *light_position)): raise ValueError('invalid sky lightning position')
    return max(0.0, 1 - math.dist(position, light_position) / radius) ** 2


def source_lightning(document, point_zone, sky_zone):
    names = Counter(a.attribute('Name') for a in document.actors if a.attribute('Class') == 'DistanceLightning')
    selected = []; excluded = []
    for index, actor in enumerate(document.actors):
        if actor.attribute('Class') != 'DistanceLightning': continue
        fields = {p.name: number(p.value, p.line) for p in parse_struct(actor.property('Location') or '', actor.line)}
        if set(fields) != set('XYZ'): raise ValueError('lightning requires complete explicit location')
        position = [fields[k] for k in 'XYZ']; zone = point_zone(position); name = actor.attribute('Name')
        identity = dict(source_actor_index=index, source_name=name, source_line=actor.line, zone=zone,
                        properties=[dict(name=p.name, value=p.value, line=p.line) for p in actor.properties])
        if zone not in (1, sky_zone):
            excluded.append(dict(**identity, reason='unselected sky or outside active world')); continue
        values = {k: actor.property(k) or v for k, v in DEFAULTS.items()}
        if values['LightType'] not in ('LT_Flicker', 'LT_Steady'): raise ValueError('unsupported exported lightning type')
        b, h, s, r = [int(values[k]) for k in ('LightBrightness', 'LightHue', 'LightSaturation', 'LightRadius')]
        if any(not 0 <= v <= 255 for v in (b, h, s, r)) or r == 0: raise ValueError('invalid lightning light byte')
        radius = r * 25.0 + 1; is_sky = zone == sky_zone
        # Explicit artistic calibration, distinct from native UE1 lighting units.
        lumens = (b / 255) * 4 * math.pi * (radius / 400) ** 2 * 50 * (1 if is_sky else 8)
        selected.append(dict(**identity, name=name + ('_Source' + str(index) if names[name] > 1 else '') + '_ue5', location=position,
                             sky=is_sky, radius=radius, peak_lumens=lumens, cast_shadows=not is_sky,
                             color_linear=colorsys.hsv_to_rgb(h / 255, 1 - s / 255, 1),
                             collection_parameter='Flash' + str(index) if is_sky else None, source_values=values,
                             defaulted_properties=[k for k in DEFAULTS if actor.property(k) is None],
                             schedule=flash_schedule(1998 + index * 65537)))
    return selected, excluded


def prepare_lightning(moons_path, destination):
    moons_path, destination = Path(moons_path), Path(destination)
    if destination.exists(): raise FileExistsError(destination)
    moons = json.loads(moons_path.read_text()); sky_path = Path(moons['sky_plan'])
    if digest(sky_path) != moons['sky_sha256']: raise ValueError('moon/sky provenance changed')
    sky = json.loads(sky_path.read_text())
    for key in ('geometry', 'source', 'package'):
        if digest(sky[key + '_file']) != sky[key + '_sha256']: raise ValueError('original map/export provenance changed')
    bsp = read_world_bsp(Package61(Path(sky['package_file']).read_bytes()))
    lights, excluded = source_lightning(parse_t3d(Path(sky['source_file']).read_text()), bsp.point_zone, sky['selected_sky']['zone'])
    if not lights: raise ValueError('no active lightning lights')
    candidates = sorted({start for e in lights for start, end in e['schedule']['bursts']})
    def score(time):
        world = sum(value_at(e['schedule']['keys'], time) for e in lights if not e['sky']); cloud = sum(value_at(e['schedule']['keys'], time) for e in lights if e['sky'])
        return (bool(world and cloud), world + cloud * 0.25)
    preview_time = max(candidates, key=score)
    plan = dict(schema_version=1, moons_plan=str(moons_path.resolve()), moons_sha256=digest(moons_path),
                source_file=sky['source_file'], source_sha256=sky['source_sha256'], package_file=sky['package_file'], package_sha256=sky['package_sha256'],
                sky_origin=sky['selected_sky']['origin'], projection_scale=sky['projection_scale'], lights=lights, excluded=excluded,
                duration_ms=128000, frame_rate=1000, flicker_step_ms=40, cloud_gain=32.0, preview_time_ms=preview_time, reference=REFERENCE,
                timer_ranges_seconds=dict(initial=[5, 15], burst=[0.4, 0.45], quiet=[9, 29]),
                limitations=['Deterministic 128-second loop and 40ms waveform approximate native random flicker; not native runtime timing',
                             'World-light lumens and cloud gain/falloff are artistic; native sky lighting, thunder and frame matching are not reconstructed',
                             'Source BeginPlay resets even exported steady lights to off; low-detail and out-of-bounds records stay excluded'])
    destination.mkdir(); (destination / 'Unreal.lightning.json').write_text(json.dumps(plan, indent=2) + '\n')
    return plan


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('moons', type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); prepare_lightning(args.moons, args.output_dir)
