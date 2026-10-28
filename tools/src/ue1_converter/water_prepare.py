"""Prepare private source-image water animation and exact raster material bindings."""
import hashlib
import json
from pathlib import Path

from .fire61 import atlas_tga
from .material_prepare import safe_parts
from .package61 import Package61
from .texture61 import decode_texture, tga_bytes
from .water61 import decode_wet, water_frame


def prepare_water(material_path, lighting_path, fire_path, texture_root, destination):
    material_path, lighting_path, fire_path, texture_root, destination = map(Path, (material_path, lighting_path, fire_path, texture_root, destination))
    if destination.exists(): raise FileExistsError(destination)
    raw_material, raw_lighting, raw_fire = [p.read_bytes() for p in (material_path, lighting_path, fire_path)]
    material, lighting, fire = map(json.loads, (raw_material, raw_lighting, raw_fire))
    mh, lh = hashlib.sha256(raw_material).hexdigest(), hashlib.sha256(raw_lighting).hexdigest()
    if lighting['material_sha256'] != mh or fire['material_sha256'] != mh or fire['lighting_sha256'] != lh:
        raise ValueError('material/lighting/fire provenance differs')
    records = []; bindings = []; files = {}; packages = {}
    for pending in material['deferred']:
        if pending['reason'] != 'procedural WetTexture': continue
        parts = safe_parts(pending['path']); name = parts[0]; package_file = texture_root / (name + '.utx')
        raw = package_file.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        if digest != material['packages'][name]['sha256']: raise ValueError('source water package checksum changed')
        packages[name] = dict(file=str(package_file.resolve()), sha256=digest)
        wet = decode_wet(Package61(raw, allow_download_flag=True), pending['path'], name)
        if (wet.width, wet.height) != (pending['width'], pending['height']) or wet.width != wet.height:
            raise ValueError('water preview requires matching square source dimensions')
        source_parts = safe_parts(wet.source_texture); source_file = texture_root / (source_parts[0] + '.utx')
        source_raw = source_file.read_bytes()
        packages[source_parts[0]] = dict(file=str(source_file.resolve()), sha256=hashlib.sha256(source_raw).hexdigest())
        texture = decode_texture(Package61(source_raw, allow_download_flag=True), wet.source_texture, source_parts[0])
        if texture.metadata['palette'].casefold() != wet.palette_path.casefold(): raise ValueError('water palette reference differs from source image')
        if texture.metadata['anim_next'] is not None: raise ValueError('animated source-image chains are unsupported')
        frames = [water_frame(wet, texture, i / 64) for i in range(64)]
        if len(set(frames)) < 2: raise ValueError('water source image produces no visible animation')
        source_image = '/'.join(['Textures'] + source_parts[:-1] + [source_parts[-1] + '.tga'])
        filename = '/'.join(['Textures'] + parts[:-1] + ['Flipbook', parts[-1] + '.tga'])
        files[source_image] = tga_bytes(texture)
        files[filename] = atlas_tga(texture, frames, masked=False, wrap_padding=True)
        original = [m for m in material['materials'] if m.get('deferred') and m['source_texture'] == pending['path']]
        if len(original) != 1: raise ValueError('ambiguous source water material')
        # This checkpoint admits the castle's lit, two-sided, translucent subset.
        flags = original[0]['flags']
        if not flags & 4 or not flags & 256 or flags & 0x400000:
            raise ValueError('unsupported source water material flags')
        target = '/Game/Unreal/Materials/' + '/'.join(parts[:-1] + ['animated', parts[-1] + '_ue5'])
        for chunk in lighting['chunks']:
            for slot, path in enumerate(chunk['materials']):
                if path != original[0]['path']: continue
                if chunk['nanite']: raise ValueError('translucent water cannot be admitted to Nanite')
                data = (lighting_path.parent / chunk['source_file']).read_bytes()
                if hashlib.sha256(data).hexdigest() != chunk['source_sha256']: raise ValueError('water mesh buffer checksum changed')
                bindings.append(dict(actor=chunk['name'], slot=slot, original_material=path, material=target,
                                     triangles=json.loads(data)['material_ids'].count(slot)))
        records.append(dict(**wet.metadata, source_image_metadata=texture.metadata, source_image_file=source_image,
                            source_image_sha256=hashlib.sha256(files[source_image]).hexdigest(),
                            source_image_asset='/Game/Unreal/Textures/' + '/'.join(source_parts[:-1] + [source_parts[-1] + '_ue5']),
                            source_file=filename, source_sha256=hashlib.sha256(files[filename]).hexdigest(),
                            texture_path='/Game/Unreal/Textures/' + '/'.join(parts[:-1] + ['Flipbook', parts[-1] + '_ue5']),
                            material_path=target, original_material=original[0]['path'], source_flags=flags,
                            frames=64, columns=8, rows=8, fps=16, padding=2,
                            uv_scale=wet.width / (wet.width + 4), uv_bias=2 / (wet.width + 4),
                            opacity=0.7, roughness=0.2, color_strength=1.0, displacement_pixels=16.0))
    if not records or not bindings: raise ValueError('no source water surfaces found')
    result = dict(schema_version=1, material_plan=str(material_path.resolve()), material_sha256=mh,
                  lighting_plan=str(lighting_path.resolve()), lighting_sha256=lh,
                  fire_plan=str(fire_path.resolve()), fire_sha256=hashlib.sha256(raw_fire).hexdigest(),
                  map_path=lighting['map_path'], textures=records, bindings=bindings, packages=packages,
                  limitations=['Independent periodic horizontal warp, not the native WetTexture solver',
                               'Raw drop coordinates anchor authored oscillators; native grid scaling and byte_a..d semantics are not inferred',
                               'Four-second/16-FPS timing, distortion, opacity and roughness are authored preview choices',
                               'Modern alpha translucency approximates source blending; no screen refraction or high-quality water reflections are established',
                               'Original sky and flyby playback remain pending'])
    destination.mkdir()
    for filename, data in files.items():
        path = destination / filename; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    (destination / 'Unreal.water.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('materials', type=Path); p.add_argument('lighting', type=Path); p.add_argument('fire', type=Path)
    p.add_argument('--texture-root', required=True, type=Path); p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); prepare_water(a.materials, a.lighting, a.fire, a.texture_root, a.output_dir)
