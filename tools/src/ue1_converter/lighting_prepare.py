"""Preserve exact material triangles in smaller render meshes and inventory source lights."""
from collections import Counter,defaultdict
import colorsys
import hashlib
import json
import math
from pathlib import Path

from .native_bsp import read_world_bsp
from .package61 import Package61
from .t3d import number,parse_struct,parse_t3d
from .ue5_prepare import validate_buffers


def partition_buffers(data,cell_size=3200.0,*,raster_material_ids=()):
    if not math.isfinite(cell_size) or cell_size<=0:raise ValueError('cell size must be positive and finite')
    validate_buffers(data)
    ids=data['material_ids']
    if len(ids)!=len(data['triangles']):raise ValueError('triangle material count differs')
    groups=defaultdict(list)
    for index,tri in enumerate(data['triangles']):
        center=[sum(data['vertices'][v][axis] for v in tri)/3 for axis in range(3)]
        key=tuple(math.floor(v/cell_size) for v in center)
        groups[key,ids[index] in raster_material_ids].append(index)
    parts=[]
    for (cell,raster),indices in sorted(groups.items()):
        out=dict(vertices=[],normals=[],uv0=[],triangles=[],material_ids=[])
        for index in indices:
            start=len(out['vertices'])
            for vertex in data['triangles'][index]:
                for field in ('vertices','normals','uv0'):out[field].append(data[field][vertex])
            # Input winding is already UE5 winding. Never reverse it a second time.
            out['triangles'].append([start,start+1,start+2]);out['material_ids'].append(ids[index])
        validate_buffers(out)
        parts.append(dict(cell=list(cell),nanite=not raster,source_triangle_indices=indices,buffers=out))
    return parts


def source_lights(document,point_zone):
    names=Counter(a.attribute('Name') for a in document.actors if a.attribute('Class')=='Light')
    result=[];excluded=[]
    defaults=dict(LightType='LT_Steady',LightBrightness='64',LightHue='0',LightSaturation='255',LightRadius='64')
    for index,actor in enumerate(document.actors):
        if actor.attribute('Class')!='Light':continue
        fields={p.name:number(p.value,p.line) for p in parse_struct(actor.property('Location') or '',actor.line)}
        location=[fields.get(k,0.0) for k in 'XYZ'];zone=point_zone(location)
        properties={k:actor.property(k) or value for k,value in defaults.items()}
        name=actor.attribute('Name')
        if zone!=1 or properties['LightType']!='LT_Steady':
            excluded.append(dict(source_actor_index=index,name=name,zone=zone,reason='sky/other zone' if zone!=1 else 'nonsteady light'));continue
        b,h,s,r=(int(properties[k]) for k in ('LightBrightness','LightHue','LightSaturation','LightRadius'))
        if any(not 0<=v<=255 for v in (b,h,s,r)):raise ValueError('source light byte outside range')
        rgb=colorsys.hsv_to_rgb(h/255,1-s/255,1)
        radius=r*25.0+1.0
        # Physical falloff with an explicit artistic calibration, not a UE1 intensity equivalence.
        target_lux=200.0 if h<=64 and s<240 else 50.0
        lumens=(b/255)*4*math.pi*(radius/400.0)**2*target_lux
        label=name+('_Source'+str(index) if names[name]>1 else '')+'_ue5'
        result.append(dict(name=label,source_name=name,source_actor_index=index,source_line=actor.line,zone=zone,
                           location=location,color_linear=rgb,intensity_lumens=lumens,attenuation_radius=radius,cast_shadows=actor.property('bCorona')=='True',
                           source_properties=properties,defaulted_properties=[k for k in defaults if actor.property(k) is None]))
    return result,excluded


def prepare_lighting(material_path,source_path,package_path,destination,*,cell_size=3200.0):
    material_path,source_path,package_path,destination=map(Path,(material_path,source_path,package_path,destination))
    plan=json.loads(material_path.read_text());original=json.loads(Path(plan['original_recipe']).read_text())
    geometry_path=Path(original['geometry_file']);raw=geometry_path.read_bytes();geometry=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=plan['geometry_sha256']:raise ValueError('geometry checksum changed')
    source=source_path.read_bytes();package=package_path.read_bytes()
    if hashlib.sha256(source).hexdigest()!=geometry['source']['sha256'] or hashlib.sha256(package).hexdigest()!=geometry['package']['sha256']:
        raise ValueError('original map/export provenance changed')
    world=next(m for m in plan['meshes'] if m['role']=='world')
    mesh_file=material_path.parent/world['source_file'];mesh_raw=mesh_file.read_bytes()
    if hashlib.sha256(mesh_raw).hexdigest()!=world['source_sha256']:raise ValueError('material buffer checksum changed')
    data=json.loads(mesh_raw)
    raster={i for i,k in enumerate(world['materials']) if plan['materials'][k]['mode'].startswith(('deferred','translucent','modulated'))}
    parts=partition_buffers(data,cell_size,raster_material_ids=raster)
    cells=sorted({tuple(p['cell']) for p in parts})
    records=[];files={}
    for index,part in enumerate(parts):
        cell_index=cells.index(tuple(part['cell']))
        name=('Unreal_Chunk' if part['nanite'] else 'Unreal_Effects')+str(cell_index).zfill(3)+'_ue5';filename=name+'.mesh.json'
        used=sorted(set(part['buffers']['material_ids']))
        remap={old:new for new,old in enumerate(used)}
        part['buffers']['material_ids']=[remap[i] for i in part['buffers']['material_ids']]
        raw=(json.dumps(part['buffers'],allow_nan=False)+'\n').encode();files[filename]=raw
        records.append(dict(name=name,asset_path='/Game/Unreal/Meshes/Lumen/'+name,cell=part['cell'],nanite=part['nanite'],
                            source_triangle_indices=part['source_triangle_indices'],source_file=filename,
                            source_sha256=hashlib.sha256(raw).hexdigest(),triangle_count=len(part['buffers']['triangles']),
                            materials=[plan['materials'][world['materials'][i]]['path'] for i in used]))
    bsp=read_world_bsp(Package61(package))
    lights,excluded=source_lights(parse_t3d(source.decode('utf-8')),bsp.point_zone)
    result=dict(schema_version=1,material_plan=str(material_path.resolve()),material_sha256=hashlib.sha256(material_path.read_bytes()).hexdigest(),
                source=geometry['source'],package=geometry['package'],map_path=plan['map_path'],chunks=records,lights=lights,excluded_lights=excluded,
                cell_size=cell_size,world_triangle_count=len(data['triangles']),
                lighting=dict(sun_lux=1000.0,sun_rotation=dict(pitch=-12.0,yaw=125.0,roll=0.0),sun_source_angle=2.0,
                              exposure_bias=-6.0,cloud_coverage=-0.2,cloud_density=0.008,fog_density=0.000015),
                limitations=['Modern artistic light intensities and HSV colors approximate source bytes; not a native UE1 lightmap conversion',
                             'Source class defaults come from the pinned Light reference; original v61 class defaults are not decoded',
                             'Modern atmosphere/clouds replace the inspection sky; original sky portals, planets, lightning and fire/water animation remain pending'])
    destination.mkdir()
    for filename,raw in files.items():(destination/filename).write_bytes(raw)
    (destination/'Unreal.lighting.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('materials',type=Path);p.add_argument('source',type=Path);p.add_argument('package',type=Path)
    p.add_argument('--output-dir',required=True,type=Path);p.add_argument('--cell-size',type=float,default=3200)
    a=p.parse_args();prepare_lighting(a.materials,a.source,a.package,a.output_dir,cell_size=a.cell_size)
