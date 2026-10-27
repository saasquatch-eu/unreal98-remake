import json
import math

import pytest

from ue1_converter.ue5_prepare import prepare_import,validate_buffers


def example():
    return dict(schema_version=1,source=dict(name='Example.t3d',sha256='source'),package=dict(sha256='package'),
                points=[[1,2,3],[3,2,3],[3,4,3],[1,4,3],[10,20,30],[11,20,30],[10,21,30]],
                surfaces=[dict(normal=[0,0,1])],
                faces=[dict(role='world',object='Example_ue5',surface=0,triangles=[[0,1,2],[0,2,3]]),
                       dict(role='mover',object='MovingDoor_ue5',surface=0,triangles=[[4,5,6]]),
                       dict(role='sky_mask',object='Example_ue5',surface=0,triangles=[[0,1,2]])],
                movers=[dict(name='MovingDoor',properties=[dict(name='Location',value='(X=10,Y=20,Z=30)',line=1)])],
                zone_samples=[dict(actor_class='InterpolationPoint',position=[5,6,7],rotation='(Pitch=16384,Yaw=3,Roll=-1)')])


def test_direct_preparation_preserves_axes_and_separate_mover_pivots(tmp_path):
    source=tmp_path/'Example.geometry.json';source.write_text(json.dumps(example()))
    plan=prepare_import(source,tmp_path/'ready')
    assert [m['name'] for m in plan['meshes']]==['Example_ue5','MovingDoor_ue5']
    assert [m['triangle_count'] for m in plan['meshes']]==[2,1]
    world=json.loads((tmp_path/'ready/Example_ue5.mesh.json').read_text())
    assert world['vertices'][0]==[1,2,3]
    assert world['vertices'][1]==[3,2,3]  # No FBX axis reflection is applied.
    assert world['triangles']==[[0,2,1],[3,5,4]]
    # UE5 reverse-cross normal agrees with the preserved outward surface normal.
    a,b,c=(world['vertices'][i] for i in world['triangles'][0])
    assert (c[0]-a[0])*(b[1]-a[1])-(c[1]-a[1])*(b[0]-a[0])>0
    assert len(world['uv0'])==len(world['vertices'])==len(world['normals'])==6
    validate_buffers(world)
    mover=json.loads((tmp_path/'ready/MovingDoor_ue5.mesh.json').read_text())
    assert mover['vertices']==[[0,0,0],[1,0,0],[0,1,0]]
    assert plan['meshes'][1]['actor_location']==[10,20,30]
    assert plan['meshes'][0]['asset_path']=='/Game/Unreal/Meshes/Example_ue5'
    assert plan['camera']['rotation']['pitch']==90
    assert plan['camera']['rotation']['yaw']==0
    assert plan['camera']['rotation']['roll']==pytest.approx(360-360/16384)
    assert 'diagnostic' in plan['uv0_mode']
    assert source.read_text()==json.dumps(example())


def test_scale_is_explicit_and_world_placement_round_trips(tmp_path):
    source=tmp_path/'Example.geometry.json';source.write_text(json.dumps(example()))
    plan=prepare_import(source,tmp_path/'ready',centimeters_per_source_unit=2)
    assert plan['camera']['location']==[10,12,14]
    mesh=plan['meshes'][1]
    data=json.loads((tmp_path/'ready'/mesh['source_file']).read_text())
    assert [v+p for v,p in zip(data['vertices'][1],mesh['actor_location'])]==[22,40,60]
    assert 'physical gameplay scale unresolved' in plan['scale_status']


@pytest.mark.parametrize('scale',[0,-1,math.inf,math.nan])
def test_invalid_scale_fails_before_creating_output(tmp_path,scale):
    source=tmp_path/'Example.geometry.json';source.write_text(json.dumps(example()))
    with pytest.raises(ValueError):prepare_import(source,tmp_path/'ready',centimeters_per_source_unit=scale)
    assert not (tmp_path/'ready').exists()


@pytest.mark.parametrize('change',['missing_uv','short_uv','degenerate_uv','nonfinite','indices','zero_normal'])
def test_unsafe_buffers_fail_before_native_engine_call(change):
    data=dict(vertices=[[0,0,0],[1,0,0],[0,1,0]],normals=[[0,0,1]]*3,
              uv0=[[0,0],[1,0],[0,1]],triangles=[[0,1,2]])
    if change=='missing_uv':del data['uv0']
    elif change=='short_uv':data['uv0']=[]
    elif change=='degenerate_uv':data['uv0']=[[0,0]]*3
    elif change=='nonfinite':data['vertices'][0][0]=math.nan
    elif change=='indices':data['triangles']=[[0,1,9]]
    elif change=='zero_normal':data['normals']=[[0,0,0]]*3
    with pytest.raises(ValueError):validate_buffers(data)


def test_existing_destination_is_never_overwritten(tmp_path):
    source=tmp_path/'Example.geometry.json';source.write_text(json.dumps(example()))
    prepare_import(source,tmp_path/'ready')
    before={p:p.read_bytes() for p in (tmp_path/'ready').iterdir()}
    with pytest.raises(FileExistsError):prepare_import(source,tmp_path/'ready')
    assert all(p.read_bytes()==data for p,data in before.items())
