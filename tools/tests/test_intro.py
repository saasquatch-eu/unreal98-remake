"""Authored audio/package and camera fixtures, without original game data."""
import hashlib
import io
import math
import struct
import wave

import pytest

from ue1_converter.audio61 import decode_audio, wave_info
from ue1_converter.intro_prepare import bspline, linked_path, sample_camera, segment_alpha, segment_seconds, source_camera
from ue1_converter.package61 import Package61, PackageError
from ue1_converter.t3d import parse_t3d


def index(value):
    first = 128 if value < 0 else 0; value = abs(value); output = bytearray([first | (64 if value >= 64 else 0) | (value & 63)]); value >>= 6
    while value: output.append((128 if value >= 128 else 0) | (value & 127)); value >>= 7
    return bytes(output)


def package_fixture(objects, names, classes, *, flags=0):
    names = list(dict.fromkeys(['None', 'Core', 'Class'] + classes + names + [o[0] for o in objects])); name = lambda s: index(names.index(s))
    table = b''.join(n.encode() + b'\0' + bytes(4) for n in names); imports = b''.join(name('Core') + name('Class') + bytes(4) + name(c) for c in classes)
    bodies = [make(name) for obj, cls, make in objects]; offset = 60 + len(table) + len(imports); exports = []
    for (obj, cls, make), body in zip(objects, bodies):
        exports.append(index(-classes.index(cls) - 1) + index(0) + bytes(4) + name(obj) + struct.pack('<I', flags) + index(len(body)) + index(offset)); offset += len(body)
    header = struct.pack('<IHHIiiiiii', 0x9e2a83c1, 61, 0, 0, len(names), 60, len(objects), offset, len(classes), 60 + len(table))
    return header.ljust(60, b'\0') + table + imports + b''.join(bodies) + b''.join(exports)


def pcm_wave():
    output = io.BytesIO()
    with wave.open(output, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(struct.pack('<8h', 0, 1000, -3000, 700, 22, -500, 0, 900))
    return output.getvalue()


def audio_fixture(*, kind='Sound', file_type='WAV', data=None, tail=b'', flags=0):
    data = pcm_wave() if data is None else data
    return package_fixture([('Tone', kind, lambda n: n('None') + n(file_type) + index(len(data)) + data + tail)], [file_type], [kind], flags=flags)


def test_source_pcm_bytes_metadata_and_package_immutability():
    raw = audio_fixture(); before = hashlib.sha256(raw).digest(); data, info = decode_audio(Package61(raw), 'Demo.Tone', 'Demo', 'Sound')
    assert data == pcm_wave() and info['frames'] == 8 and info['sample_rate'] == 8000 and info['sample_width'] == 2
    assert hashlib.sha256(raw).digest() == before
    assert info['payload_sha256'] == hashlib.sha256(data).hexdigest()


def test_music_payload_is_preserved_for_the_explicit_decoder():
    data = b'IMPM' + bytes(188); raw = audio_fixture(kind='Music', file_type='IT', data=data)
    result, info = decode_audio(Package61(raw), 'Demo.Tone', 'Demo', 'Music')
    assert result == data and info['file_type'] == 'it'


@pytest.mark.parametrize('change', [dict(tail=b'!'), dict(file_type='OGG'), dict(data=b'RIFF' + bytes(40)), dict(flags=0x02000000)])
def test_unsupported_or_trailing_audio_is_rejected(change):
    with pytest.raises(PackageError): decode_audio(Package61(audio_fixture(**change)), 'Demo.Tone', 'Demo', 'Sound')


@pytest.mark.parametrize('data', [b'', b'RIFF', pcm_wave()[:-1], pcm_wave() + b'!'])
def test_incomplete_or_overlong_wave_payloads_are_rejected(data):
    with pytest.raises(PackageError): wave_info(data)


def test_wave_sample_loops_are_read_and_bounded():
    data = pcm_wave(); loop = struct.pack('<9I', 0, 0, 0, 60, 0, 0, 0, 1, 0) + struct.pack('<6I', 0, 0, 1, 6, 0, 0)
    data += b'smpl' + struct.pack('<I', len(loop)) + loop; data = data[:4] + struct.pack('<I', len(data) - 8) + data[8:]
    assert wave_info(data)['sample_loops'] == [dict(start_frame=1, end_frame_inclusive=6, play_count=0)]
    bad = data[:-12] + struct.pack('<I', 999) + data[-8:]
    with pytest.raises(PackageError): wave_info(bad)


def points():
    return [dict(position=i, rate=0.5, location=[10 * math.cos(i * math.pi / 2), 10 * math.sin(i * math.pi / 2), 2], rotation_degrees=[0, i * 90, 0]) for i in range(4)]


def test_linking_preserves_later_duplicate_position_side_effects():
    p = points(); p.append(dict(p[1], location=[999, 0, 0])); links = linked_path(p)
    assert links['order'] == [0, 4, 2, 3] and links['excluded'] == [1]
    assert links['previous'][2] == 4 and links['following'][0] == 4
    p = points(); p.insert(2, dict(p[1], location=[999, 0, 0])); links = linked_path(p)
    assert links['order'] == [0, 2, 3, 4] and links['previous'][3] == 1


def test_rate_integration_and_inverse_preserve_duration_and_progress():
    for a, b in [(0.5, 0.5), (0.3, 0.8), (0.8, 0.3)]:
        duration = segment_seconds(a, b)
        assert segment_alpha(a, b, 0) == 0 and segment_alpha(a, b, duration) == pytest.approx(1)
        assert 1 / max(a, b) <= duration <= 1 / min(a, b)
        values = [segment_alpha(a, b, duration * k / 100) for k in range(101)]
        assert all(x < y for x, y in zip(values, values[1:]))
    with pytest.raises(ValueError): segment_seconds(0, 1)
    with pytest.raises(ValueError): segment_alpha(1, 1, 2)


def test_bspline_is_smooth_and_approximates_instead_of_interpolating_controls():
    control = [[0, 0, 0], [1, 3, 2], [4, 2, 0], [8, 1, -2], [12, 7, 4]]
    assert bspline(control[:4], 0) != control[1]
    assert bspline(control[:4], 1) == pytest.approx(bspline(control[1:], 0))
    derivative_left = [(a-b)/1e-5 for a,b in zip(bspline(control[:4],1), bspline(control[:4],1-1e-5))]
    derivative_right = [(a-b)/1e-5 for a,b in zip(bspline(control[1:],1e-5), bspline(control[1:],0))]
    assert derivative_left == pytest.approx(derivative_right, abs=1e-4)


def test_sampled_camera_closes_spatially_and_avoids_euler_wrap_jumps():
    p = points(); camera = sample_camera(p, linked_path(p))
    assert camera['duration_seconds'] == 8 and camera['playback_frames'] == 480
    assert camera['samples'][0]['location'] == pytest.approx(camera['samples'][-1]['location'])
    assert all(abs(a['rotation'][1] - b['rotation'][1]) < 5 for a, b in zip(camera['samples'], camera['samples'][1:]))
    assert (camera['samples'][-1]['rotation'][1] - camera['samples'][0]['rotation'][1]) % 360 == pytest.approx(0, abs=1e-8)


def camera_fixture(*, mismatch=False, bad_order=False, nonfinite=False):
    names = ['Position', 'Location', 'Vector', 'Rotation', 'Rotator', 'RateModifier']
    objects = [('MyLevel', 'Level', lambda n: n('None') + struct.pack('<ii', 4, 4) + b''.join(index(i) for i in ([3,2,4,5] if bad_order else [2,3,4,5])))]
    source = 'Begin Map\n'
    for i in range(4):
        def body(n, i=i):
            data = b'' if i == 0 else n('Position') + bytes([0x22]) + struct.pack('<i', i + (1 if mismatch and i == 2 else 0))
            data += n('Location') + bytes([0x3a]) + n('Vector') + struct.pack('<3f', float('nan') if nonfinite else i * 10, 2, 3)
            data += n('RateModifier') + bytes([0x24]) + struct.pack('<f', 0.5)
            return data + n('None')
        objects.append(('Point' + str(i), 'InterpolationPoint', body))
        source += f'Begin Actor Class=InterpolationPoint Name=Point{i}\nTag="Path"\nLocation=(X={i*10},Y=2,Z=3)\nRateModifier=0.5\n' + (f'Position={i}\n' if i else '') + 'End Actor\n'
    return Package61(package_fixture(objects, names, ['Level', 'InterpolationPoint'])), parse_t3d(source + 'End Map\n')


def test_binary_level_actor_order_and_camera_values_are_checked():
    p, d = camera_fixture(); camera = source_camera(p, d)
    assert [c['position'] for c in camera] == [0, 1, 2, 3] and camera[2]['location'] == [20, 2, 3]
    assert camera[0]['rotation_units'] == [0, 0, 0]


@pytest.mark.parametrize('change', [dict(mismatch=True), dict(bad_order=True), dict(nonfinite=True)])
def test_camera_binary_export_conflicts_are_rejected(change):
    p, d = camera_fixture(**change)
    with pytest.raises(PackageError): source_camera(p, d)


def test_complete_intro_preparation_reproduces_and_keeps_sources_unchanged(tmp_path, monkeypatch):
    import json
    import ue1_converter.intro_prepare as module
    package, doc = camera_fixture()
    source = tmp_path / 'source.t3d'
    text = doc.source_text.replace('End Map', "Begin Actor Class=LevelInfo Name=Info\nSong=Music'Flyby.Flyby'\nEnd Actor\nBegin Actor Class=AmbientSound Name=Wind\nLocation=(X=1,Y=2,Z=3)\nAmbientSound=Sound'Demo.Tone'\nEnd Actor\nEnd Map")
    source.write_text(text); map_path = tmp_path / 'map.unr'; map_path.write_bytes(package.data); geometry = tmp_path / 'geometry.json'; geometry.write_text('{}')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    sky = tmp_path / 'sky.json'; sky.write_text(json.dumps(dict(geometry_file=str(geometry), geometry_sha256=sha(geometry))))
    moons = tmp_path / 'moons.json'; moons.write_text(json.dumps(dict(sky_plan=str(sky), sky_sha256=sha(sky))))
    lightning = tmp_path / 'lightning.json'; lightning.write_text(json.dumps(dict(moons_plan=str(moons), moons_sha256=sha(moons), source_file=str(source), source_sha256=sha(source), package_file=str(map_path), package_sha256=sha(map_path))))
    installation = tmp_path / 'install'; (installation / 'Music').mkdir(parents=True); (installation / 'Sounds').mkdir()
    music = package_fixture([('FlyBy', 'Music', lambda n: n('None') + n('IT') + index(192) + b'IMPM' + bytes(188))], ['IT'], ['Music'])
    (installation / 'Music/Flyby.umx').write_bytes(music); (installation / 'Sounds/Demo.uax').write_bytes(audio_fixture())
    from types import SimpleNamespace
    monkeypatch.setattr(module, 'read_world_bsp', lambda p: SimpleNamespace(point_zone=lambda pos: 1))
    monkeypatch.setattr(module, 'render_it', lambda data, lib: (pcm_wave(), wave_info(pcm_wave())))
    paths = [source, map_path, geometry, installation / 'Music/Flyby.umx', installation / 'Sounds/Demo.uax']; before = [p.read_bytes() for p in paths]
    first = module.prepare_intro(lightning, installation, tmp_path / 'explicit-library', tmp_path / 'ready')
    second = module.prepare_intro(lightning, installation, tmp_path / 'explicit-library', tmp_path / 'repeat')
    assert first == second and [p.read_bytes() for p in paths] == before
    assert [e['path'] for e in first['audio']] == ['Demo.Tone', 'Flyby.FlyBy']
    assert first['emitters'][0]['location'] == [1, 2, 3] and len(first['links']['order']) == 4
    assert first['horizontal_fov'] > first['base_horizontal_fov']
    with pytest.raises(FileExistsError): module.prepare_intro(lightning, installation, tmp_path / 'explicit-library', tmp_path / 'ready')
    geometry.write_text('changed')
    with pytest.raises(ValueError, match='provenance'): module.prepare_intro(lightning, installation, tmp_path / 'explicit-library', tmp_path / 'blocked')
    assert not (tmp_path / 'blocked').exists()


def test_pcm_comparison_allows_only_single_lsb_import_rounding():
    from ue1_converter.audio61 import compare_pcm
    source = pcm_wave(); values = list(struct.unpack('<8h', source[-16:])); values[2] += 1
    rounded = source[:-16] + struct.pack('<8h', *values)
    assert compare_pcm(source, rounded)['max_signed_16bit_sample_error'] == 1
    assert compare_pcm(source, source)['exact']
    values[2] += 1
    with pytest.raises(PackageError): compare_pcm(source, source[:-16] + struct.pack('<8h', *values))


def test_eight_bit_source_readback_admits_two_rounding_steps_only():
    from ue1_converter.audio61 import compare_pcm
    output = io.BytesIO()
    with wave.open(output, 'wb') as w: w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(bytes([0, 128, 255]))
    source = output.getvalue(); output = io.BytesIO()
    with wave.open(output, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(struct.pack('<3h', -32766, 0, 32510))
    assert compare_pcm(source, output.getvalue())['max_signed_16bit_sample_error'] == 2
    with pytest.raises(PackageError): compare_pcm(source, output.getvalue()[:-2] + struct.pack('<h', 32509))
