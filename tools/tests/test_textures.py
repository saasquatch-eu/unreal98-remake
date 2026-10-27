"""Synthetic P8 packages and UV fixtures; no game-derived bytes."""
import hashlib
import struct

import pytest

from ue1_converter.package61 import Package61,PackageError
from ue1_converter.texture61 import Texture,decode_texture,tga_bytes
from ue1_converter.material_prepare import normalized_uvs,safe_parts


def index(v):
    sign=128 if v<0 else 0;v=abs(v);out=bytearray([sign|(64 if v>=64 else 0)|(v&63)]);v>>=6
    while v:out.append((128 if v>=128 else 0)|(v&127));v>>=7
    return bytes(out)


def fixture(*,flags=1,version=61,texture_class='Texture',fmt=0,palette_ref=2,tail=b'',dimensions=(2,2),bad_mip=False,palette_count=256,duplicate=False):
    names=['None','Core','Class','Texture','Palette','Tile','PaletteData','Format','USize','VSize','UBits','VBits','InternalTime',texture_class]
    n=lambda s:index(names.index(s))
    imports=b''.join(n('Core')+n('Class')+bytes(4)+n(c) for c in (texture_class,'Palette'))
    tag=lambda k,t,raw:n(k)+bytes([t])+raw
    props=tag('Format',1,bytes([fmt]))+tag('Palette',5,index(palette_ref))
    props+=b''.join(tag(k,0x22,struct.pack('<i',v)) for k,v in zip(('USize','VSize'),dimensions))
    props+=tag('InternalTime',0x22,bytes(4))+n('InternalTime')+bytes([0xa2,1])+bytes(4)
    if duplicate:props+=tag('Format',1,bytes([fmt]))
    # Two asymmetric mip levels exercise row/channel order and exact table consumption.
    texture=props+n('None')+index(2)+index(4)+bytes([0,1,2,3])+struct.pack('<iiBB',2 if not bad_mip else 4,2,1,1)
    texture+=index(1)+bytes([2])+struct.pack('<iiBB',1,1,0,0)+tail
    colors=b''.join(bytes([i,255-i,(i*7)%256,(i*3)%256]) for i in range(256))
    palette=n('None')+index(palette_count)+colors
    name_data=b''.join(s.encode()+b'\0'+bytes(4) for s in names)
    io=60+len(name_data);offset=io+len(imports);table=[]
    # Palette has the same path as the texture: class-aware resolution is essential.
    for cls,body in ((-1,texture),(-2,palette)):
        table.append(index(cls)+index(0)+bytes(4)+n('Tile')+bytes(4)+index(len(body))+index(offset));offset+=len(body)
    h=struct.pack('<IHHIiiiiii',0x9e2a83c1,version,0,flags,len(names),60,2,offset,2,io)
    return h.ljust(60,b'\0')+name_data+imports+texture+palette+b''.join(table)


def test_p8_decode_exact_mips_palette_channels_and_source_immutability():
    raw=fixture();before=hashlib.sha256(raw).hexdigest()
    t=decode_texture(Package61(raw,allow_download_flag=True),'Demo.Tile','Demo')
    assert (t.width,t.height,t.pixels)==(2,2,bytes([0,1,2,3]))
    assert len(t.metadata['mips'])==2
    assert t.rgba()[:8]==bytes([0,255,0,255,1,254,7,255])
    assert t.rgba(True)[:8]==bytes([0,255,0,0,1,254,7,255])
    image=tga_bytes(t,True)
    assert image[17]==0x28 and image[18:26]==bytes([0,255,0,0,7,254,1,255])
    assert hashlib.sha256(raw).hexdigest()==before


def test_download_flag_is_opt_in_and_other_flags_are_still_rejected():
    with pytest.raises(PackageError):Package61(fixture())
    assert Package61(fixture(),allow_download_flag=True).flags==1
    for flags in (2,3,0x02000000):
        with pytest.raises(PackageError):Package61(fixture(flags=flags),allow_download_flag=True)


@pytest.mark.parametrize('change',[dict(version=62),dict(texture_class='FireTexture'),dict(fmt=1),dict(palette_ref=-1),dict(palette_ref=1),dict(tail=b'!'),dict(dimensions=(3,2)),dict(bad_mip=True),dict(palette_count=255),dict(duplicate=True)])
def test_unexplained_or_unsupported_texture_data_is_rejected(change):
    with pytest.raises(PackageError):decode_texture(Package61(fixture(**change),allow_download_flag=True),'Demo.Tile','Demo')


def test_truncated_texture_data_is_rejected():
    with pytest.raises(PackageError):Package61(fixture()[:-8],allow_download_flag=True)


def test_normalized_uvs_preserve_pan_repeats_sign_and_v_direction():
    f=dict(points=[2,7,9],uv_texels=[[-16,32],[48,-64],[16,0]])
    assert normalized_uvs(f,16,32)=={2:[-1,1],7:[3,-2],9:[1,0]}


@pytest.mark.parametrize('face',[dict(points=[1],uv_texels=[]),dict(points=[1],uv_texels=[[float('nan'),0]]),dict(points=[1,1],uv_texels=[[0,0],[1,0]])])
def test_invalid_or_ambiguous_uvs_are_rejected(face):
    with pytest.raises(ValueError):normalized_uvs(face,16,16)


@pytest.mark.parametrize('path',['../escape','Demo.Group.bad/name','Demo..Tile','OnlyName'])
def test_resource_paths_cannot_escape_output(path):
    with pytest.raises(ValueError):safe_parts(path)


def material_fixture(tmp_path,texture_class='Texture'):
    import json
    from ue1_converter.ue5_prepare import prepare_import
    root=tmp_path/'textures';root.mkdir();(root/'Demo.utx').write_bytes(fixture(texture_class=texture_class))
    g=dict(schema_version=1,source=dict(name='Demo.t3d'),package=dict(sha256='synthetic'),
           points=[[0,0,0],[2,0,0],[0,2,0]],surfaces=[dict(normal=[0,0,1],texture='Demo.Tile',flags=2)],
           faces=[dict(role='world',object='Demo_ue5',surface=0,points=[0,1,2],triangles=[[0,1,2]],uv_texels=[[-2,0],[2,0],[-2,2]])],
           movers=[],zone_samples=[dict(actor_class='InterpolationPoint',position=[0,0,2],rotation=None)])
    source=tmp_path/'Demo.geometry.json';source.write_text(json.dumps(g))
    prepare_import(source,tmp_path/'geometry-ready')
    return source,tmp_path/'geometry-ready/Demo.import.json',root


def test_material_recipe_replaces_only_uvs_and_adds_local_material_ids(tmp_path):
    import json
    from ue1_converter.material_prepare import prepare_materials
    source,recipe,root=material_fixture(tmp_path)
    result=prepare_materials(source,recipe,root,tmp_path/'ready')
    before=json.loads((recipe.parent/'Demo_ue5.mesh.json').read_text())
    after=json.loads((tmp_path/'ready/Demo_ue5.mesh.json').read_text())
    for key in ('vertices','normals','triangles'):assert after[key]==before[key]
    assert after['uv0']==[[-1,0],[1,0],[-1,1]]
    assert after['triangles']==[[0,2,1]] and after['material_ids']==[0]
    assert result['materials'][0]['mode']=='masked'
    assert result['textures'][0]['asset_path']=='/Game/Unreal/Textures/Demo/Tile_ue5'
    raw=(tmp_path/'ready/Textures/Demo/Tile.tga').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==result['textures'][0]['source_sha256']
    with pytest.raises(FileExistsError):prepare_materials(source,recipe,root,tmp_path/'ready')


def test_procedural_texture_is_explicitly_deferred_without_decoding_pixels(tmp_path):
    from ue1_converter.material_prepare import prepare_materials
    source,recipe,root=material_fixture(tmp_path,'FireTexture')
    result=prepare_materials(source,recipe,root,tmp_path/'ready')
    assert not result['textures']
    assert result['deferred']==[dict(path='Demo.Tile',reason='procedural FireTexture',width=2,height=2)]
    assert result['materials'][0]['texture'] is None
    assert result['materials'][0]['mode']=='deferred' and result['materials'][0]['deferred']


@pytest.mark.parametrize('changed',['geometry','mesh'])
def test_changed_geometry_or_buffer_provenance_blocks_material_preparation(tmp_path,changed):
    from ue1_converter.material_prepare import prepare_materials
    source,recipe,root=material_fixture(tmp_path)
    target=source if changed=='geometry' else recipe.parent/'Demo_ue5.mesh.json'
    target.write_text(target.read_text()+' ')
    with pytest.raises(ValueError,match='provenance'):prepare_materials(source,recipe,root,tmp_path/'ready')
    assert not (tmp_path/'ready').exists()
