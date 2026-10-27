"""Prepare private original-color images and normalized UV/material buffers."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

from .package61 import Package61,PackageError
from .texture61 import decode_texture,tga_bytes,properties,scalar
from .ue5_prepare import validate_buffers


def safe_parts(path):
    parts=path.split('.')
    if len(parts)<2 or any(not re.fullmatch(r'[A-Za-z0-9_-]+',p) for p in parts):raise ValueError('unsafe resource path')
    return parts


def normalized_uvs(face,width,height):
    if width<=0 or height<=0:raise ValueError('invalid texture dimensions')
    if len(face['points'])!=len(face['uv_texels']):raise ValueError('UV corner count differs')
    uv={}
    for point,texels in zip(face['points'],face['uv_texels']):
        if len(texels)!=2 or not all(math.isfinite(v) for v in texels):raise ValueError('invalid source UVs')
        value=[texels[0]/width,texels[1]/height]
        if point in uv and uv[point]!=value:raise ValueError('ambiguous repeated UV corner')
        uv[point]=value
    return uv


def prepare_materials(geometry_path,recipe_path,texture_root,destination):
    geometry_path,recipe_path,texture_root,destination=map(Path,(geometry_path,recipe_path,texture_root,destination))
    g=json.loads(geometry_path.read_text());original=json.loads(recipe_path.read_text())
    if hashlib.sha256(geometry_path.read_bytes()).hexdigest()!=original['geometry_sha256']:raise ValueError('geometry provenance changed')
    faces=[f for f in g['faces'] if f['role'] in ('world','mover')]
    paths=sorted({g['surfaces'][f['surface']]['texture'] for f in faces if g['surfaces'][f['surface']]['texture']})
    packages={};textures={};deferred=[];files={}
    for path in paths:
        parts=safe_parts(path);name=parts[0]
        if name not in packages:
            package_path=texture_root/(name+'.utx');raw=package_path.read_bytes()
            packages[name]=(Package61(raw,allow_download_flag=True),dict(file=str(package_path.resolve()),sha256=hashlib.sha256(raw).hexdigest()))
        package=packages[name][0]
        matches=[e for e in package.exports if package.object_path(e.index+1,name)==path and package.class_name(e)!='Palette']
        if len(matches)!=1:raise PackageError('ambiguous or missing texture object: '+path)
        cls=package.class_name(matches[0])
        if cls!='Texture':
            if cls not in ('WetTexture','FireTexture','WaterTexture','WaveTexture','IceTexture'):raise PackageError('unknown texture class: '+cls)
            props,_=properties(package,matches[0])
            width,height=scalar(props,'USize',2),scalar(props,'VSize',2)
            if any(not isinstance(v,int) or not 1<=v<=4096 or v&(v-1) for v in (width,height)):raise PackageError('invalid procedural texture dimensions')
            deferred.append(dict(path=path,reason='procedural '+cls,width=width,height=height));continue
        texture=decode_texture(package,path,name)
        filename='/'.join(['Textures']+parts[:-1]+[parts[-1]+'.tga'])
        # Alpha zero for palette index 0 is stored, but only masked parents use it.
        raw=tga_bytes(texture,masked=True);files[filename]=raw
        textures[path]=dict(**texture.metadata,source_file=filename,source_sha256=hashlib.sha256(raw).hexdigest(),
                            asset_path='/Game/Unreal/Textures/'+'/'.join(parts[:-1]+[parts[-1]+'_ue5']))
    procedural={e['path']:e for e in deferred}
    materials=[];material_lookup={};mesh_records=[]
    for mesh in original['meshes']:
        source=recipe_path.parent/mesh['source_file'];raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=mesh['source_sha256']:raise ValueError('original buffer provenance changed')
        data=json.loads(raw);uvs=[];slots=[];ids=[]
        for face in (f for f in faces if f['object']==mesh['name']):
            surface=g['surfaces'][face['surface']];path=surface['texture'];flags=surface['flags']
            texture=textures.get(path)
            pending=procedural.get(path)
            dimensions=texture or pending
            # Procedural images get transparent placeholders; missing assignments remain neutral.
            key=(path,flags&0x00400146) if dimensions else (None,0)
            if key not in material_lookup:
                index=len(materials);material_lookup[key]=index
                mode='masked' if flags&2 else 'modulated' if flags&64 else 'translucent' if flags&4 else 'opaque'
                mode+=('_two_sided' if flags&256 else '')+('_unlit' if flags&0x400000 else '')
                if pending:mode='deferred'
                elif texture is None:mode='neutral'
                parts=safe_parts(path) if dimensions else []
                material_path='/Game/Unreal/Materials/'+'/'.join(parts[:-1]+[mode,parts[-1]+'_ue5']) if dimensions else '/Engine/BasicShapes/BasicShapeMaterial'
                materials.append(dict(path=material_path,texture=path if texture else None,deferred=bool(pending),source_texture=path,mode=mode,flags=flags if dimensions else 0))
            index=material_lookup[key]
            if index not in slots:slots.append(index)
            local_id=slots.index(index)
            uv=normalized_uvs(face,dimensions['width'],dimensions['height']) if dimensions else None
            for triangle in face['triangles']:
                uvs.extend([uv[i] for i in triangle] if uv else [[0,0],[1,0],[0,1]])
                ids.append(local_id)
        if len(ids)!=mesh['triangle_count'] or len(uvs)!=len(data['vertices']):raise ValueError('mesh triangle correspondence changed')
        data['uv0']=uvs
        validate_buffers(data)
        data['material_ids']=ids
        filename=mesh['name']+'.mesh.json';raw=(json.dumps(data,allow_nan=False)+'\n').encode();files[filename]=raw
        mesh_records.append(dict(**{k:v for k,v in mesh.items() if k not in ('source_file','source_sha256')},source_file=filename,
                                 source_sha256=hashlib.sha256(raw).hexdigest(),materials=slots))
    plan=dict(schema_version=1,geometry_sha256=original['geometry_sha256'],original_recipe=str(recipe_path.resolve()),
              original_recipe_sha256=hashlib.sha256(recipe_path.read_bytes()).hexdigest(),map_path=original['map_path'],
              textures=list(textures.values()),materials=materials,meshes=mesh_records,deferred=deferred,
              packages={k:v[1] for k,v in packages.items()},
              uv_convention='u=source_texel_u/width; v=source_texel_v/height; no flip or clamping',
              limitations=['Static base-color reconstruction; original lighting, detail maps and animation remain pending',
                           'Procedural effects are transparent placeholders; missing assignments retain neutral inspection material',
                           'Original translucent/modulated blending is an approximation; sky and collision remain pending'])
    destination.mkdir()
    for name,raw in files.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    (destination/'Unreal.materials.json').write_text(json.dumps(plan,indent=2)+'\n')
    return plan


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('geometry',type=Path);p.add_argument('recipe',type=Path);p.add_argument('--texture-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();prepare_materials(a.geometry,a.recipe,a.texture_root,a.output_dir)
