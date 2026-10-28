"""Prepare a private camera-centered preview from compiled source sky geometry."""
import hashlib
import json
import math
from pathlib import Path

from .material_prepare import normalized_uvs, safe_parts
from .package61 import Package61
from .t3d import number, parse_struct, parse_t3d
from .texture61 import decode_texture, tga_bytes
from .ue5_prepare import validate_buffers


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sky_buffers(geometry, zone, origin, dimensions, *, scale=128.0):
    """Preserve source directions/UVs, separating surfaces by texture and flags."""
    if not math.isfinite(scale) or scale <= 0 or len(origin) != 3 or not all(math.isfinite(v) for v in origin):
        raise ValueError('invalid sky origin/scale')
    groups = {}
    for index, face in enumerate(geometry['faces']):
        if face['role'] != 'sky_geometry' or zone not in face['zones']: continue
        surface = geometry['surfaces'][face['surface']]; path = surface['texture']; flags = surface['flags']
        # This preview supports the observed opaque and translucent sky surfaces only.
        if flags & ~0x870c or bool(flags & 0x4) != bool(flags & 0x600):
            raise ValueError('unsupported sky surface flags')
        width, height = dimensions[path]; uv = normalized_uvs(face, width, height)
        key = (path, flags)
        group = groups.setdefault(key, dict(texture=path, flags=flags, source_faces=[], buffers=dict(vertices=[], normals=[], uv0=[], triangles=[])))
        group['source_faces'].append(index); data = group['buffers']
        for tri in face['triangles']:
            start = len(data['vertices'])
            for point in tri:
                data['vertices'].append([(v - o) * scale for v, o in zip(geometry['points'][point], origin)])
                data['normals'].append(surface['normal']); data['uv0'].append(uv[point])
            data['triangles'].append([start, start + 2, start + 1])
    if not groups: raise ValueError('selected sky zone has no geometry')
    for group in groups.values(): validate_buffers(group['buffers'])
    return list(groups.values())


def select_sky(geometry, document):
    matches = [(i, a) for i, a in enumerate(document.actors)
               if a.attribute('Class') == 'SkyZoneInfo' and a.property('bHighDetail') == 'True']
    if len(matches) != 1: raise ValueError('expected one explicit high-detail sky')
    index, actor = matches[0]; name = actor.attribute('Name')
    if len(safe_parts('Sky.' + name)) != 2: raise ValueError('unsafe sky actor name')
    zones = [z['index'] for z in geometry['zones'] if z['actor'] and z['actor'].split('.')[-1] == name]
    if len(zones) != 1: raise ValueError('sky actor has ambiguous compiled zone')
    fields = {p.name: number(p.value, p.line) for p in parse_struct(actor.property('Location') or '', actor.line)}
    if set(fields) != set('XYZ'): raise ValueError('sky requires explicit complete location')
    return dict(name=name, source_actor_index=index, source_line=actor.line, zone=zones[0],
                origin=[fields[k] for k in 'XYZ'], properties=[dict(name=p.name, value=p.value, line=p.line) for p in actor.properties])


def prepare_sky(geometry_path, source_path, package_path, texture_root, destination):
    geometry_path, source_path, package_path, texture_root, destination = map(Path, (geometry_path, source_path, package_path, texture_root, destination))
    if destination.exists(): raise FileExistsError(destination)
    geometry = json.loads(geometry_path.read_text())
    if geometry.get('schema_version') != 1: raise ValueError('unsupported geometry schema')
    if digest(source_path) != geometry['source']['sha256'] or digest(package_path) != geometry['package']['sha256']:
        raise ValueError('original map/export provenance changed')
    document = parse_t3d(source_path.read_text()); selected = select_sky(geometry, document)
    faces = [f for f in geometry['faces'] if f['role'] == 'sky_geometry' and selected['zone'] in f['zones']]
    paths = sorted({geometry['surfaces'][f['surface']]['texture'] for f in faces})
    packages = {}; textures = []; dimensions = {}; files = {}
    for path in paths:
        parts = safe_parts(path); name = parts[0]
        if name not in packages:
            source = texture_root / (name + '.utx'); raw = source.read_bytes()
            packages[name] = (Package61(raw, allow_download_flag=True), dict(file=str(source.resolve()), sha256=hashlib.sha256(raw).hexdigest()))
        texture = decode_texture(packages[name][0], path, name); dimensions[path] = (texture.width, texture.height)
        filename = '/'.join(['Textures'] + parts[:-1] + [parts[-1] + '.tga']); raw = tga_bytes(texture)
        files[filename] = raw
        textures.append(dict(**texture.metadata, source_file=filename, source_sha256=hashlib.sha256(raw).hexdigest(),
                             asset_path='/Game/Unreal/Textures/' + '/'.join(parts[:-1] + [parts[-1] + '_ue5'])))
    groups = sky_buffers(geometry, selected['zone'], selected['origin'], dimensions); meshes = []
    for index, group in enumerate(groups):
        name = selected['name'] + '_Surface' + str(index).zfill(2) + '_ue5'; filename = name + '.mesh.json'
        raw = (json.dumps(group['buffers'], allow_nan=False) + '\n').encode(); files[filename] = raw
        parts = safe_parts(group['texture']); mode = 'sky_cloud' if group['flags'] & 4 else 'sky_stars'
        # Preview rate is an authored 32 texels/second multiplier, not verified native timing.
        props = {p.name: p for p in document.actors[selected['source_actor_index']].properties}
        speed = [number(props[k].value, props[k].line) * 32 / dimensions[group['texture']][axis] if group['flags'] & bit else 0
                 for axis, k, bit in [(0, 'TexUPanSpeed', 0x200), (1, 'TexVPanSpeed', 0x400)]]
        meshes.append(dict(name=name, asset_path='/Game/Unreal/Meshes/Sky/' + name, source_file=filename,
                           source_sha256=hashlib.sha256(raw).hexdigest(), triangle_count=len(group['buffers']['triangles']),
                           source_faces=group['source_faces'], texture=group['texture'], flags=group['flags'], pan_uv_per_second=speed,
                           material_path='/Game/Unreal/Materials/' + '/'.join(parts[:-1] + [mode, parts[-1] + '_ue5']), mode=mode))
    deferred = [dict(source_actor_index=i, name=a.attribute('Name'), actor_class=a.attribute('Class'),
                     properties=[dict(name=p.name, value=p.value, line=p.line) for p in a.properties])
                for i, a in enumerate(document.actors) if a.attribute('Class') in ('Moon', 'Moon2', 'Moon3', 'DistanceLightning')]
    plan = dict(schema_version=1, geometry_file=str(geometry_path.resolve()), geometry_sha256=digest(geometry_path),
                source_file=str(source_path.resolve()), source_sha256=digest(source_path), package_file=str(package_path.resolve()), package_sha256=digest(package_path),
                selected_sky=selected, projection_scale=128.0, meshes=meshes, textures=textures,
                packages={k: v[1] for k, v in packages.items()}, deferred_actors=deferred,
                limitations=['Camera-centered source geometry; sky portals are approximated by existing world openings',
                             'Unlit source-image preview; original sky lighting and native scrolling timing are not matched',
                             'Moon meshes, lightning, coronas and low-detail sky remain deferred'])
    destination.mkdir()
    for filename, raw in files.items():
        target = destination / filename; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    (destination / 'Unreal.sky.json').write_text(json.dumps(plan, indent=2) + '\n')
    return plan


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('geometry', 'source', 'package'): parser.add_argument(name, type=Path)
    parser.add_argument('--texture-root', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(); prepare_sky(args.geometry, args.source, args.package, args.texture_root, args.output_dir)
