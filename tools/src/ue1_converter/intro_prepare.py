"""Prepare a source-linked intro camera path and private original-audio resources."""
from bisect import bisect_right
import hashlib
import json
import math
from pathlib import Path
import struct

from .audio61 import decode_audio, render_it
from .material_prepare import safe_parts
from .native_bsp import _array, read_world_bsp
from .package61 import Package61, PackageError
from .sky_prepare import digest
from .t3d import number, parse_struct, parse_t3d
from .texture61 import properties, scalar

REFERENCES = {
    'intro': 'https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/Intro.uc',
    'linking': 'https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Classes/InterpolationPoint.uc',
    'curve': 'https://www.oldunreal.com/phpBB3/viewtopic.php?p=30028',
    'audio': 'https://github.com/libxmp/libxmp/blob/libxmp-4.6.0/include/xmp.h',
}


def segment_seconds(first_rate, next_rate):
    if not all(math.isfinite(v) and v > 0 for v in (first_rate, next_rate)): raise ValueError('camera rates must be positive and finite')
    delta = next_rate - first_rate
    return 1 / first_rate if abs(delta) < 1e-8 else math.log(next_rate / first_rate) / delta


def segment_alpha(first_rate, next_rate, seconds):
    duration = segment_seconds(first_rate, next_rate)
    if not math.isfinite(seconds) or not 0 <= seconds <= duration + 1e-9: raise ValueError('camera segment time outside range')
    delta = next_rate - first_rate
    return first_rate * seconds if abs(delta) < 1e-8 else first_rate * math.expm1(delta * seconds) / delta


def bspline(values, alpha):
    if len(values) != 4 or not 0 <= alpha <= 1: raise ValueError('four camera controls and bounded alpha required')
    a = alpha; weights = ((1 - a) ** 3 / 6, (3 * a ** 3 - 6 * a * a + 4) / 6, (-3 * a ** 3 + 3 * a * a + 3 * a + 1) / 6, a ** 3 / 6)
    return [sum(w * v[i] for w, v in zip(weights, values)) for i in range(len(values[0]))]


def linked_path(points):
    """Preserve ordered BeginPlay writes, including duplicate-position side effects."""
    if len(points) < 4: raise ValueError('intro requires at least four points')
    if any(not isinstance(p['position'], int) or not 0 <= p['position'] <= 127 for p in points): raise ValueError('invalid camera position index')
    starts = [i for i, p in enumerate(points) if p['position'] == 0]
    if len(starts) != 1: raise ValueError('intro requires exactly one start')
    previous = [None] * len(points); following = [None] * len(points)
    for i, p in enumerate(points):
        previous[i] = next((j for j, q in enumerate(points) if q['position'] == p['position'] - 1), None)
        if previous[i] is not None: following[previous[i]] = i
        following[i] = next((j for j, q in enumerate(points) if q['position'] == p['position'] + 1), starts[0])
        previous[following[i]] = i
    order = []; current = starts[0]
    while current not in order:
        order.append(current); current = following[current]
    if current != starts[0] or len(order) < 4 or any(previous[i] is None for i in order): raise ValueError('camera links do not form the supported loop')
    return dict(order=order, previous=previous, following=following, excluded=[i for i in range(len(points)) if i not in order])


def sample_camera(points, links, *, fps=60):
    if fps not in (30, 60): raise ValueError('unsupported camera sampling rate')
    starts = [0.0]
    for i in links['order']: starts.append(starts[-1] + segment_seconds(points[i]['rate'], points[links['following'][i]]['rate']))
    duration = starts[-1]; frames = math.ceil(duration * fps); samples = []
    for frame in range(frames + 1):
        time = min(frame / fps, duration); segment = min(len(starts) - 2, bisect_right(starts, time) - 1); i = links['order'][segment]
        nxt = links['following'][i]; after = links['following'][nxt]; prev = links['previous'][i]
        alpha = min(1.0, max(0.0, segment_alpha(points[i]['rate'], points[nxt]['rate'], time - starts[segment])))
        controls = [points[j] for j in (prev, i, nxt, after)]
        position = bspline([c['location'] for c in controls], alpha)
        angles = [[((v + 180) % 360) - 180 for v in c['rotation_degrees']] for c in controls]
        for row in range(1, 4):
            for axis in range(3): angles[row][axis] = angles[row - 1][axis] + (angles[row][axis] - angles[row - 1][axis] + 180) % 360 - 180
        rotation = bspline(angles, alpha)
        if samples:
            rotation = [old + (v - old + 180) % 360 - 180 for v, old in zip(rotation, samples[-1]['rotation'])]
        samples.append(dict(frame=frame, source_seconds=time, location=position, rotation=rotation))
    return dict(fps=fps, duration_seconds=duration, playback_frames=frames, segment_starts_seconds=starts, samples=samples)


def source_camera(package, document):
    level = next(e for e in package.exports if package.class_name(e) == 'Level'); reader, count = _array(package, level.index + 1, 'Level', 1)
    references = [reader.compact() for _ in range(count)]
    if any(not 0 <= ref <= len(package.exports) for ref in references): raise PackageError('invalid level actor reference')
    source = [(i, a) for i, a in enumerate(document.actors) if a.attribute('Class') == 'InterpolationPoint']
    exports = [package.exports[ref - 1] for ref in references if ref and package.class_name(package.exports[ref - 1]) == 'InterpolationPoint']
    if [e.name for e in exports] != [a.attribute('Name') for i, a in source]: raise PackageError('binary camera actor order differs from export')
    result = []
    for export, (index, actor) in zip(exports, source):
        props, reader = properties(package, export)
        if reader.offset != reader.end: raise PackageError('camera export has unexplained native data')
        def vector(name, kind):
            value = props.get((name, 0))
            if value is None:
                if name == 'Rotation': return [0, 0, 0]
                raise PackageError('camera location omitted')
            if value[0] != 10 or value[1] != kind or len(value[2]) != 12: raise PackageError('camera struct differs')
            return list(struct.unpack('<fff' if kind == 'Vector' else '<iii', value[2]))
        location = vector('Location', 'Vector'); rotation = vector('Rotation', 'Rotator')
        if not all(math.isfinite(v) for v in location): raise PackageError('non-finite camera location')
        text_rotation = {p.name: int(p.value) for p in parse_struct(actor.property('Rotation') or '()', actor.line)}
        if rotation != [text_rotation.get(k, 0) for k in ('Pitch', 'Yaw', 'Roll')]: raise PackageError('camera rotation evidence differs')
        position = scalar(props, 'Position', 2, 0)
        text_location = {p.name: number(p.value, p.line) for p in parse_struct(actor.property('Location'), actor.line)}
        if any(abs(location[i] - text_location[k]) > 0.02 for i, k in enumerate('XYZ')) or position != int(actor.property('Position') or 0): raise PackageError('camera binary/export evidence differs')
        raw_rate = props.get(('RateModifier', 0))
        if raw_rate is not None and (raw_rate[0] != 4 or len(raw_rate[2]) != 4): raise PackageError('invalid camera rate property')
        rate = struct.unpack('<f', raw_rate[2])[0] if raw_rate else 1.0
        if not math.isfinite(rate) or rate <= 0: raise PackageError('invalid camera rate')
        if abs(rate - float(actor.property('RateModifier') or 1)) > 1e-6: raise PackageError('camera rate evidence differs')
        if actor.property('Tag') != '"Path"' or any(actor.property(k) not in (None, '1.0', '1') for k in ('FovModifier', 'GameSpeedModifier', 'ScreenFlashScale')) or any(actor.property(k) not in (None, 'False') for k in ('bEndOfPath', 'bSkipNextPath')) or actor.property('ScreenFlashFog') is not None: raise PackageError('unsupported camera path controls')
        result.append(dict(source_actor_index=index, source_name=export.name, source_export_index=export.index, position=position, rate=rate, location=location,
                           rotation_units=rotation, rotation_degrees=[v * 360 / 65536 for v in rotation], raw_properties=[dict(name=p.name, value=p.value, line=p.line) for p in actor.properties]))
    return result


def prepare_intro(lightning_path, installation, library_path, destination):
    lightning_path, installation, destination = Path(lightning_path), Path(installation), Path(destination)
    if destination.exists(): raise FileExistsError(destination)
    lightning = json.loads(lightning_path.read_text()); moons = json.loads(Path(lightning['moons_plan']).read_text()); sky = json.loads(Path(moons['sky_plan']).read_text())
    for path, checksum in [(lightning['moons_plan'], lightning['moons_sha256']), (moons['sky_plan'], moons['sky_sha256']), *[(lightning[k + '_file'], lightning[k + '_sha256']) for k in ('source', 'package')], (sky['geometry_file'], sky['geometry_sha256'])]:
        if digest(path) != checksum: raise ValueError('intro provenance changed')
    package = Package61(Path(lightning['package_file']).read_bytes()); document = parse_t3d(Path(lightning['source_file']).read_text()); points = source_camera(package, document); links = linked_path(points); camera = sample_camera(points, links)
    bsp = read_world_bsp(package); audio = []; emitters = []; packages = {}; excluded = []
    level = next(a for a in document.actors if a.attribute('Class') == 'LevelInfo')
    if level.property('Song') != "Music'Flyby.Flyby'": raise ValueError('unsupported intro song')
    requests = [('Flyby.Flyby', 'Music')]
    for index, actor in enumerate(document.actors):
        sound = actor.property('AmbientSound')
        if not sound: continue
        if not sound.startswith("Sound'") or not sound.endswith("'"): raise ValueError('unsupported sound reference')
        fields = {p.name: number(p.value, p.line) for p in parse_struct(actor.property('Location'), actor.line)}; position = [fields[k] for k in 'XYZ']; zone = bsp.point_zone(position)
        if zone != 1: excluded.append(dict(source_actor_index=index, source_name=actor.attribute('Name'), reason='ambient sound outside active world', zone=zone)); continue
        path = sound[6:-1]; radius, volume, pitch = [int(actor.property(k) or default) for k, default in [('SoundRadius', 64), ('SoundVolume', 128), ('SoundPitch', 64)]]
        if any(not 0 <= v <= 255 for v in (radius, volume, pitch)) or pitch == 0: raise ValueError('invalid source sound controls')
        emitters.append(dict(name=actor.attribute('Name') + '_Ambient_ue5', source_actor_index=index, source_name=actor.attribute('Name'), sound=path, location=position, source_radius=radius, radius=radius * 25.0, source_volume=volume, volume=volume / 255 * 0.35, pitch=pitch / 64))
        requests.append((path, 'Sound'))
    files = {}
    for requested, kind in sorted(set(requests)):
        pack = requested.split('.')[0]; filename = installation / ('Music' if kind == 'Music' else 'Sounds') / (pack + ('.umx' if kind == 'Music' else '.uax'))
        p = Package61(filename.read_bytes(), allow_download_flag=True); matches = [e for e in p.exports if p.class_name(e) == kind and p.object_path(e.index + 1, pack).lower() == requested.lower()]
        if len(matches) != 1: raise PackageError('source audio reference unresolved: ' + requested)
        path = p.object_path(matches[0].index + 1, pack); data, metadata = decode_audio(p, path, pack, kind); packages[pack] = dict(file=str(filename.resolve()), sha256=digest(filename))
        if kind == 'Music': data, rendered = render_it(data, library_path); metadata['rendered'] = rendered
        pieces = safe_parts(path); name = pieces[-1]; rel = '/'.join(pieces[:-1] + [name + '_ue5.wav']); files[rel] = data
        audio.append(dict(requested_path=requested, path=path, source_file=rel, source_sha256=hashlib.sha256(data).hexdigest(), asset_path='/Game/Unreal/' + ('Music' if kind == 'Music' else 'Sounds') + '/' + '/'.join(pieces[:-1] + [name + '_ue5']), metadata=metadata))
    plan = dict(schema_version=1, lightning_plan=str(lightning_path.resolve()), lightning_sha256=digest(lightning_path), source_file=lightning['source_file'], source_sha256=lightning['source_sha256'], package_file=lightning['package_file'], package_sha256=lightning['package_sha256'],
                points=points, links=links, camera=camera, audio=audio, emitters=emitters, excluded_ambient=excluded, packages=packages, references=REFERENCES,
                base_horizontal_fov=90.0, source_aspect_ratio=4/3, aspect_ratio=16/9, horizontal_fov=math.degrees(2 * math.atan(math.tan(math.pi / 4) * (16/9) / (4/3))), music_volume=0.55,
                limitations=['Four-control cubic B-spline and analytic rate integration are an authored reconstruction, not a captured native frame/timing match', 'Raw source path height; native player eye-height/bob and rotation semantics remain to be compared', 'Original music rendered to PCM with installed libxmp; original tracker mixer and ambient attenuation are not an exact audio match', 'Camera loops independently of full-length music; birds, Nali, decoration meshes, triggered Movers and original HUD/menu remain separate work'])
    destination.mkdir()
    for name, data in files.items(): p = destination / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    (destination / 'Unreal.intro.json').write_text(json.dumps(plan, indent=2) + '\n'); return plan


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('lightning', type=Path); parser.add_argument('installation', type=Path); parser.add_argument('--libxmp', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); prepare_intro(args.lightning, args.installation, args.libxmp, args.output_dir)
