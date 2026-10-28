"""Synthetic v69 moon resources and transform/provenance checks; no game bytes."""
from dataclasses import replace
import hashlib
import json
import math
import struct

import pytest

from ue1_converter.moon69 import MoonPackage69, MoonMesh, decode_mesh, decode_moon_texture, unpack_vertex
from ue1_converter.moon_prepare import components, mesh_signature, moon_buffers, prepare_moons
from ue1_converter.package61 import Package61, PackageError
from ue1_converter.t3d import parse_t3d, integer


def ci(value):
    sign = 128 if value < 0 else 0; value = abs(value); result = bytearray([sign | (64 if value >= 64 else 0) | (value & 63)]); value >>= 6
    while value: result.append((128 if value >= 128 else 0) | (value & 127)); value >>= 7
    return bytes(result)


def fixture(*, kind='LodMesh', licensee=227, version=69, mesh_tail=b'', texture_tail=b'', bad_index=False, bad_endpoint=False, frames=1, special=False):
    names = ['None', 'Core', 'Class', kind, 'Palette', 'Texture', 'Moon1', 'Colors', 'Paint', 'PaletteData', 'USize', 'VSize', 'UBits', 'VBits']
    n = lambda name: ci(names.index(name))
    imports = b''.join(n('Core') + n('Class') + bytes(4) + n(name) for name in (kind, 'Palette', 'Texture'))
    name_data = b''.join(ci(len(s) + 1) + s.encode() + b'\0' + bytes(4) for s in names)
    start = 60 + len(name_data) + len(imports)
    box = struct.pack('<ffffffB', 0, 0, 0, 20, 20, 20, 1); sphere = struct.pack('<ffff', 10, 10, 10, 20)
    body = bytearray(n('None') + box + sphere)
    def array(fmt, values, lazy=False):
        raw = ci(len(values)) + b''.join(struct.pack('<' + fmt, *(v if isinstance(v, tuple) else (v,))) for v in values)
        if lazy: body.extend(struct.pack('<i', start + len(body) + 4 + len(raw) + int(bad_endpoint)))
        body.extend(raw)
    array('I', [0, 20, 20 << 11], True)
    triangles = [(0, 1, 9 if bad_index else 2, 0, 0, 255, 0, 0, 255, 0, 0)]
    array('HHHBBBBBBIi', triangles if kind == 'Mesh' else [], True); body.extend(ci(0))
    array('ii', [(1, 0), (1, 1), (1, 2)] if kind == 'Mesh' else [], True)
    body.extend(box + sphere); array('i', [0, 0, 0] if kind == 'Mesh' else [], True)
    body.extend(ci(1) + ci(3) + ci(1) + box + ci(1) + sphere)
    body.extend(struct.pack('<iiIIffffffiiiii', 3, frames, 0, 0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 0)); array('f', [1])
    if kind == 'LodMesh':
        array('H', [0, 1, 2]); array('H', [3]); array('HHHH', [(0, 1, 9 if bad_index else 2, 0)]); array('H', [0, 1, 2])
        array('HBB', [(0, 0, 0), (1, 255, 0), (2, 0, 255)]); array('Ii', [(0, 0)]); array('HHHH', [(0, 1, 2, 0)] if special else [])
        body.extend(struct.pack('<iifffiff', 3, int(special), 1, 0, 1, 1, 0, 0) + ci(0) + struct.pack('<i', 0))
    body.extend(mesh_tail)
    palette = n('None') + ci(256) + b''.join(bytes((i, 255 - i, i // 2, 0)) for i in range(256))
    texture_start = start + len(body) + len(palette)
    tag = lambda name, info, raw: n(name) + bytes([info]) + raw
    texture = b''.join(tag(name, 0x22, struct.pack('<i', 2)) for name in ('USize', 'VSize'))
    texture += b''.join(tag(name, 1, bytes([1])) for name in ('UBits', 'VBits')) + tag('Palette', 5, ci(2)) + n('None') + ci(1)
    data = ci(4) + bytes([0, 1, 2, 3]); texture += struct.pack('<i', texture_start + len(texture) + 4 + len(data)) + data + struct.pack('<iiBB', 2, 2, 1, 1) + texture_tail
    export_data = []; offset = start
    for cls, name, data in [(-1, 'Moon1', body), (-2, 'Colors', palette), (-3, 'Paint', texture)]:
        export_data.append(ci(cls) + ci(0) + bytes(4) + n(name) + bytes(4) + ci(len(data)) + ci(offset)); offset += len(data)
    header = struct.pack('<IHHIiiiiii', 0x9e2a83c1, version, licensee, 1, len(names), 60, 3, offset, 3, 60 + len(name_data))
    return header.ljust(60, b'\0') + name_data + imports + body + palette + texture + b''.join(export_data)


@pytest.mark.parametrize('licensee', [0, 227])
def test_resource_reader_admits_only_explicit_package_profile_without_relaxing_map_reader(licensee):
    raw = fixture(licensee=licensee)
    assert MoonPackage69(raw).licensee == licensee
    with pytest.raises(PackageError): Package61(raw, allow_download_flag=True)
    for changed in (dict(version=68), dict(licensee=228)):
        with pytest.raises(PackageError): MoonPackage69(fixture(**changed))


def test_mesh_and_lod_representations_have_identical_full_detail_geometry_uvs():
    a = decode_mesh(MoonPackage69(fixture(kind='Mesh')), 'Moon1'); b = decode_mesh(MoonPackage69(fixture()), 'Moon1')
    assert mesh_signature(a) == mesh_signature(b)
    assert a.vertices == [(0, 0, 0), (20, 0, 0), (0, 20, 0)]
    assert a.uvs == [[[0, 0], [255 / 256, 0], [0, 255 / 256]]]
    assert a.scale == (1, 2, 3) and a.origin == (0, 0, 0) and a.texture == 'UnrealI.Paint'


@pytest.mark.parametrize('changes', [dict(mesh_tail=b'?'), dict(bad_index=True), dict(bad_endpoint=True), dict(frames=2), dict(special=True)])
def test_unsupported_or_malformed_mesh_records_fail(changes):
    with pytest.raises(PackageError): decode_mesh(MoonPackage69(fixture(**changes)), 'Moon1')


def test_signed_packed_vertices_keep_all_bits_and_axes():
    assert unpack_vertex(0x7ff | (0x400 << 11) | (0x200 << 22)) == (-1, -1024, -512)
    assert unpack_vertex(1023 | (1023 << 11) | (511 << 22)) == (1023, 1023, 511)


def test_texture_exact_palette_pixels_and_opaque_index_zero():
    raw = fixture(); before = hashlib.sha256(raw).hexdigest(); texture = decode_moon_texture(MoonPackage69(raw), 'Paint')
    assert texture.pixels == bytes([0, 1, 2, 3]) and texture.rgba()[:8] == bytes([0, 255, 0, 255, 1, 254, 0, 255])
    assert texture.metadata['pixels_sha256'] == hashlib.sha256(bytes([0, 1, 2, 3])).hexdigest()
    assert hashlib.sha256(raw).hexdigest() == before
    with pytest.raises(PackageError): decode_moon_texture(MoonPackage69(fixture(texture_tail=b'?')), 'Paint')


def mesh():
    return MoonMesh([(0, 0, 0), (2, 0, 0), (0, 2, 0)], [[0, 1, 2]], [[[0, 0], [1, 0], [0, 1]]], 'Synthetic.Paint', (2, 3, 4), (1, 0, 0), (0, 0, 0), {})


def test_actor_drawscale_mesh_origin_anisotropic_scale_and_sky_projection():
    data, pivot = moon_buffers(mesh(), actor_location=[20, 30, 40], actor_rotation=[0, 16384, 0], draw_scale=0.5, sky_origin=[10, 20, 30], projection_scale=2)
    assert pivot == [20, 20, 20]
    assert data['vertices'][0] == pytest.approx([20, 18, 20])
    assert data['vertices'][1] == pytest.approx([20, 22, 20])
    assert data['vertices'][2] == pytest.approx([14, 18, 20])
    assert data['triangles'] == [[0, 2, 1]] and data['uv0'] == [[0, 0], [1, 0], [0, 1]]


@pytest.mark.parametrize('scale', [0, -1, math.nan, math.inf])
def test_invalid_moon_scale_rejected(scale):
    with pytest.raises(ValueError): moon_buffers(mesh(), actor_location=[0]*3, actor_rotation=[0]*3, draw_scale=scale, sky_origin=[0]*3, projection_scale=128)


def test_partial_rotation_rate_overrides_preserve_reference_components():
    actor = parse_t3d('Begin Map\nBegin Actor Class=Moon3 Name=M\nRotationRate=(Yaw=0,Roll=0)\nEnd Actor\nEnd Map\n').actors[0]
    assert components(actor, 'RotationRate', ('Pitch', 'Yaw', 'Roll'), (0, 400, 100), integer) == (0, 0, 0)


def test_moon_preparation_refuses_overwrite_and_mismatching_sky_provenance(tmp_path):
    dest = tmp_path / 'ready'; dest.mkdir()
    with pytest.raises(FileExistsError): prepare_moons('missing', 'missing', 'missing', dest)
    source = tmp_path / 'source'; source.write_bytes(b'synthetic')
    sky = tmp_path / 'sky.json'; sky.write_text(json.dumps(dict(geometry_file=str(source), geometry_sha256='changed')))
    with pytest.raises(ValueError, match='provenance'): prepare_moons(sky, 'missing', 'missing', tmp_path / 'new')
    assert not (tmp_path / 'new').exists()


def preparation_fixture(tmp_path, monkeypatch, *, mismatch=False):
    import ue1_converter.moon_prepare as module
    from ue1_converter.texture61 import Texture
    source_package = tmp_path / 'source.u'; source_package.write_bytes(fixture())
    comparison_package = tmp_path / 'comparison.u'; comparison_package.write_bytes(fixture(licensee=0))
    geometry = tmp_path / 'geometry.json'; geometry.write_text('{}')
    package = tmp_path / 'map.unr'; package.write_bytes(b'authored synthetic map')
    source = tmp_path / 'source.t3d'
    text = 'Begin Map\n'
    for name, cls, scale, rate in [('A', 'Moon', 1, '(Yaw=-100)'), ('B', 'Moon3', 0.5, '(Yaw=0,Roll=0)'), ('C', 'Moon2', 0.8, '(Pitch=0,Yaw=-300)')]:
        text += f'Begin Actor Class={cls} Name={name}\nDrawScale={scale}\nLocation=(X=10,Y=20,Z=30)\nRotationRate={rate}\nEnd Actor\n'
    source.write_text(text + 'End Map\n')
    sky = dict(selected_sky=dict(origin=[0, 0, 0]), projection_scale=2)
    for key, path in [('geometry', geometry), ('package', package), ('source', source)]:
        sky[key + '_file'] = str(path); sky[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    sky_path = tmp_path / 'sky.json'; sky_path.write_text(json.dumps(sky))
    def decode(package, name):
        value = decode_mesh(package, 'Moon1')
        if mismatch and package.licensee == 0: value = replace(value, vertices=[(1, 0, 0), *value.vertices[1:]])
        return replace(value, metadata=dict(value.metadata, name=name))
    def texture(package, name):
        value = decode_moon_texture(package, 'Paint')
        return replace(value, metadata=dict(value.metadata, path='UnrealI.Skins.' + name))
    monkeypatch.setattr(module, 'decode_mesh', decode); monkeypatch.setattr(module, 'decode_moon_texture', texture)
    return sky_path, source_package, comparison_package


def test_full_preparation_preserves_actor_order_rates_evidence_and_output_hashes(tmp_path, monkeypatch):
    args = preparation_fixture(tmp_path, monkeypatch); plan = prepare_moons(*args, tmp_path / 'ready')
    assert [e['name'] for e in plan['meshes']] == ['A_ue5', 'B_ue5', 'C_ue5']
    assert [e['yaw_turns_per_second'] for e in plan['meshes']] == [-100 / 65536, 0, -300 / 65536]
    assert [e['source_mesh'] for e in plan['meshes']] == ['Moon1', 'Moon3M', 'Moon1']
    assert all(e['exact_triangle_uv_transform_match'] for e in plan['evidence'].values())
    assert all(e['exact_pixel_palette_match'] for e in plan['textures'])
    for entry in plan['meshes'] + plan['textures']:
        assert hashlib.sha256((tmp_path / 'ready' / entry['source_file']).read_bytes()).hexdigest() == entry['source_sha256']
    with pytest.raises(FileExistsError): prepare_moons(*args, tmp_path / 'ready')


def test_cross_installation_mesh_mismatch_prevents_output(tmp_path, monkeypatch):
    args = preparation_fixture(tmp_path, monkeypatch, mismatch=True)
    with pytest.raises(ValueError, match='comparison differs'): prepare_moons(*args, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_package_tables_names_and_palette_bounds_fail_closed():
    raw = bytearray(fixture()); bad = bytearray(raw); struct.pack_into('<i', bad, 16, 20)
    with pytest.raises(PackageError): MoonPackage69(bytes(bad))
    bad = bytearray(raw); bad[60] = 0
    with pytest.raises(PackageError): MoonPackage69(bytes(bad))
    package = MoonPackage69(bytes(raw)); palette = next(e for e in package.exports if e.name == 'Colors')
    raw[palette.offset + 1:palette.offset + 3] = ci(255)
    with pytest.raises(PackageError, match='256 colors'): decode_moon_texture(MoonPackage69(bytes(raw)), 'Paint')
