"""Prepare the three source moon actors with checked local package evidence."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from .brush_math import cross, dot, matvec, rotation_matrix
from .material_prepare import safe_parts
from .moon69 import MoonPackage69, decode_mesh, decode_moon_texture
from .sky_prepare import digest
from .t3d import integer, number, parse_struct, parse_t3d
from .texture61 import tga_bytes
from .ue5_prepare import validate_buffers

REFERENCE = 'https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/'
DEFAULTS = {'Moon': dict(mesh='Moon1', skin='JMoon1', rate=(0, 500, 0)),
            'Moon2': dict(mesh='Moon1', skin='MoonTwo', rate=(300, -1000, 0)),
            'Moon3': dict(mesh='Moon3M', skin='JMoon3', rate=(0, 400, 100))}


def mesh_signature(mesh):
    result = Counter()
    for tri, uvs in zip(mesh.triangles, mesh.uvs, strict=True):
        corners = tuple(tuple(mesh.vertices[i]) + tuple(uv) for i, uv in zip(tri, uvs, strict=True))
        result[min(corners, corners[1:] + corners[:1], corners[2:] + corners[:2])] += 1
    return result


def components(actor, field, keys, defaults, convert=number):
    raw = actor.property(field)
    values = parse_struct(raw, actor.line) if raw else ()
    if len({v.name for v in values}) != len(values) or any(v.name not in keys for v in values): raise ValueError('invalid moon ' + field)
    result = dict(zip(keys, defaults, strict=True)); result.update({v.name: convert(v.value, v.line) for v in values})
    return tuple(result[k] for k in keys)


def moon_buffers(mesh, *, actor_location, actor_rotation, draw_scale, sky_origin, projection_scale):
    if not math.isfinite(draw_scale) or draw_scale <= 0 or not math.isfinite(projection_scale) or projection_scale <= 0:
        raise ValueError('invalid moon scale')
    if len(mesh.triangles) != len(mesh.uvs): raise ValueError('moon UV triangle count differs')
    if any(len(v) != 3 or not all(math.isfinite(x) for x in v) for v in (actor_location, sky_origin)):
        raise ValueError('invalid moon placement')
    mesh_rotation = rotation_matrix(mesh.rotation); actor_matrix = rotation_matrix(actor_rotation)
    pivot = [(a - b) * projection_scale for a, b in zip(actor_location, sky_origin, strict=True)]
    points = []
    for vertex in mesh.vertices:
        local = matvec(mesh_rotation, [(v - o) * s for v, o, s in zip(vertex, mesh.origin, mesh.scale, strict=True)])
        rotated = matvec(actor_matrix, local)
        points.append([p + v * draw_scale * projection_scale for p, v in zip(pivot, rotated, strict=True)])
    data = dict(vertices=[], normals=[], uv0=[], triangles=[])
    for tri, uv in zip(mesh.triangles, mesh.uvs, strict=True):
        a, b, c = [points[i] for i in tri]; n = cross([v - u for u, v in zip(a, b)], [v - u for u, v in zip(a, c)])
        length = math.sqrt(dot(n, n))
        if not length: raise ValueError('degenerate moon triangle')
        start = len(data['vertices']); data['vertices'].extend([a, b, c]); data['normals'].extend([[v / length for v in n]] * 3)
        data['uv0'].extend(uv); data['triangles'].append([start, start + 2, start + 1])
    validate_buffers(data)
    return data, pivot


def prepare_moons(sky_path, package_path, comparison_path, destination):
    sky_path, package_path, comparison_path, destination = map(Path, (sky_path, package_path, comparison_path, destination))
    if destination.exists(): raise FileExistsError(destination)
    sky = json.loads(sky_path.read_text())
    for key in ('geometry', 'source', 'package'):
        if digest(sky[key + '_file']) != sky[key + '_sha256']: raise ValueError('sky source provenance changed')
    source = MoonPackage69(package_path.read_bytes()); comparison = MoonPackage69(comparison_path.read_bytes())
    meshes = {}; textures = {}; evidence = {}
    for name in ('Moon1', 'Moon3M'):
        first, second = decode_mesh(source, name), decode_mesh(comparison, name)
        if mesh_signature(first) != mesh_signature(second) or (first.scale, first.origin, first.rotation) != (second.scale, second.origin, second.rotation):
            raise ValueError('installed moon geometry/UV/transform comparison differs')
        meshes[name] = first; evidence[name] = dict(source=first.metadata, comparison=second.metadata, exact_triangle_uv_transform_match=True)
    files = {}
    for name in ('JMoon1', 'MoonTwo', 'JMoon3'):
        first, second = decode_moon_texture(source, name), decode_moon_texture(comparison, name)
        if (first.width, first.height, first.pixels, first.palette) != (second.width, second.height, second.pixels, second.palette):
            raise ValueError('installed moon image comparison differs')
        parts = safe_parts(first.metadata['path']); filename = '/'.join(['Textures'] + parts[:-1] + [parts[-1] + '.tga']); raw = tga_bytes(first); files[filename] = raw
        textures[name] = dict(**first.metadata, comparison_export_sha256=second.metadata['export_sha256'], exact_pixel_palette_match=True,
                              source_file=filename, source_sha256=hashlib.sha256(raw).hexdigest(), asset_path='/Game/Unreal/Textures/' + '/'.join(parts[:-1] + [parts[-1] + '_ue5']))
    document = parse_t3d(Path(sky['source_file']).read_text()); actors = []
    for index, actor in enumerate(document.actors):
        cls = actor.attribute('Class')
        if cls not in DEFAULTS: continue
        defaults = DEFAULTS[cls]; name = actor.attribute('Name')
        if len(safe_parts('Moon.' + name)) != 2: raise ValueError('unsafe moon actor name')
        if any(actor.property(k) is not None for k in ('Mesh', 'Skin', 'DrawScale3D', 'PrePivot', 'Physics')): raise ValueError('unsupported moon instance override')
        location = components(actor, 'Location', 'XYZ', (math.nan,) * 3)
        rotation = components(actor, 'Rotation', ('Pitch', 'Yaw', 'Roll'), (0, 0, 0), integer)
        rate = components(actor, 'RotationRate', ('Pitch', 'Yaw', 'Roll'), defaults['rate'], integer)
        if rate[0] or rate[2]: raise ValueError('only observed yaw-only moon rotation supported')
        raw_scale = actor.property('DrawScale')
        if raw_scale is None: raise ValueError('moon requires explicit DrawScale')
        mesh = meshes[defaults['mesh']]; data, pivot = moon_buffers(mesh, actor_location=location, actor_rotation=rotation,
            draw_scale=number(raw_scale, actor.line), sky_origin=sky['selected_sky']['origin'], projection_scale=sky['projection_scale'])
        asset_name = name + '_ue5'; filename = asset_name + '.mesh.json'; raw = (json.dumps(data, allow_nan=False) + '\n').encode(); files[filename] = raw
        actors.append(dict(name=asset_name, source_name=name, source_actor_index=index, source_line=actor.line, actor_class=cls,
                           properties=[dict(name=p.name, value=p.value, line=p.line) for p in actor.properties], reference_defaults=REFERENCE + cls + '.uc',
                           source_mesh=defaults['mesh'], texture=textures[defaults['skin']]['path'],
                           asset_path='/Game/Unreal/Meshes/UnrealI/' + asset_name, source_file=filename, source_sha256=hashlib.sha256(raw).hexdigest(),
                           triangle_count=len(data['triangles']), rotation_pivot=pivot, rotation_units_per_second=rate, yaw_turns_per_second=rate[1] / 65536,
                           material_path='/Game/Unreal/Materials/UnrealI/Moons/' + asset_name))
    if len(actors) != 3: raise ValueError('expected three source moon actors')
    plan = dict(schema_version=1, sky_plan=str(sky_path.resolve()), sky_sha256=digest(sky_path),
                packages=[dict(file=str(p.resolve()), sha256=digest(p)) for p in (package_path, comparison_path)],
                meshes=actors, textures=list(textures.values()), evidence=evidence, preview_brightness=8.0,
                limitations=['Installed 227/UT99 resource payloads match; original v61 class defaults are not decoded',
                             'Source positions and transform metadata retained; phase, lighting and native frame matching remain unverified',
                             'Continuous yaw preview uses source rate with UE5 material time; native quantized physics timing is not emulated'])
    destination.mkdir()
    for filename, raw in files.items():
        target = destination / filename; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    (destination / 'Unreal.moons.json').write_text(json.dumps(plan, indent=2) + '\n')
    return plan


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('sky', 'package', 'comparison'): parser.add_argument(field, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path); args = parser.parse_args()
    prepare_moons(args.sky, args.package, args.comparison, args.output_dir)
