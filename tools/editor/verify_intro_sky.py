"""Reload the complete castle and check source-sky buffers, bindings and motion."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import struct

import unreal

ROOT = Path(__file__).resolve().parents[2]


def verify_gpu(plan):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(); reports = []
    for path in sorted({e['material_path'] for e in plan['meshes']}):
        entry = next(e for e in plan['meshes'] if e['material_path'] == path)
        texture = next(t for t in plan['textures'] if t['path'] == entry['texture'])
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, unreal.load_asset(path)); mid.set_scalar_parameter_value('FollowCamera', 0)
        mid.set_vector_parameter_value('PanRate', unreal.LinearColor(0, 0, 0, 0))
        hashes = []; counts = []
        for phase in ([0, 0.37] if entry['mode'] == 'sky_cloud' else [0]):
            mid.set_vector_parameter_value('PreviewOffset', unreal.LinearColor(phase, phase, 0, 0))
            target = unreal.RenderingLibrary.create_render_target2d(world, texture['width'], texture['height'], unreal.TextureRenderTargetFormat.RTF_RGBA8)
            try:
                unreal.RenderingLibrary.clear_render_target2d(world, target, unreal.LinearColor(0, 0, 0, 1)); unreal.RenderingLibrary.draw_material_to_render_target(world, target, mid)
                colors = unreal.RenderingLibrary.read_render_target_raw(world, target, False)
                if len(colors) != texture['width'] * texture['height']: raise RuntimeError('sky GPU dimensions differ')
                counts.append(sum(max(c.r, c.g, c.b) > 0.002 for c in colors))
                hashes.append(hashlib.sha256(b''.join(struct.pack('<fff', c.r, c.g, c.b) for c in colors)).hexdigest())
                unreal.RenderingLibrary.export_render_target(world, target, str(ROOT / '.local'), texture['path'].split('.')[-1] + '-sky-' + str(phase) + '.png')
            finally: unreal.RenderingLibrary.release_render_target2d(target)
        if min(counts) <= 10 or len(set(hashes)) != len(hashes): raise RuntimeError('sky image blank or cloud sampling static')
        reports.append(dict(material=path, nonblack_pixels=counts, hashes=hashes))
    return reports


def verify(plan_path, report_path):
    plan_path = Path(plan_path); helper = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_sky.py')); plan = helper['checked_plan'](plan_path)
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_mood.py'))['verify'](
        ROOT / 'tools/presets/Unreal_Gloom_ue5.json', ROOT / '.local/logs/unreal-mood-verified.json')
    stage = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_materials.py')); record = stage['record']
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    edit = unreal.MaterialEditingLibrary; smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for texture in plan['textures']:
        asset = unreal.load_asset(texture['asset_path'])
        if (asset.blueprint_get_size_x(), asset.blueprint_get_size_y()) != (texture['width'], texture['height']) or not asset.get_editor_property('srgb'):
            raise RuntimeError('sky image dimensions/color space differ')
        if any(asset.get_editor_property(k) != unreal.TextureAddress.TA_WRAP for k in ('address_x', 'address_y')): raise RuntimeError('sky texture addressing differs')
    for entry in plan['meshes']:
        actor = actors[entry['name']]; c = actor.static_mesh_component; asset = unreal.load_asset(entry['asset_path'])
        if c.static_mesh != asset or not c.is_visible() or c.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION: raise RuntimeError('sky actor mesh/visibility/collision differs')
        if any(c.get_editor_property(k) for k in ('cast_shadow', 'affect_distance_field_lighting', 'visible_in_real_time_sky_captures', 'visible_in_reflection_captures', 'visible_in_ray_tracing')):
            raise RuntimeError('source sky participates in lighting/capture')
        pos = actor.get_actor_location(); rot = actor.get_actor_rotation(); scale = actor.get_actor_scale3d()
        if any(abs(v) > 1e-6 for v in (pos.x, pos.y, pos.z, rot.pitch, rot.yaw, rot.roll)) or any(abs(v - 1) > 1e-6 for v in (scale.x, scale.y, scale.z)):
            raise RuntimeError('sky actor transform differs')
        if asset.get_num_triangles(0) != entry['triangle_count'] or smes.get_nanite_settings(asset).enabled: raise RuntimeError('sky count/Nanite differs')
        build = smes.get_lod_build_settings(asset, 0)
        if not build.use_full_precision_u_vs or build.distance_field_resolution_scale != 0 or build.max_lumen_mesh_cards != 0: raise RuntimeError('sky build settings differ')
        data = json.loads((plan_path.parent / entry['source_file']).read_text())
        expected = Counter(record([data['vertices'][i] for i in tri], [data['uv0'][i] for i in tri], 0) for tri in data['triangles'])
        options = unreal.GeometryScriptCopyMeshFromAssetOptions(); options.apply_build_settings = False
        lod = unreal.GeometryScriptMeshReadLOD(); lod.lod_type = unreal.GeometryScriptLODType.SOURCE_MODEL
        mesh, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(asset, unreal.DynamicMesh(), options, lod)
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS: raise RuntimeError('sky readback failed')
        actual = Counter()
        for i in range(mesh.get_triangle_count()):
            valid, a, b, d = unreal.GeometryScript_MeshQueries.get_triangle_positions(mesh, i)
            u, v, w, uv_valid = unreal.GeometryScript_MeshQueries.get_triangle_u_vs(mesh, 0, i)
            if not valid or not uv_valid: raise RuntimeError('sky corner attribute missing')
            actual[record([(p.x, p.y, p.z) for p in (a, b, d)], [(p.x, p.y) for p in (u, v, w)], 0)] += 1
        if actual != expected: raise RuntimeError('sky source positions/winding/UVs differ')
        material = unreal.load_asset(entry['material_path']); parent = unreal.load_asset(helper['PARENTS'][entry['mode']])
        if c.get_material(0) != material or material.parent != parent: raise RuntimeError('sky material binding differs')
        if parent.get_editor_property('is_sky') or not parent.get_editor_property('two_sided') or parent.get_editor_property('shading_model') != unreal.MaterialShadingModel.MSM_UNLIT:
            raise RuntimeError('sky material shading differs')
        far_backdrop = isinstance(edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET), unreal.MaterialExpressionAdd)
        blend = unreal.BlendMode.BLEND_ADDITIVE if entry['mode'] == 'sky_cloud' else unreal.BlendMode.BLEND_TRANSLUCENT if far_backdrop else unreal.BlendMode.BLEND_OPAQUE
        if far_backdrop:
            if parent.get_editor_property('use_translucency_vertex_fog') or c.get_editor_property('translucency_sort_priority') != (-99 if entry['mode'] == 'sky_cloud' else -100): raise RuntimeError('sky background compositing differs')
            if entry['mode'] != 'sky_cloud':
                opacity = edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_OPACITY)
                if not isinstance(opacity, unreal.MaterialExpressionConstant) or opacity.get_editor_property('r') != 1: raise RuntimeError('star backdrop opacity differs')
        if parent.get_editor_property('blend_mode') != blend: raise RuntimeError('sky blend differs')
        texture = unreal.load_asset(next(t['asset_path'] for t in plan['textures'] if t['path'] == entry['texture']))
        if edit.get_material_instance_texture_parameter_value(material, 'OriginalColor') != texture: raise RuntimeError('sky source texture differs')
        for name in ('SkyBrightness', 'FollowCamera'):
            if edit.get_material_instance_scalar_parameter_value(material, name) != 1: raise RuntimeError('sky scalar differs: ' + name)
        if entry['mode'] == 'sky_cloud':
            rate = edit.get_material_instance_vector_parameter_value(material, 'PanRate'); phase = edit.get_material_instance_vector_parameter_value(material, 'PreviewOffset')
            if any(abs(v - e) > 1e-6 for v, e in zip((rate.r, rate.g), entry['pan_uv_per_second'])) or any(v != 0 for v in (phase.r, phase.g, phase.b, phase.a)):
                raise RuntimeError('cloud motion differs')
        root = edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        if isinstance(root, unreal.MaterialExpressionAdd):
            # Explicit far-backdrop profile; canonical sky buffers and actor transforms stay exact.
            parts = edit.get_inputs_for_material_expression(parent, root)
            if len(parts) != 2 or not isinstance(parts[1], unreal.MaterialExpressionMultiply): raise RuntimeError('far-backdrop output differs')
            expansion = edit.get_inputs_for_material_expression(parent, parts[1])
            if len(expansion) != 2 or not isinstance(expansion[0], unreal.MaterialExpressionSubtract) or not isinstance(expansion[1], unreal.MaterialExpressionMultiply): raise RuntimeError('far-backdrop expansion differs')
            positions = edit.get_inputs_for_material_expression(parent, expansion[0]); amount = edit.get_inputs_for_material_expression(parent, expansion[1])
            if len(positions) != 2 or not isinstance(positions[0], unreal.MaterialExpressionWorldPosition) or positions[0].get_editor_property('world_position_shader_offset') != unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS or not isinstance(positions[1], unreal.MaterialExpressionActorPositionWS): raise RuntimeError('far-backdrop source coordinates differ')
            if len(amount) != 2 or not isinstance(amount[0], unreal.MaterialExpressionSubtract) or not isinstance(amount[1], unreal.MaterialExpressionScalarParameter) or str(amount[1].get_editor_property('parameter_name')) != 'FollowCamera': raise RuntimeError('far-backdrop follow control differs')
            scale = edit.get_inputs_for_material_expression(parent, amount[0])
            if len(scale) != 2 or not isinstance(scale[0], unreal.MaterialExpressionScalarParameter) or str(scale[0].get_editor_property('parameter_name')) != 'BackdropDistanceScale' or scale[0].get_editor_property('default_value') != 64 or not isinstance(scale[1], unreal.MaterialExpressionConstant) or scale[1].get_editor_property('r') != 1: raise RuntimeError('far-backdrop scale differs')
            if edit.get_material_instance_scalar_parameter_value(material, 'BackdropDistanceScale') != 64: raise RuntimeError('sky instance overrides far-backdrop scale')
            if entry['mode'] == 'sky_cloud':
                projections = []
                for expression in edit.get_material_expressions(parent):
                    if not isinstance(expression, unreal.MaterialExpressionDivide): continue
                    terms = edit.get_inputs_for_material_expression(parent, expression)
                    if len(terms) != 2 or not isinstance(terms[1], unreal.MaterialExpressionMultiply): continue
                    denominator = edit.get_inputs_for_material_expression(parent, terms[1])
                    if len(denominator) == 2 and isinstance(denominator[0], unreal.MaterialExpressionConstant) and denominator[0].get_editor_property('r') == 128 and isinstance(denominator[1], unreal.MaterialExpressionAdd): projections.append(denominator[1])
                if len(projections) != 1: raise RuntimeError('cloud projection compensation missing')
                effective = edit.get_inputs_for_material_expression(parent, projections[0])
                if len(effective) != 2 or not isinstance(effective[0], unreal.MaterialExpressionConstant) or effective[0].get_editor_property('r') != 1 or effective[1] != expansion[1]: raise RuntimeError('cloud projection compensation differs')
            root = parts[0]
        if not isinstance(root, unreal.MaterialExpressionMultiply): raise RuntimeError('camera-centering graph missing')
        inputs = edit.get_inputs_for_material_expression(parent, root)
        if len(inputs) != 2 or not isinstance(inputs[0], unreal.MaterialExpressionSubtract) or not isinstance(inputs[1], unreal.MaterialExpressionScalarParameter) or str(inputs[1].get_editor_property('parameter_name')) != 'FollowCamera':
            raise RuntimeError('camera-centering controls differ')
        positions = edit.get_inputs_for_material_expression(parent, inputs[0])
        if len(positions) != 2 or not isinstance(positions[0], unreal.MaterialExpressionCameraPositionWS) or not isinstance(positions[1], unreal.MaterialExpressionActorPositionWS):
            raise RuntimeError('camera-centering positions differ')
        if entry['mode'] == 'sky_cloud':
            pending = [edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_EMISSIVE_COLOR)]; visited = set(); clock = False; pan = False
            while pending:
                expression = pending.pop()
                if not expression or expression.get_path_name() in visited: continue
                visited.add(expression.get_path_name()); clock |= isinstance(expression, unreal.MaterialExpressionTime)
                pan |= isinstance(expression, unreal.MaterialExpressionVectorParameter) and str(expression.get_editor_property('parameter_name')) == 'PanRate'
                pending.extend(edit.get_inputs_for_material_expression(parent, expression))
            if not clock or not pan: raise RuntimeError('cloud runtime clock/rate graph missing')
    report = dict(status='success', plan_sha256=helper['digest'](plan_path), sky_triangles=sum(e['triangle_count'] for e in plan['meshes']),
                  world_triangles=baseline['world_triangles'], mover_triangles=baseline['mover_triangles'], gpu=verify_gpu(plan))
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_SKY_VERIFY_SUCCESS')
    return report


if __name__ == '__main__':
    verify(ROOT / 'data/converted/Unreal/Maps/Unreal/sky-ready/Unreal.sky.json', ROOT / '.local/logs/unreal-sky-verified.json')
