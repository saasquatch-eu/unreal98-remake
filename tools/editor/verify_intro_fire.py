"""Reload the castle and verify explicit flame bindings without changing source assets."""
import hashlib
import json
from pathlib import Path
import runpy
import struct

import unreal

ROOT = Path(__file__).resolve().parents[2]


def verify_gpu(plan, *, scalar_overrides=None):
    """Draw every frame through the real material function using transient MIDs/targets."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    reports = []
    for entry in plan['textures']:
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, unreal.load_asset(entry['material_path']))
        values = dict(PlaybackRate=0.0, EmissiveStrength=1.0) if scalar_overrides is None else scalar_overrides
        for name, value in values.items(): mid.set_scalar_parameter_value(name, value)
        hashes = []; counts = []
        for frame in range(entry['frames']):
            target = unreal.RenderingLibrary.create_render_target2d(world, entry['width'], entry['height'], unreal.TextureRenderTargetFormat.RTF_RGBA8)
            mid.set_scalar_parameter_value('PhaseOffset', frame / entry['frames'])
            unreal.RenderingLibrary.clear_render_target2d(world, target, unreal.LinearColor(0, 0, 0, 1))
            unreal.RenderingLibrary.draw_material_to_render_target(world, target, mid)
            colors = unreal.RenderingLibrary.read_render_target_raw(world, target, False)
            if len(colors) != entry['width'] * entry['height']: raise RuntimeError('GPU animation readback dimensions differ')
            counts.append(sum(max(c.r, c.g, c.b) > 0.002 for c in colors))
            hashes.append(hashlib.sha256(b''.join(struct.pack('<fff', c.r, c.g, c.b) for c in colors)).hexdigest())
            if frame in (0, entry['frames'] // 2):
                unreal.RenderingLibrary.export_render_target(world, target, str(ROOT / '.local'), entry['path'].split('.')[-1] + '-gpu-' + str(frame) + '.png')
            unreal.RenderingLibrary.release_render_target2d(target)
        if min(counts) <= 10 or len(set(hashes)) < 2: raise RuntimeError('animation frames are blank or do not change')
        reports.append(dict(path=entry['path'], rendered_frames=len(hashes), distinct_frames=len(set(hashes)), nonblack_pixels=counts, frame_hashes=hashes))
    return reports


def verify(plan_path, report_path, *, additional_bindings=(), lighting_profile=None):
    plan_path = Path(plan_path)
    helper = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_fire.py'))
    plan = helper['checked_plan'](plan_path)
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_lumen_lighting.py'))['verify'](plan['lighting_plan'], ROOT / '.local/logs/unreal-lumen-verified.json', lighting_profile=lighting_profile)
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    lighting = json.loads(Path(plan['lighting_plan']).read_text())
    own = {(e['actor'], e['slot']): e for e in plan['bindings']}
    bindings = dict(own)
    for entry in additional_bindings:
        key = entry['actor'], entry['slot']
        if key in bindings: raise RuntimeError('conflicting later-stage material binding')
        bindings[key] = entry
    chunks = {e['name']: e for e in lighting['chunks']}
    for (actor, slot), entry in bindings.items():
        chunk = chunks.get(actor)
        if chunk is None or not 0 <= slot < len(chunk['materials']) or chunk['materials'][slot] != entry['original_material']:
            raise RuntimeError('material binding source differs')
    parent = unreal.load_asset(helper['PARENT']); edit = unreal.MaterialEditingLibrary
    if not parent or parent.get_editor_property('blend_mode') != unreal.BlendMode.BLEND_ADDITIVE or not parent.get_editor_property('two_sided'):
        raise RuntimeError('fire material blend/sides differ')
    functions = [e.get_editor_property('material_function') for e in edit.get_material_expressions(parent) if isinstance(e, unreal.MaterialExpressionMaterialFunctionCall)]
    if unreal.load_asset(helper['FUNCTION']) not in functions: raise RuntimeError('engine FlipBook function missing')
    report = dict(status='success', plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  world_triangles=baseline['visible_world_triangles'], mover_triangles=baseline['movable_mover_triangles'], textures=[], bindings=[])
    for entry in plan['textures']:
        texture = unreal.load_asset(entry['texture_path']); material = unreal.load_asset(entry['material_path'])
        size = ((entry['width'] + entry['padding'] * 2) * entry['columns'], (entry['height'] + entry['padding'] * 2) * entry['rows'])
        if (texture.blueprint_get_size_x(), texture.blueprint_get_size_y()) != size: raise RuntimeError('atlas size differs')
        if not texture.get_editor_property('srgb') or texture.get_editor_property('mip_gen_settings') != unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS:
            raise RuntimeError('atlas color space/mip policy differs')
        if not texture.get_editor_property('never_stream'): raise RuntimeError('atlas residency differs')
        if texture.get_editor_property('filter') != unreal.TextureFilter.TF_BILINEAR or texture.get_editor_property('address_x') != unreal.TextureAddress.TA_WRAP or texture.get_editor_property('address_y') != unreal.TextureAddress.TA_WRAP:
            raise RuntimeError('atlas filtering/addressing differs')
        if material.get_editor_property('parent') != parent or edit.get_material_instance_texture_parameter_value(material, 'FlameAtlas') != texture:
            raise RuntimeError('fire parent/atlas assignment differs')
        expected = dict(Rows=entry['rows'], Columns=entry['columns'], PlaybackRate=entry['fps'] / entry['frames'], PhaseOffset=0,
                        EmissiveStrength=entry['emissive_strength'], InnerScale=entry['uv_scale'][0], InnerBias=entry['uv_bias'][0])
        for key, value in expected.items():
            if abs(edit.get_material_instance_scalar_parameter_value(material, key) - value) > 1e-6:
                raise RuntimeError('fire instance parameter differs: ' + key)
        report['textures'].append(dict(path=entry['texture_path'], dimensions=size, frames=entry['frames'], fps=entry['fps']))
    for chunk in lighting['chunks']:
        component = actors[chunk['name']].static_mesh_component
        for slot, source in enumerate(chunk['materials']):
            binding = bindings.get((chunk['name'], slot)); wanted = binding['material'] if binding else source
            if component.get_material(slot) != unreal.load_asset(wanted): raise RuntimeError('unexpected visible material binding')
            if binding:
                if chunk['nanite'] or component.get_editor_property('cast_shadow'): raise RuntimeError('fire shadow/Nanite admission differs')
                if (chunk['name'], slot) in own: report['bindings'].append(binding)
    if len(report['bindings']) != len(own): raise RuntimeError('fire binding missing')
    report['additional_binding_count'] = len(additional_bindings)
    report['flame_triangles'] = sum(e['triangles'] for e in report['bindings'])
    report['gpu'] = verify_gpu(plan)
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    unreal.log('UR_FIRE_VERIFY_SUCCESS')
    return report


if __name__ == '__main__':
    verify(ROOT / 'data/converted/Unreal/Maps/Unreal/fire-ready/Unreal.fire.json', ROOT / '.local/logs/unreal-fire-verified.json')
