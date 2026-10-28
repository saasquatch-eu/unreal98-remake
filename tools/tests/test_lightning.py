"""Synthetic source lightning selection, periodic timing, spatial falloff and provenance."""
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest

from ue1_converter.lightning_prepare import flash_schedule, prepare_lightning, sky_attenuation, source_lightning, value_at
from ue1_converter.t3d import parse_t3d


def document(actors):
    text = 'Begin Map\n'
    for name, z, extra in actors:
        text += f'Begin Actor Class=DistanceLightning Name={name}\nLocation=(X=1,Y=2,Z={z})\n{extra}End Actor\n'
    return parse_t3d(text + 'End Map\n')


def test_active_world_and_selected_sky_only_with_duplicate_identity_preserved():
    doc = document([('Same', 1, ''), ('Same', 12, ''), ('Low', 11, ''), ('Outside', 0, '')])
    lights, excluded = source_lightning(doc, lambda p: int(p[2]), 12)
    assert [e['name'] for e in lights] == ['Same_Source0_ue5', 'Same_Source1_ue5']
    assert [e['source_actor_index'] for e in lights] == [0, 1]
    assert lights[0]['location'] == [1, 2, 1] and lights[0]['cast_shadows'] and not lights[0]['sky']
    assert lights[1]['collection_parameter'] == 'Flash1' and not lights[1]['cast_shadows']
    assert [e['source_actor_index'] for e in excluded] == [2, 3]
    assert [e['source_name'] for e in excluded] == ['Low', 'Outside']


def test_exported_steady_type_is_recorded_but_preview_starts_dark():
    lights, _ = source_lightning(document([('Flash', 1, 'LightType=LT_Steady\nLightRadius=200\n')]), lambda p: 1, 12)
    item = lights[0]
    assert item['source_values']['LightType'] == 'LT_Steady' and 'LightType' not in item['defaulted_properties']
    assert item['radius'] == 5001 and value_at(item['schedule']['keys'], 0) == 0
    assert item['schedule']['bursts'][0][0] >= 5000
    assert item['color_linear'] == (1, 1, 1) and item['peak_lumens'] > 0


@pytest.mark.parametrize('extra', ['LightRadius=0\n', 'LightBrightness=256\n', 'LightHue=-1\n', 'LightType=LT_Pulse\n'])
def test_unsupported_light_values_are_rejected(extra):
    with pytest.raises(ValueError): source_lightning(document([('Flash', 1, extra)]), lambda p: 1, 12)


def test_preview_preserves_timer_ranges_off_intervals_and_periodic_seam_across_seeds():
    for seed in range(100):
        schedule = flash_schedule(seed); bursts = schedule['bursts']; keys = schedule['keys']
        assert 5000 <= bursts[0][0] < 15000
        assert all(400 <= end - start < 450 for start, end in bursts)
        assert all(9000 <= right[0] - left[1] < 29000 for left, right in zip(bursts, bursts[1:]))
        assert 9000 <= 128000 - bursts[-1][1] + bursts[0][0] < 29000
        assert all(a[0] < b[0] for a, b in zip(keys, keys[1:]))
        assert keys[0] == [0, 0] and keys[-1] == [128000, 0]
        for start, end in bursts:
            assert value_at(keys, start - 1) == 0 and value_at(keys, start) == 1 and value_at(keys, end) == 0
        assert all(0 <= value <= 1 and (value == 0 or any(start <= time < end for start, end in bursts)) for time, value in keys)
        assert schedule == flash_schedule(seed)
    assert flash_schedule(1) != flash_schedule(2)


@pytest.mark.parametrize('duration', [0, 59000, 600001, 128000.5])
def test_invalid_duration_is_rejected(duration):
    with pytest.raises(ValueError): flash_schedule(1, duration)


def test_sky_flash_falloff_uses_source_positions_and_vanishes_outside_radius():
    assert sky_attenuation([1, 2, 3], [1, 2, 3], 20) == 1
    assert sky_attenuation([11, 2, 3], [1, 2, 3], 20) == 0.25
    assert sky_attenuation([21, 2, 3], [1, 2, 3], 20) == 0
    assert sky_attenuation([100, 2, 3], [1, 2, 3], 20) == 0
    for radius in [0, -1, float('nan')]:
        with pytest.raises(ValueError): sky_attenuation([0]*3, [0]*3, radius)


def inputs(tmp_path, monkeypatch):
    import ue1_converter.lightning_prepare as module
    fixture = runpy.run_path(str(Path(__file__).with_name('test_textures.py')))['fixture']
    source = tmp_path / 'source.t3d'; source.write_text(document([('WorldFlash', 1, ''), ('SkyFlash', 12, ''), ('Other', 11, '')]).source_text)
    package = tmp_path / 'map.unr'; package.write_bytes(fixture(flags=0)); geometry = tmp_path / 'geometry.json'; geometry.write_text('{}')
    sky = dict(selected_sky=dict(origin=[10, 20, 30], zone=12), projection_scale=128)
    for key, path in [('source', source), ('package', package), ('geometry', geometry)]:
        sky[key + '_file'] = str(path); sky[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    sky_path = tmp_path / 'sky.json'; sky_path.write_text(json.dumps(sky))
    moons_path = tmp_path / 'moons.json'; moons_path.write_text(json.dumps(dict(sky_plan=str(sky_path), sky_sha256=hashlib.sha256(sky_path.read_bytes()).hexdigest())))
    monkeypatch.setattr(module, 'read_world_bsp', lambda p: SimpleNamespace(point_zone=lambda pos: int(pos[2])))
    return moons_path, source, package, geometry


def test_complete_preparation_keeps_provenance_names_and_is_reproducible(tmp_path, monkeypatch):
    args = inputs(tmp_path, monkeypatch); before = [p.read_bytes() for p in args]
    plan = prepare_lightning(args[0], tmp_path / 'ready'); second = prepare_lightning(args[0], tmp_path / 'repeat')
    assert plan == second and [e['name'] for e in plan['lights']] == ['WorldFlash_ue5', 'SkyFlash_ue5']
    assert plan['excluded'][0]['source_name'] == 'Other' and plan['sky_origin'] == [10, 20, 30]
    assert [p.read_bytes() for p in args] == before
    assert json.loads((tmp_path / 'ready/Unreal.lightning.json').read_text())['lights'][0]['schedule'] == plan['lights'][0]['schedule']
    with pytest.raises(FileExistsError): prepare_lightning(args[0], tmp_path / 'ready')


@pytest.mark.parametrize('changed', [0, 1, 2, 3])
def test_changed_prior_recipe_map_export_or_geometry_blocks_writes(tmp_path, monkeypatch, changed):
    args = inputs(tmp_path, monkeypatch); args[changed].write_bytes(args[changed].read_bytes() + b' ')
    if changed == 0:
        # Moon recipes themselves are the explicit input; change their checked sky reference.
        value = json.loads(args[0].read_text()); value['sky_sha256'] = 'changed'; args[0].write_text(json.dumps(value))
    with pytest.raises(ValueError, match='provenance'): prepare_lightning(args[0], tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()
