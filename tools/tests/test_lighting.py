"""Synthetic light plans and lossless partitioning invariants."""
from collections import Counter
from copy import deepcopy
import math

import pytest

from ue1_converter.lighting_prepare import partition_buffers,source_lights
from ue1_converter.t3d import parse_t3d


def mesh():
    return dict(vertices=[[-4,0,0],[-2,0,0],[-4,2,0],[2,0,0],[4,0,0],[2,2,0]],
                normals=[[0,0,1]]*6,uv0=[[-2,0],[0,0],[-2,1],[0,0],[1,0],[0,1]],
                triangles=[[0,2,1],[3,5,4]],material_ids=[7,3])


def triangles(data):
    return Counter((m,tuple(tuple(data[k][v]) for v in tri for k in ('vertices','normals','uv0'))) for tri,m in zip(data['triangles'],data['material_ids']))


def test_partition_preserves_every_corner_winding_uv_and_material_once():
    data=mesh();before=deepcopy(data);parts=partition_buffers(data,4)
    assert len(parts)==2 and parts[0]['cell'][0]==-1 and parts[1]['cell'][0]==0
    actual=Counter()
    for part in parts:actual.update(triangles(part['buffers']))
    assert actual==triangles(data) and data==before
    assert sorted(i for part in parts for i in part['source_triangle_indices'])==[0,1]
    assert parts==partition_buffers(data,4)


@pytest.mark.parametrize('size',[0,-1,math.inf,math.nan])
def test_invalid_partition_size_is_rejected(size):
    with pytest.raises(ValueError):partition_buffers(mesh(),size)


def test_partition_requires_one_material_id_per_triangle():
    data=mesh();data['material_ids']=[]
    with pytest.raises(ValueError):partition_buffers(data)


def document(extra='',name='Torch'):
    return parse_t3d('Begin Map\nBegin Actor Class=Light Name='+name+'\nLocation=(X=10,Y=-2,Z=3)\nLightBrightness=128\nLightHue=21\nLightSaturation=100\nLightRadius=20\n'+extra+'End Actor\nEnd Map\n')


def test_source_light_placement_color_calibration_and_actor_identity():
    lights,excluded=source_lights(document(),lambda p:1)
    assert not excluded
    item=lights[0]
    assert item['location']==[10,-2,3] and item['name']=='Torch_ue5'
    assert item['color_linear'][0]>item['color_linear'][1]>item['color_linear'][2]
    assert item['attenuation_radius']==501 and item['intensity_lumens']>0
    assert item['defaulted_properties']==['LightType']
    assert item['source_actor_index']==0 and item['source_line']==2


@pytest.mark.parametrize('zone,extra',[(11,''),(12,''),(0,''),(1,'LightType=LT_None\n'),(1,'LightType=LT_Pulse\n')])
def test_sky_and_nonsteady_lights_are_reported_instead_of_imported(zone,extra):
    lights,excluded=source_lights(document(extra),lambda p:zone)
    assert not lights and len(excluded)==1


def test_missing_defaults_are_recorded_and_not_mistaken_for_exported_values():
    d=parse_t3d('Begin Map\nBegin Actor Class=Light Name=Fill\nLocation=(X=0)\nEnd Actor\nEnd Map\n')
    lights,_=source_lights(d,lambda p:1)
    assert set(lights[0]['defaulted_properties'])=={'LightType','LightBrightness','LightHue','LightSaturation','LightRadius'}
    assert lights[0]['source_properties']['LightBrightness']=='64'
    assert lights[0]['color_linear']==(1,1,1)


def test_duplicate_light_names_keep_distinct_source_indices():
    text='Begin Map\n'+''.join('Begin Actor Class=Light Name=Same\nLocation=(X='+str(x)+')\nEnd Actor\n' for x in (1,2))+'End Map\n'
    lights,_=source_lights(parse_t3d(text),lambda p:1)
    assert [i['name'] for i in lights]==['Same_Source0_ue5','Same_Source1_ue5']


def test_invalid_source_light_bytes_are_rejected():
    with pytest.raises(ValueError):source_lights(parse_t3d(document().source_text.replace('LightBrightness=128','LightBrightness=256')),lambda p:1)


def test_transparent_effects_are_separated_without_losing_attributes():
    data=mesh()
    for point in data['vertices']:point[0]+=5
    parts=partition_buffers(data,10,raster_material_ids={3})
    assert len(parts)==2 and parts[0]['cell']==parts[1]['cell']
    assert {p['nanite'] for p in parts}=={True,False}
    assert next(p for p in parts if not p['nanite'])['buffers']['material_ids']==[3]
    actual=Counter()
    for part in parts:actual.update(triangles(part['buffers']))
    assert actual==triangles(data)


def test_only_explicit_corona_lights_receive_point_shadow_budget():
    lights,_=source_lights(document('bCorona=True\n'),lambda p:1)
    assert lights[0]['cast_shadows'] is True
    lights,_=source_lights(document(),lambda p:1)
    assert lights[0]['cast_shadows'] is False
