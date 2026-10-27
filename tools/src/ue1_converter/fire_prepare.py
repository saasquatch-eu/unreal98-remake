"""Prepare private flame atlases and explicit source-to-preview material bindings."""
import hashlib
import json
from pathlib import Path

from .fire61 import decode_fire, render_fire, atlas_tga
from .material_prepare import safe_parts
from .package61 import Package61


def prepare_fire(material_path, lighting_path, texture_root, destination):
    material_path, lighting_path, texture_root, destination = map(Path, (material_path, lighting_path, texture_root, destination))
    if destination.exists():
        raise FileExistsError(destination)
    material_raw, lighting_raw = material_path.read_bytes(), lighting_path.read_bytes()
    materials, lighting = json.loads(material_raw), json.loads(lighting_raw)
    if hashlib.sha256(material_raw).hexdigest() != lighting['material_sha256']:
        raise ValueError('lighting/material provenance differs')
    entries = []; files = {}; bindings = []
    for pending in materials['deferred']:
        if pending['reason'] != 'procedural FireTexture':
            continue
        source_path = pending['path']; parts = safe_parts(source_path); package_name = parts[0]
        package_path = texture_root / (package_name + '.utx'); raw = package_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != materials['packages'][package_name]['sha256']:
            raise ValueError('source fire package checksum changed')
        fire = decode_fire(Package61(raw, allow_download_flag=True), source_path, package_name)
        if fire.width != fire.height:
            raise ValueError('castle flame previews require square frames')
        if (fire.width, fire.height) != (pending['width'], pending['height']):
            raise ValueError('source fire dimensions changed')
        seed = int(fire.metadata['export_sha256'][:8], 16)
        frames = render_fire(fire, seed=seed)
        filename = '/'.join(['Textures'] + parts[:-1] + ['Flipbook', parts[-1] + '.tga'])
        atlas = atlas_tga(fire, frames); files[filename] = atlas
        texture_path = '/Game/Unreal/Textures/' + '/'.join(parts[:-1] + ['Flipbook', parts[-1] + '_ue5'])
        target = '/Game/Unreal/Materials/' + '/'.join(parts[:-1] + ['animated', parts[-1] + '_ue5'])
        previous = [m['path'] for m in materials['materials'] if m.get('deferred') and m['source_texture'] == source_path]
        if len(previous) != 1:
            raise ValueError('ambiguous original flame material')
        for chunk in lighting['chunks']:
            for slot, path in enumerate(chunk['materials']):
                if path != previous[0]:
                    continue
                if chunk['nanite']:
                    raise ValueError('transparent fire cannot be admitted to a Nanite chunk')
                buffer_raw = (lighting_path.parent / chunk['source_file']).read_bytes()
                if hashlib.sha256(buffer_raw).hexdigest() != chunk['source_sha256']:
                    raise ValueError('lighting buffer checksum changed')
                ids = json.loads(buffer_raw)['material_ids']
                bindings.append(dict(actor=chunk['name'], slot=slot, original_material=path,
                                     material=target, triangles=ids.count(slot)))
        entries.append(dict(**fire.metadata, package_sha256=hashlib.sha256(raw).hexdigest(),
                            source_file=filename, source_sha256=hashlib.sha256(atlas).hexdigest(),
                            texture_path=texture_path, material_path=target, original_material=previous[0],
                            columns=8, rows=8, frames=64, fps=16, padding=2,
                            uv_scale=[fire.width / (fire.width + 4), fire.height / (fire.height + 4)],
                            uv_bias=[2 / (fire.width + 4), 2 / (fire.height + 4)],
                            emissive_strength=64.0, seed=seed))
    if not entries or not bindings:
        raise ValueError('no source fire surfaces found')
    result = dict(schema_version=1, material_plan=str(material_path.resolve()), material_sha256=hashlib.sha256(material_raw).hexdigest(),
                  lighting_plan=str(lighting_path.resolve()), lighting_sha256=hashlib.sha256(lighting_raw).hexdigest(),
                  map_path=lighting['map_path'], textures=entries, bindings=bindings,
                  limitations=['Independent heat/particle preview, not the original native fire simulation',
                               'Original spark bytes retained; byte_a..d motion semantics are not inferred',
                               'Normal/Lathe and Blaze/OzHasSpoken/BlazeLeft are the only supported preview modes',
                               '16 FPS, four-second loop, emissive gain and particle motion are authored preview choices',
                               'Water, original sky and camera playback remain pending'])
    destination.mkdir()
    for filename, data in files.items():
        path = destination / filename; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    (destination / 'Unreal.fire.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('materials', type=Path); parser.add_argument('lighting', type=Path)
    parser.add_argument('--texture-root', required=True, type=Path); parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    prepare_fire(args.materials, args.lighting, args.texture_root, args.output_dir)
