"""Extract a private, source-space Nali1 walk reference from the installed game."""

import argparse
import hashlib
import json
from pathlib import Path

from .nali69 import TargetPackage69, decode_nali_mesh
from .package61 import PackageError


SOURCE_SHA256 = 'ab2e571dd2e0bad0d8e4389f4d8bc1c7476a61d809de69ce2e7552511197864d'
MESH_SHA256 = '11643260bc3301b1d332cdac1735350f2873554c5afc6b5745909088c5e51df7'
SAFE_EXPORT_PREFIX = 13627


def obj_frame(mesh, index: int) -> bytes:
    """Diagnostic OBJ in scaled mesh-local coordinates, without actor motion."""
    frame = mesh.frame(index)
    lines = [f'# {mesh.name} source frame {index}; mesh origin/rotation not applied']
    for vertex in frame:
        lines.append('v ' + ' '.join(format(v * scale, '.9g') for v, scale in zip(vertex, mesh.scale)))
    for _, u, v in mesh.wedges:
        lines.append(f'vt {u / 256:.9g} {1 - v / 256:.9g}')
    for a, b, c, _ in mesh.faces:
        corners = [f'{mesh.wedges[w][0] + 1}/{w + 1}' for w in (a, b, c)]
        lines.append('f ' + ' '.join(corners))
    return ('\n'.join(lines) + '\n').encode('utf-8')


def prepare(package_path: Path, output_dir: Path):
    if output_dir.exists() or output_dir.resolve() == package_path.resolve():
        raise FileExistsError('Nali output must be a new directory')
    data = package_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise PackageError('installed UnrealShare.u differs from checked source package')
    package = TargetPackage69(data, {'Nali1', 'JNali1'}, minimum_exports=SAFE_EXPORT_PREFIX)
    mesh = decode_nali_mesh(package, 'Nali1', 'UnrealShare')
    if mesh.source['export_sha256'] != MESH_SHA256 or (mesh.vertex_count, mesh.frame_count, len(mesh.sequences), len(mesh.faces), len(mesh.wedges)) != (293, 397, 33, 568, 500):
        raise PackageError('Nali1 differs from checked source mesh')
    walk = next((s for s in mesh.sequences if s.name == 'Walk'), None)
    if walk is None or (walk.start, walk.count, walk.rate, walk.notifies) != (262, 20, 15.0, ((0.25, 'Step'), (0.75, 'Step'))):
        raise PackageError('Nali1 walk sequence differs from checked source')
    files = [(f'Nali1.Walk.frame{i:02}.obj', obj_frame(mesh, walk.start + i)) for i in range(walk.count)]
    report = dict(schema='nali-walk-reference-v1', source_package=str(package_path.resolve()),
                  source=mesh.source, mesh=mesh.name, frame_count=mesh.frame_count,
                  vertex_count=mesh.vertex_count, face_count=len(mesh.faces), scale=mesh.scale,
                  origin=mesh.origin, rotation=mesh.rotation,
                  sequences=[dict(name=s.name, group=s.group, start=s.start, count=s.count, rate=s.rate,
                                  notifies=[dict(time=t, event=event) for t, event in s.notifies]) for s in mesh.sequences],
                  walk=dict(start=walk.start, count=walk.count, rate=walk.rate,
                            nominal_seconds=walk.count / walk.rate,
                            notify_times=[dict(fraction=t, event=event) for t, event in walk.notifies],
                            frame_files=[dict(path=name, sha256=hashlib.sha256(payload).hexdigest()) for name, payload in files]),
                  limitations=['OBJ frames are scaled mesh-local source positions, not a rig or UE5 skeletal animation',
                               'Mesh origin/rotation, actor movement, native interpolation and playback-rate overrides are not applied',
                               'Only the required export-table prefix is validated; later unrelated records are not parsed'])
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in files:
        (output_dir / name).write_bytes(payload)
    (output_dir / 'Nali1.Walk.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path, help='checked installed UnrealShare.u')
    parser.add_argument('--output-dir', type=Path, required=True, help='new private destination')
    args = parser.parse_args()
    try:
        report = prepare(args.package, args.output_dir)
    except (OSError, PackageError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(dict(output_dir=str(args.output_dir), mesh=report['mesh'],
                          walk_frames=report['walk']['count'], vertices_per_frame=report['vertex_count'],
                          faces_per_frame=report['face_count'], source=report['source']), indent=2))


if __name__ == '__main__':
    main()
