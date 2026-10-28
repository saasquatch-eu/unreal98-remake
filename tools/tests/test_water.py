"""Synthetic WetTexture packages, source-preserving warps and admission checks."""
from dataclasses import replace
import hashlib
import json
import math
import struct

import pytest

from ue1_converter.package61 import Package61, PackageError
from ue1_converter.texture61 import decode_texture, Texture
from ue1_converter.water61 import decode_wet, water_frame
from ue1_converter.fire61 import atlas_tga
from ue1_converter.water_prepare import prepare_water


def idx(v):
    sign = 128 if v < 0 else 0; v = abs(v); out = bytearray([sign | (64 if v >= 64 else 0) | (v & 63)]); v >>= 6
    while v: out.append((128 if v >= 128 else 0) | (v & 127)); v >>= 7
    return bytes(out)


def fixture(*, kind='WetTexture', count=1, indices=(0,), drop=(12, 64, 3, 5, 0, 0, 8, 30), structure='ADrop', tail=b'', mip_count=1, mip_pixels=0, source_ref=2, palette_ref=3, dims=(8, 8), pixels=bytes(range(64))):
    names = list(dict.fromkeys(['None', 'Core', 'Class', kind, 'Texture', 'Palette', 'Pool', 'Water', 'Colors',
                              'USize', 'VSize', 'UBits', 'VBits', 'WaveAmp', 'SourceTexture', 'NumDrops', 'Drops', 'ADrop', structure]))
    n = lambda k: idx(names.index(k))
    imports = b''.join(n('Core') + n('Class') + bytes(4) + n(k) for k in (kind, 'Texture', 'Palette'))
    tag = lambda name, info, raw: n(name) + bytes([info]) + raw
    dimensions = b''.join(tag(k, 0x22, struct.pack('<i', v)) for k, v in zip(('USize', 'VSize'), dims))
    dimensions += b''.join(tag(k, 1, bytes([v.bit_length() - 1])) for k, v in zip(('UBits', 'VBits'), dims))
    wet = dimensions + tag('WaveAmp', 1, bytes([128])) + tag('SourceTexture', 5, idx(source_ref)) + tag('Palette', 5, idx(palette_ref))
    wet += tag('NumDrops', 0x22, struct.pack('<i', count))
    for i in indices:
        wet += n('Drops') + bytes([0x5a | (128 if i else 0)]) + n(structure) + bytes([len(drop)]) + (bytes([i]) if i else b'') + bytes(drop)
    wet += n('None') + idx(mip_count) + idx(mip_pixels) + struct.pack('<iiBB', *dims, *(v.bit_length() - 1 for v in dims)) + tail
    texture = dimensions + tag('Palette', 5, idx(3)) + n('None') + idx(1) + idx(len(pixels)) + pixels + struct.pack('<iiBB', *dims, *(v.bit_length() - 1 for v in dims))
    palette = n('None') + idx(256) + b''.join(bytes([i, i // 2, 255 - i, 0]) for i in range(256))
    data = b''.join(s.encode() + b'\0' + bytes(4) for s in names)
    io = 60 + len(data); offset = io + len(imports); table = []
    for cls, name, body in [(-1, 'Pool', wet), (-2, 'Water', texture), (-3, 'Colors', palette)]:
        table.append(idx(cls) + idx(0) + bytes(4) + n(name) + bytes(4) + idx(len(body)) + idx(offset)); offset += len(body)
    header = struct.pack('<IHHIiiiiii', 0x9e2a83c1, 61, 0, 1, len(names), 60, 3, offset, 3, io)
    return header.ljust(60, b'\0') + data + imports + wet + texture + palette + b''.join(table)


def decode(raw):
    return decode_wet(Package61(raw, allow_download_flag=True), 'Demo.Pool', 'Demo')


def test_water_native_records_source_reference_and_raw_property_preservation():
    raw = fixture(); before = hashlib.sha256(raw).hexdigest(); wet = decode(raw)
    assert (wet.width, wet.height, wet.wave_amp) == (8, 8, 128)
    assert wet.source_texture == 'Demo.Water' and wet.palette_path == 'Demo.Colors'
    assert wet.drops == ((12, 64, 3, 5, 0, 0, 8, 30),)
    assert wet.metadata['drops'][0]['byte_d'] == 30
    assert next(e for e in wet.metadata['properties'] if e['name'] == 'Drops')['raw_hex'] == bytes(wet.drops[0]).hex()
    assert hashlib.sha256(raw).hexdigest() == before


@pytest.mark.parametrize('change', [dict(kind='Texture'), dict(count=-1), dict(count=129), dict(count=2), dict(indices=(1,)), dict(structure='Vector'), dict(drop=(12, 64, 3)), dict(drop=(20, 64, 3, 5, 0, 0, 8, 30)), dict(drop=(12, 64, 8, 5, 0, 0, 8, 30)), dict(tail=b'!'), dict(mip_count=2), dict(mip_pixels=1), dict(source_ref=0), dict(palette_ref=0), dict(dims=(3, 8))])
def test_malformed_or_unsupported_water_layouts_are_rejected(change):
    with pytest.raises(PackageError): decode(fixture(**change))


def test_water_warp_is_periodic_deterministic_horizontal_and_uses_source_pixels_only():
    raw = fixture(); wet = decode(raw); image = decode_texture(Package61(raw, allow_download_flag=True), 'Demo.Water', 'Demo')
    frames = [water_frame(wet, image, t) for t in (0, 0.125, 0.375)]
    assert frames[1] == water_frame(wet, image, 0.125)
    assert water_frame(wet, image, 0) == water_frame(wet, image, 1)
    assert water_frame(wet, image, -0.125) == water_frame(wet, image, 0.875)
    assert len(set(frames)) > 1
    for frame in frames:
        for y in range(8): assert set(frame[y * 8:(y + 1) * 8]) <= set(image.pixels[y * 8:(y + 1) * 8])
    assert water_frame(wet, image, 0.2, displacement=0) == image.pixels
    assert water_frame(replace(wet, wave_amp=0), image, 0.2) == image.pixels


def test_unimplemented_water_motion_and_mismatched_dimensions_are_rejected():
    raw = fixture(); wet = decode(raw); image = decode_texture(Package61(raw, allow_download_flag=True), 'Demo.Water', 'Demo')
    with pytest.raises(ValueError): water_frame(replace(wet, drops=((16, 64, 3, 5, 0, 0, 0, 0),)), image, 0)
    with pytest.raises(ValueError): water_frame(replace(wet, width=4), image, 0)
    for phase, displacement in [(math.nan, 1), (math.inf, 1), (0, -1), (0, 33), (0, math.inf)]:
        with pytest.raises(ValueError): water_frame(wet, image, phase, displacement=displacement)


def test_water_atlas_wraps_gutters_and_does_not_mask_source_palette_zero():
    palette = b''.join(bytes([i, i, i, 0]) for i in range(256))
    image = Texture(2, 2, bytes([0, 1, 2, 3]), palette, {})
    tga = atlas_tga(image, [image.pixels], columns=1, padding=1, masked=False, wrap_padding=True)
    pixels = tga[18:]
    assert [pixels[i] for i in range(0, len(pixels), 4)] == [3, 2, 3, 2, 1, 0, 1, 0, 3, 2, 3, 2, 1, 0, 1, 0]
    assert set(pixels[3::4]) == {255}


def setup(tmp_path, *, flags=0x104, nanite=False, raw=None):
    root = tmp_path / 'source'; root.mkdir(); raw = fixture() if raw is None else raw; (root / 'Demo.utx').write_bytes(raw)
    original = '/Game/Unreal/Materials/Demo/deferred/Pool_ue5'
    material = dict(deferred=[dict(path='Demo.Pool', reason='procedural WetTexture', width=8, height=8)],
                    packages={'Demo': dict(sha256=hashlib.sha256(raw).hexdigest())}, materials=[dict(path=original, deferred=True, source_texture='Demo.Pool', flags=flags)])
    mp = tmp_path / 'material.json'; mp.write_text(json.dumps(material)); mh = hashlib.sha256(mp.read_bytes()).hexdigest()
    buffer = tmp_path / 'chunk.json'; buffer.write_text(json.dumps(dict(material_ids=[1, 0, 1])))
    lighting = dict(material_sha256=mh, map_path='/Game/Unreal/Maps/Demo_ue5', chunks=[dict(name='Demo_Effects_ue5', nanite=nanite, materials=['/Game/Other', original], source_file=buffer.name, source_sha256=hashlib.sha256(buffer.read_bytes()).hexdigest())])
    lp = tmp_path / 'lighting.json'; lp.write_text(json.dumps(lighting))
    fp = tmp_path / 'fire.json'; fp.write_text(json.dumps(dict(material_sha256=mh, lighting_sha256=hashlib.sha256(lp.read_bytes()).hexdigest())))
    return mp, lp, fp, root


def test_water_preparation_preserves_inputs_exact_bindings_and_reproducible_outputs(tmp_path):
    args = setup(tmp_path); before = [p.read_bytes() for p in args[:3]]
    result = prepare_water(*args, tmp_path / 'ready'); other = prepare_water(*args, tmp_path / 'again')
    assert result == other and len(result['bindings']) == 1
    assert result['bindings'][0]['slot'] == 1 and result['bindings'][0]['triangles'] == 2
    assert result['textures'][0]['source_image_asset'] == '/Game/Unreal/Textures/Demo/Water_ue5'
    assert [p.read_bytes() for p in args[:3]] == before
    for entry in result['textures']:
        for key in ('source_file', 'source_image_file'): assert (tmp_path / 'ready' / entry[key]).read_bytes() == (tmp_path / 'again' / entry[key]).read_bytes()
    with pytest.raises(FileExistsError): prepare_water(*args, tmp_path / 'ready')


@pytest.mark.parametrize('flags,nanite', [(0x100, False), (4, False), (0x400104, False), (0x104, True)])
def test_water_preparation_rejects_incompatible_source_flags_or_nanite(tmp_path, flags, nanite):
    args = setup(tmp_path, flags=flags, nanite=nanite)
    with pytest.raises(ValueError): prepare_water(*args, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_water_preparation_rejects_changed_source_and_static_warp_before_output(tmp_path):
    args = setup(tmp_path); (args[-1] / 'Demo.utx').write_bytes(b'changed')
    with pytest.raises(ValueError, match='checksum'): prepare_water(*args, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_water_preparation_refuses_a_source_image_that_cannot_show_motion(tmp_path):
    args = setup(tmp_path, raw=fixture(pixels=bytes(64)))
    with pytest.raises(ValueError, match='no visible animation'): prepare_water(*args, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()
