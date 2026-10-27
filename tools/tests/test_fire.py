"""Synthetic FireTexture byte layouts and animation/atlas invariants."""
import hashlib
import struct
from dataclasses import replace

import pytest

from ue1_converter.fire61 import decode_fire, render_fire, atlas_tga, Fire
from ue1_converter.package61 import Package61, PackageError


def compact(value):
    assert 0 <= value < 64
    return bytes([value])


def fixture(*, sparks=((5, 180, 3, 5, 11, 22, 33, 44),), count=None, mip_count=1, tail=b'', palette_ref=2, kind='FireTexture', dims=(8, 8), palette_count=256):
    names = ['None', 'Core', 'Class', kind, 'Palette', 'Flame', 'USize', 'VSize', 'UBits', 'VBits', 'RenderHeat', 'bRising', 'NumSparks']
    n = lambda key: compact(names.index(key))
    imports = b''.join(n('Core') + n('Class') + bytes(4) + n(k) for k in (kind, 'Palette'))
    tag = lambda key, t, raw: n(key) + bytes([t]) + raw
    body = b''.join(tag(k, 0x22, struct.pack('<i', v)) for k, v in zip(('USize', 'VSize'), dims))
    body += b''.join(tag(k, 1, bytes([v.bit_length() - 1])) for k, v in zip(('UBits', 'VBits'), dims))
    body += tag('Palette', 5, compact(palette_ref)) + tag('RenderHeat', 1, bytes([226]))
    body += tag('bRising', 0x83, b'') + tag('NumSparks', 0x22, struct.pack('<i', len(sparks) if count is None else count)) + n('None')
    body += compact(mip_count) + compact(0) + struct.pack('<iiBB', *dims, *(v.bit_length() - 1 for v in dims))
    body += compact(len(sparks)) + b''.join(bytes(s) for s in sparks) + tail
    # 256 is compact-encoded as 0x40, 0x04.
    palette = n('None') + (bytes([0x40, 4]) if palette_count == 256 else compact(palette_count)) + bytes(range(256)) * 4
    name_data = b''.join(s.encode() + b'\0' + bytes(4) for s in names)
    io = 60 + len(name_data); offset = io + len(imports); table = []
    def idx(v):
        sign = 128 if v < 0 else 0; v = abs(v); out = bytearray([sign | (64 if v >= 64 else 0) | (v & 63)]); v >>= 6
        while v: out.append((128 if v >= 128 else 0) | (v & 127)); v >>= 7
        return bytes(out)
    for cls, data in ((-1, body), (-2, palette)):
        table.append(idx(cls) + idx(0) + bytes(4) + n('Flame') + bytes(4) + idx(len(data)) + idx(offset)); offset += len(data)
    header = struct.pack('<IHHIiiiiii', 0x9e2a83c1, 61, 0, 1, len(names), 60, 2, offset, 2, io)
    return header.ljust(60, b'\0') + name_data + imports + body + palette + b''.join(table)


def decode(raw):
    return decode_fire(Package61(raw, allow_download_flag=True), 'Demo.Flame', 'Demo')


def test_fire_exact_native_records_palette_and_source_immutability():
    raw = fixture(); before = hashlib.sha256(raw).hexdigest(); fire = decode(raw)
    assert (fire.width, fire.height, fire.render_heat, fire.rising) == (8, 8, 226, True)
    assert fire.sparks == ((5, 180, 3, 5, 11, 22, 33, 44),)
    assert fire.metadata['sparks'][0]['byte_d'] == 44
    assert fire.palette == bytes(range(256)) * 4
    assert fire.metadata['defaulted_properties'] == ['DrawMode']
    assert hashlib.sha256(raw).hexdigest() == before


@pytest.mark.parametrize('change', [dict(count=2), dict(mip_count=2), dict(tail=b'!'), dict(palette_ref=1), dict(kind='Texture'), dict(dims=(3, 8)), dict(palette_count=3), dict(sparks=((5, 180, 8, 5, 0, 0, 0, 0),)), dict(sparks=((29, 180, 3, 5, 0, 0, 0, 0),))])
def test_invalid_native_fire_is_rejected(change):
    with pytest.raises(PackageError): decode(fixture(**change))


def test_animation_is_deterministic_changes_over_time_and_keeps_inputs():
    fire = decode(fixture()); before = fire.sparks
    frames = render_fire(fire, frames=16, warmup=12, seed=9)
    assert frames == render_fire(fire, frames=16, warmup=12, seed=9)
    assert len(set(frames)) > 4 and all(len(f) == 64 for f in frames)
    assert any(any(f) for f in frames) and fire.sparks == before
    assert frames != render_fire(fire, frames=16, warmup=12, seed=10)


def test_preview_rejects_unimplemented_native_motion_instead_of_silently_substituting():
    fire = decode(fixture(sparks=((23, 180, 3, 5, 0, 0, 0, 0),)))
    with pytest.raises(ValueError): render_fire(fire)
    with pytest.raises(ValueError): render_fire(replace(decode(fixture()), draw_mode=4))


@pytest.mark.parametrize('kwargs', [dict(frames=0), dict(frames=257), dict(warmup=-1), dict(warmup=1025)])
def test_invalid_animation_allocation_is_rejected(kwargs):
    with pytest.raises(ValueError): render_fire(decode(fixture()), **kwargs)


def test_atlas_palette_alpha_padding_and_top_row_frame_order():
    palette = bytes([0, 0, 0, 0, 10, 20, 30, 0, 40, 50, 60, 0]) + bytes(1012)
    fire = Fire(2, 1, palette, (), 226, True, 0, {})
    tga = atlas_tga(fire, [bytes([1, 2]), bytes([2, 1])], columns=1, padding=1)
    assert struct.unpack_from('<HH', tga, 12) == (4, 6)
    pixels = tga[18:]
    def pixel(x, y): return pixels[(y * 4 + x) * 4:(y * 4 + x + 1) * 4]
    assert pixel(1, 1) == bytes([30, 20, 10, 255])
    assert pixel(1, 4) == bytes([60, 50, 40, 255])
    assert pixel(0, 0) == bytes(4) and pixel(3, 4) == bytes(4)


def test_atlas_refuses_inconsistent_or_excessive_dimensions():
    fire = decode(fixture())
    with pytest.raises(ValueError): atlas_tga(fire, [bytes(1)], columns=1)
    with pytest.raises(ValueError): atlas_tga(fire, [bytes(64)] * 3, columns=2)
    with pytest.raises(ValueError): atlas_tga(fire, [bytes(64)], columns=1, padding=17)


def prepared_fixture(tmp_path, *, nanite=False, dims=(8, 8)):
    import json
    material = '/Game/Unreal/Materials/Demo/deferred/Flame_ue5'
    root = tmp_path / 'source'; root.mkdir(); raw = fixture(dims=dims); (root / 'Demo.utx').write_bytes(raw)
    m = dict(deferred=[dict(path='Demo.Flame', reason='procedural FireTexture', width=dims[0], height=dims[1])],
             packages={'Demo': dict(sha256=hashlib.sha256(raw).hexdigest())},
             materials=[dict(path=material, deferred=True, source_texture='Demo.Flame')])
    mp = tmp_path / 'materials.json'; mp.write_text(json.dumps(m))
    buffer = tmp_path / 'chunk.json'; buffer.write_text(json.dumps(dict(material_ids=[0, 1, 0])))
    lighting = dict(material_sha256=hashlib.sha256(mp.read_bytes()).hexdigest(), map_path='/Game/Unreal/Maps/Demo_ue5',
                    chunks=[dict(name='Demo_Effects_ue5', nanite=nanite, materials=[material, '/Game/Other'],
                                 source_file=buffer.name, source_sha256=hashlib.sha256(buffer.read_bytes()).hexdigest())])
    lp = tmp_path / 'lighting.json'; lp.write_text(json.dumps(lighting))
    return mp, lp, root


def test_fire_preparation_preserves_inputs_binds_only_exact_source_slots_and_refuses_overwrite(tmp_path):
    from ue1_converter.fire_prepare import prepare_fire
    mp, lp, root = prepared_fixture(tmp_path)
    before = [p.read_bytes() for p in (mp, lp, root / 'Demo.utx')]
    result = prepare_fire(mp, lp, root, tmp_path / 'ready')
    assert len(result['textures']) == 1 and len(result['bindings']) == 1
    assert result['bindings'][0]['triangles'] == 2 and result['bindings'][0]['slot'] == 0
    assert result['bindings'][0]['material'] == '/Game/Unreal/Materials/Demo/animated/Flame_ue5'
    assert [p.read_bytes() for p in (mp, lp, root / 'Demo.utx')] == before
    with pytest.raises(FileExistsError): prepare_fire(mp, lp, root, tmp_path / 'ready')


def test_fire_preparation_rejects_changed_package_without_output(tmp_path):
    from ue1_converter.fire_prepare import prepare_fire
    mp, lp, root = prepared_fixture(tmp_path)
    (root / 'Demo.utx').write_bytes(fixture(tail=b'!'))
    with pytest.raises(ValueError, match='package checksum'): prepare_fire(mp, lp, root, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_fire_preparation_rejects_nanite_effect_admission(tmp_path):
    from ue1_converter.fire_prepare import prepare_fire
    mp, lp, root = prepared_fixture(tmp_path, nanite=True)
    with pytest.raises(ValueError, match='Nanite'): prepare_fire(mp, lp, root, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_fire_preparation_rejects_non_square_frames_before_asset_admission(tmp_path):
    from ue1_converter.fire_prepare import prepare_fire
    mp, lp, root = prepared_fixture(tmp_path, dims=(8, 16))
    with pytest.raises(ValueError, match='square frames'): prepare_fire(mp, lp, root, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()
