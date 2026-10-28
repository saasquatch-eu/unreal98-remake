"""Verify saved water/flame bindings, source geometry, lit material and GPU frames."""
import hashlib
import json
from pathlib import Path
import runpy

import unreal

ROOT = Path(__file__).resolve().parents[2]


def verify(plan_path, report_path, *, lighting_profile=None):
    plan_path = Path(plan_path); helper = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_water.py'))
    plan = helper['checked_plan'](plan_path)
    fire = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_fire.py'))
    baseline = fire['verify'](plan['fire_plan'], ROOT / '.local/logs/unreal-fire-verified.json', additional_bindings=plan['bindings'], lighting_profile=lighting_profile)
    report = dict(status='success', plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  world_triangles=baseline['world_triangles'], mover_triangles=baseline['mover_triangles'],
                  flame_triangles=baseline['flame_triangles'], water_triangles=sum(e['triangles'] for e in plan['bindings']),
                  bindings=plan['bindings'], textures=[])
    parent = unreal.load_asset(helper['PARENT']); edit = unreal.MaterialEditingLibrary
    if parent.get_editor_property('blend_mode') != unreal.BlendMode.BLEND_TRANSLUCENT or parent.get_editor_property('shading_model') != unreal.MaterialShadingModel.MSM_DEFAULT_LIT:
        raise RuntimeError('water blend/shading differs')
    if not parent.get_editor_property('two_sided') or parent.get_editor_property('translucency_lighting_mode') != unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING:
        raise RuntimeError('water surface lighting differs')
    if not edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_BASE_COLOR): raise RuntimeError('water has no lit color input')
    for e in plan['textures']:
        texture = unreal.load_asset(e['texture_path']); material = unreal.load_asset(e['material_path']); source = unreal.load_asset(e['source_image_asset'])
        if (source.blueprint_get_size_x(), source.blueprint_get_size_y()) != (e['width'], e['height']) or not source.get_editor_property('srgb'):
            raise RuntimeError('original water image dimensions/color space differ')
        size = ((e['width'] + e['padding'] * 2) * e['columns'], (e['height'] + e['padding'] * 2) * e['rows'])
        if (texture.blueprint_get_size_x(), texture.blueprint_get_size_y()) != size: raise RuntimeError('water atlas dimensions differ')
        if not texture.get_editor_property('srgb') or texture.get_editor_property('mip_gen_settings') != unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS or not texture.get_editor_property('never_stream'):
            raise RuntimeError('water atlas color/mip/residency differs')
        if texture.get_editor_property('filter') != unreal.TextureFilter.TF_BILINEAR or any(texture.get_editor_property(k) != unreal.TextureAddress.TA_WRAP for k in ('address_x', 'address_y')):
            raise RuntimeError('water atlas filtering/addressing differs')
        if material.get_editor_property('parent') != parent or edit.get_material_instance_texture_parameter_value(material, 'WaterAtlas') != texture:
            raise RuntimeError('water material parent/texture differs')
        values = dict(Rows=e['rows'], Columns=e['columns'], PlaybackRate=e['fps'] / e['frames'], PhaseOffset=0,
                      InnerScale=e['uv_scale'], InnerBias=e['uv_bias'], ColorStrength=e['color_strength'],
                      Opacity=e['opacity'], Roughness=e['roughness'], PreviewEmissive=0)
        for name, value in values.items():
            if abs(edit.get_material_instance_scalar_parameter_value(material, name) - value) > 1e-6: raise RuntimeError('water parameter differs: ' + name)
        report['textures'].append(dict(path=e['texture_path'], dimensions=size, source_image=e['source_image_asset'], frames=e['frames'], fps=e['fps']))
    # The exact same sampling graph is exercised; diagnostic emission is transient.
    report['gpu'] = fire['verify_gpu'](plan, scalar_overrides=dict(PlaybackRate=0, ColorStrength=1, PreviewEmissive=1, Opacity=1))
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_WATER_VERIFY_SUCCESS')
    return report


if __name__ == '__main__':
    verify(ROOT / 'data/converted/Unreal/Maps/Unreal/water-ready/Unreal.water.json', ROOT / '.local/logs/unreal-water-verified.json')
