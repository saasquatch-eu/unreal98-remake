"""Authored native-table fixtures; no game-derived bytes or coordinates."""

import hashlib
import json
from pathlib import Path
import struct

import pytest

from ue1_converter.__main__ import main
from ue1_converter.geometry import extract_geometry,obj_text,surface_role,write_bundle
from ue1_converter.native_bsp import read_world_bsp
from ue1_converter.package61 import Package61,PackageError
from ue1_converter.triangulation import triangulate


def index(value):
    sign=128 if value<0 else 0;value=abs(value)
    data=bytearray([sign|(64 if value>=64 else 0)|(value&63)]);value>>=6
    while value:
        data.append((128 if value>=128 else 0)|(value&127));value>>=7
    return bytes(data)


def text(value):
    raw=value.encode()+b'\0'
    return index(len(raw))+raw


def native_fixture(*,child=-1,first=0,trailing=False,bad_model=False):
    classes=['Level','Model','Vectors','BspNodes','BspSurfs','Verts','Polys','Brush','SkyZoneInfo']
    exports=[('MyLevel','Level'),('WorldModel','Model'),('Points','Vectors'),('Directions','Vectors'),
             ('Nodes','BspNodes'),('Surfaces','BspSurfs'),('Vertices','Verts'),('Polygons','Polys'),
             ('SyntheticBrush','Brush'),('SyntheticSky','SkyZoneInfo'),('LargerDecoy','Model')]
    names=list(dict.fromkeys(['None','Core','Class','Package','Engine','Texture','DemoStone','Group','Tile']+classes+[n for n,c in exports]))
    name=lambda value:index(names.index(value))
    imports=[('Core','Class',0,c) for c in classes]
    imports += [('Core','Package',0,'DemoStone'),('Core','Package',-10,'Group'),('Engine','Texture',-11,'Tile')]
    imports_data=b''.join(name(cp)+name(cn)+struct.pack('<i',outer)+name(n) for cp,cn,outer,n in imports)
    array=lambda count,payload:b'\0'+struct.pack('<ii',count,count)+payload
    points=[(0,0,0),(2,0,0),(2,2,0),(0,2,0)]
    vectors=[(0,0,1),(1,0,0),(0,1,0)]
    node=struct.pack('<4fQB',0,0,1,0,2,0)
    node+=b''.join(index(i) for i in [first,0,-1,child,-1,-1,-1])+struct.pack('<BBBii',0,1,4,-1,-1)
    node_data=array(1,node)+index(3)
    node_data+=index(0)+struct.pack('<QQ',0,0)+index(0)+struct.pack('<QQ',2,2)+index(10)+struct.pack('<QQ',4,4)
    if trailing:node_data+=b'!'
    surface=index(-12)+struct.pack('<I',0)+b''.join(index(i) for i in [0,0,1,2,-1,0])+struct.pack('<hh',7,-3)+index(9)
    level=array(2,index(9)+index(10))
    level+=text('unreal')+text('')+text('Example.unr')+text('')+index(0)+struct.pack('<ii',7777,1)+index(11 if bad_model else 2)
    model=b'\0'+struct.pack('<6fB3f',*([0]*6),0,0,0,0)+b''.join(index(i) for i in [4,3,5,6,7,8])
    bodies=[level,model,array(4,b''.join(struct.pack('<3f',*p) for p in points)),
            array(3,b''.join(struct.pack('<3f',*v) for v in vectors)),node_data,array(1,surface),
            array(5,b''.join(index(p)+index(-1) for p in [0,1,2,3,999]))+index(0),
            b'\0',b'\0',b'\0',b'\0'+bytes(500)]
    name_data=b''.join(n.encode()+b'\0'+bytes(4) for n in names)
    import_offset=60+len(name_data)
    offset=import_offset+len(imports_data)
    table=[]
    for (n,c),body in zip(exports,bodies):
        table.append(index(-(classes.index(c)+1))+index(0)+bytes(4)+name(n)+bytes(4)+index(len(body))+index(offset))
        offset+=len(body)
    header=struct.pack('<IHHIiiiiii',0x9E2A83C1,61,0,0,len(names),60,len(exports),offset,len(imports),import_offset)
    return header.ljust(60,b'\0')+name_data+imports_data+b''.join(bodies)+b''.join(table)


SOURCE=b'''Begin Map
Begin Actor Class=Brush Name=SyntheticBrush
CsgOper=CSG_Subtract
Begin Brush Name=BrushModel
Begin PolyList
Begin Polygon Texture=DemoStone.Group.Tile
Origin 0,0,0
Normal 0,0,1
TextureU 1,0,0
TextureV 0,1,0
Pan U=7 V=-3
Vertex 0,0,0
Vertex 2,0,0
Vertex 2,2,0
Vertex 0,2,0
End Polygon
End PolyList
End Brush
Brush=Model'Example.BrushModel'
Location=(X=100)
End Actor
Begin Actor Class=InterpolationPoint Name=CameraPoint
Position=0
Location=(X=1,Y=1,Z=1)
End Actor
End Map
'''


def extract(data=None):
    data=native_fixture() if data is None else data
    return extract_geometry(SOURCE,data,'Example.t3d',hashlib.sha256(SOURCE).hexdigest(),hashlib.sha256(data).hexdigest())


def test_native_level_link_selects_world_model_and_checks_all_referenced_points():
    package=Package61(native_fixture())
    bsp=read_world_bsp(package)
    assert bsp.model_reference==2  # A larger decoy model must not be selected.
    assert bsp.reachable==(0,)
    assert bsp.points==((0,0,0),(2,0,0),(2,2,0),(0,2,0))
    assert bsp.unused_invalid_pool_entries==1
    assert bsp.point_zone((1,1,1))==1
    assert bsp.point_zone((1,1,-1))==0
    assert bsp.surfaces[0]['pan']==(7,-3)
    assert package.object_path(-12,'Example')=='DemoStone.Group.Tile'
    assert package.object_path(9,'Example')=='Example.SyntheticBrush'


@pytest.mark.parametrize('options',[{'child':0},{'child':7},{'first':1},{'trailing':True},{'bad_model':True}])
def test_native_corruption_and_cycles_fail_closed(options):
    with pytest.raises(PackageError):read_world_bsp(Package61(native_fixture(**options)))


def test_object_paths_reject_import_cycles():
    package=Package61(native_fixture())
    cp,cn,outer,n=package.imports[10]
    package.imports[10]=(cp,cn,-11,n)
    with pytest.raises(PackageError,match='cycle'):package.object_path(-12,'Example')


def test_extraction_keeps_native_coordinates_uvs_and_source_metadata():
    g=extract()
    assert g['points'][:4]==[(0,0,0),(2,0,0),(2,2,0),(0,2,0)]
    assert g['surfaces'][0]['texture']=='DemoStone.Group.Tile'
    assert g['faces'][0]['uv_texels']==[[7,-3],[9,-3],[9,-1],[7,-1]]
    assert g['diagnostics']['render_triangles']==2
    assert g['zone_samples'][0]['zone']==1
    assert g['diagnostics']['bounds']=={'minimum':[0,0,0],'maximum':[2,2,0]}
    assert obj_text(g).count('\nf ')==2
    assert 'Example_ue5' in obj_text(g)
    assert '\nvt ' not in obj_text(g)  # Texel coordinates must not masquerade as normalized UVs.


@pytest.mark.parametrize('flags,zones,sky,role',[
    (0,(0,1),{2},'world'),(8,(0,1),{2},'world'),(32,(0,1),{2},'world'),
    (128,(0,1),{2},'sky_mask'),(0,(0,2),{2},'sky_geometry'),
    (1,(0,1),{2},'invisible'),(1|0x04000000,(1,2),set(),'invisible_portal'),
    (0x04000000|4,(1,2),set(),'world'),(0,(0,0),set(),'solid_interior')])
def test_solidity_and_render_roles_do_not_turn_portals_or_sky_into_walls(flags,zones,sky,role):
    assert surface_role(flags,zones,sky)==role


def area(triangle,points):
    a,b,c=(points[i] for i in triangle)
    return abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2


@pytest.mark.parametrize('points,expected',[
    ([(0,0,0),(2,0,0),(2,2,0),(0,2,0)],4),
    ([(0,0,0),(2,0,0),(2,1,0),(1,1,0),(1,2,0),(0,2,0)],3),
    ([(0,0,0),(1,0,0),(2,0,0),(2,2,0),(0,2,0),(0,0,0)],4),
    ([(0,2,0),(2,2,0),(2,0,0),(0,0,0)],4)])
def test_triangulation_preserves_convex_concave_collinear_and_reversed_boundaries(points,expected):
    triangles=triangulate(points,(0,0,1))
    assert sum(area(t,points) for t in triangles)==pytest.approx(expected)
    assert all(area(t,points)>0 for t in triangles)
    for a,b,c in triangles:
        pa,pb,pc=points[a],points[b],points[c]
        assert (pb[0]-pa[0])*(pc[1]-pa[1])-(pb[1]-pa[1])*(pc[0]-pa[0])>0


@pytest.mark.parametrize('points',[
    [(0,0,0),(1,1,0),(0,1,0),(1,0,0)],
    [(0,0,0),(1,0,0),(2,0,0)],
    [(float('nan'),0,0),(1,0,0),(0,1,0)],
    [(0,0,0)]*257])
def test_bad_polygon_boundaries_are_not_silently_fanned(points):
    with pytest.raises(ValueError):triangulate(points,(0,0,1))


def test_collinear_boundary_corners_stay_connected_to_triangles():
    points=[(0,0,0),(1,0,0),(2,0,0),(3,0,0),(3,2,0),(0,2,0)]
    triangles=triangulate(points,(0,0,1))
    assert set(i for t in triangles for i in t)==set(range(len(points)))
    assert len(triangles)==len(points)-2
    assert sum(area(t,points) for t in triangles)==pytest.approx(6)


def test_zero_width_spur_is_removed_without_changing_projected_area():
    points=[(0,0,0),(2,0,0),(2,1,0),(2,0.75,0),(2,2,0),(0,2,0)]
    triangles=triangulate(points,(0,0,1))
    assert sum(area(t,points) for t in triangles)==pytest.approx(4)
    used={i for t in triangles for i in t}
    assert len(used)==5 and not {2,3}<=used


def test_bundle_refuses_replacement_and_cli_binds_provenance(tmp_path,capsys):
    source=tmp_path/'Example.t3d';source.write_bytes(SOURCE)
    package=tmp_path/'Example.unr';package.write_bytes(native_fixture())
    source.with_suffix('.source-baseline.json').write_text(json.dumps({str(package):hashlib.sha256(package.read_bytes()).hexdigest()}))
    source.with_suffix('.export-summary.json').write_text(json.dumps({'sha256':hashlib.sha256(SOURCE).hexdigest()}))
    destination=tmp_path/'geometry'
    command=['extract-bsp',str(source),'--package',str(package),'--output-dir',str(destination)]
    assert main(command)==0
    report=json.loads((destination/'Example.geometry.json').read_text())
    assert report['diagnostics']['render_triangles']==2
    assert (destination/'Example_ue5.obj').exists()
    before={p:p.read_bytes() for p in destination.iterdir()}
    assert main(command)==2
    assert all(p.read_bytes()==data for p,data in before.items())
    with pytest.raises(FileExistsError):write_bundle(extract(),source)
    assert source.read_bytes()==SOURCE
    package.write_bytes(package.read_bytes()+b'changed')
    assert main(command)==2
    assert 'checksum' in capsys.readouterr().err
