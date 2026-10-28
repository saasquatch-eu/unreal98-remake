"""Synthetic source-sky geometry, selection, admission and provenance checks."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import runpy

import pytest

from ue1_converter.sky_prepare import prepare_sky, select_sky, sky_buffers
from ue1_converter.t3d import parse_t3d
fixture = runpy.run_path(str(Path(__file__).with_name('test_textures.py')))['fixture']


def geometry():
    return dict(schema_version=1, points=[[10, 20, 30], [14, 20, 30], [10, 28, 30]],
                surfaces=[dict(texture='Demo.Tile', flags=0, normal=[0, 0, 1])],
                faces=[dict(role='sky_geometry', zones=[0, 5], surface=0, points=[0, 1, 2],
                            triangles=[[0, 1, 2]], uv_texels=[[-2, 4], [6, 4], [-2, -4]])],
                zones=[dict(index=5, actor='Demo.SkyZoneInfo1')])


def document(extra=''):
    return parse_t3d('Begin Map\nBegin Actor Class=SkyZoneInfo Name=SkyZoneInfo1\nbHighDetail=True\nLocation=(X=10,Y=20,Z=25)\nTexUPanSpeed=0.3\nTexVPanSpeed=0.4\nEnd Actor\n'+extra+'End Map\n')


def test_sky_preserves_directions_uvs_winding_and_input():
    g = geometry(); before = deepcopy(g)
    result = sky_buffers(g, 5, [10, 20, 25], {'Demo.Tile': (2, 4)}, scale=2)[0]
    assert result['buffers'] == dict(vertices=[[0, 0, 10], [8, 0, 10], [0, 16, 10]], normals=[[0, 0, 1]] * 3,
                                    uv0=[[-1, 1], [3, 1], [-1, -1]], triangles=[[0, 2, 1]])
    assert result['source_faces'] == [0] and g == before
    assert result == sky_buffers(g, 5, [10, 20, 25], {'Demo.Tile': (2, 4)}, scale=2)[0]


def test_only_selected_sky_geometry_is_admitted():
    g = geometry(); other = deepcopy(g['faces'][0]); other['zones'] = [0, 6]; g['faces'].append(other)
    world = deepcopy(g['faces'][0]); world['role'] = 'world'; g['faces'].append(world)
    result = sky_buffers(g, 5, [0, 0, 0], {'Demo.Tile': (2, 2)})
    assert len(result) == 1 and len(result[0]['buffers']['triangles']) == 1
    with pytest.raises(ValueError, match='no geometry'): sky_buffers(g, 7, [0, 0, 0], {'Demo.Tile': (2, 2)})


@pytest.mark.parametrize('scale', [0, -1, math.inf, math.nan])
def test_invalid_projection_scale_rejected(scale):
    with pytest.raises(ValueError): sky_buffers(geometry(), 5, [0, 0, 0], {'Demo.Tile': (2, 2)}, scale=scale)


def test_translucent_pan_flags_form_separate_group():
    g = geometry(); g['surfaces'].append(dict(g['surfaces'][0], flags=0x870c)); g['faces'].append(dict(g['faces'][0], surface=1))
    groups = sky_buffers(g, 5, [0, 0, 0], {'Demo.Tile': (2, 2)})
    assert [e['flags'] for e in groups] == [0, 0x870c]
    assert sum(len(e['buffers']['triangles']) for e in groups) == 2
    g['surfaces'][1]['flags'] = 0x40
    with pytest.raises(ValueError, match='flags'): sky_buffers(g, 5, [0, 0, 0], {'Demo.Tile': (2, 2)})


def test_selection_uses_explicit_high_detail_and_compiled_zone():
    selected = select_sky(geometry(), document())
    assert selected['zone'] == 5 and selected['origin'] == [10, 20, 25] and selected['source_actor_index'] == 0
    with pytest.raises(ValueError, match='high-detail'): select_sky(geometry(), parse_t3d(document().source_text.replace('bHighDetail=True', 'bHighDetail=False')))
    g = geometry(); g['zones'].append(dict(index=6, actor='Demo.SkyZoneInfo1'))
    with pytest.raises(ValueError, match='ambiguous'): select_sky(g, document())


def inputs(tmp_path):
    source = tmp_path / 'Demo.t3d'; source.write_text(document('Begin Actor Class=DistanceLightning Name=Same\nEnd Actor\nBegin Actor Class=DistanceLightning Name=Same\nEnd Actor\n').source_text)
    package = tmp_path / 'Demo.unr'; package.write_bytes(b'checked synthetic map')
    g = geometry(); g['source'] = dict(sha256=hashlib.sha256(source.read_bytes()).hexdigest()); g['package'] = dict(sha256=hashlib.sha256(package.read_bytes()).hexdigest())
    path = tmp_path / 'Demo.geometry.json'; path.write_text(json.dumps(g))
    textures = tmp_path / 'textures'; textures.mkdir(); (textures / 'Demo.utx').write_bytes(fixture())
    return path, source, package, textures


def test_preparation_hashes_original_images_preserves_names_and_duplicate_actor_identity(tmp_path):
    args = inputs(tmp_path); before = [p.read_bytes() for p in args[:3]]
    plan = prepare_sky(*args, tmp_path / 'ready')
    assert plan['textures'][0]['asset_path'] == '/Game/Unreal/Textures/Demo/Tile_ue5'
    mesh = plan['meshes'][0]; assert mesh['name'] == 'SkyZoneInfo1_Surface00_ue5'
    assert mesh['triangle_count'] == 1 and mesh['pan_uv_per_second'] == [0, 0]
    assert [a['source_actor_index'] for a in plan['deferred_actors']] == [1, 2]
    raw = (tmp_path / 'ready' / plan['textures'][0]['source_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == plan['textures'][0]['source_sha256']
    assert raw[18 + 3] == 255  # P8 palette zero stays opaque for the black starfield.
    assert [p.read_bytes() for p in args[:3]] == before
    with pytest.raises(FileExistsError): prepare_sky(*args, tmp_path / 'ready')


@pytest.mark.parametrize('changed', [1, 2])
def test_mismatching_map_or_export_prevents_writes(tmp_path, changed):
    args = inputs(tmp_path); args[changed].write_bytes(args[changed].read_bytes() + b' ')
    with pytest.raises(ValueError, match='provenance'): prepare_sky(*args, tmp_path / 'ready')
    assert not (tmp_path / 'ready').exists()


def test_cloud_pan_uses_only_flagged_axes_and_records_authored_rate(tmp_path):
    args = inputs(tmp_path); g = json.loads(args[0].read_text()); g['surfaces'][0]['flags'] = 0x820c
    args[0].write_text(json.dumps(g)); plan = prepare_sky(*args, tmp_path / 'ready')
    assert plan['meshes'][0]['pan_uv_per_second'] == [0.3 * 32 / 2, 0]
    assert plan['meshes'][0]['mode'] == 'sky_cloud'
    assert any('native scrolling timing' in s for s in plan['limitations'])


def test_camera_centering_preserves_view_direction_under_translation():
    g = geometry(); origin = [10, 20, 25]; scale = 128
    data = sky_buffers(g, 5, origin, {'Demo.Tile': (2, 2)}, scale=scale)[0]['buffers']
    for camera in ([0, 0, 0], [234, -987, 65]):
        for source, local in zip(g['points'], data['vertices']):
            rendered = [p + c for p, c in zip(local, camera)]
            assert [(p - c) / scale for p, c in zip(rendered, camera)] == [p - o for p, o in zip(source, origin)]
