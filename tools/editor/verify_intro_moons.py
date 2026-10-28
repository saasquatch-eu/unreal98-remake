"""Reload source moons and verify exact saved buffers plus real GPU yaw motion."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

import unreal

ROOT = Path(__file__).resolve().parents[2]


def verify_gpu(plan):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before = Counter(a.get_path_name() for a in actors.get_all_level_actors()); world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    reports = []
    for entry in plan['meshes']:
        preview = capture = target = None
        try:
            preview = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(), transient=True)
            mesh = unreal.load_asset(entry['asset_path']); preview.static_mesh_component.set_static_mesh(mesh)
            material = unreal.MaterialLibrary.create_dynamic_material_instance(world, unreal.load_asset(entry['material_path']))
            material.set_scalar_parameter_value('FollowCamera', 0); material.set_scalar_parameter_value('PlaybackRate', 0); material.set_scalar_parameter_value('SkyBrightness', 1)
            preview.static_mesh_component.set_material(0, material)
            bounds = mesh.get_bounding_box(); center = [(getattr(bounds.min, k) + getattr(bounds.max, k)) / 2 for k in 'xyz']
            radius = math.sqrt(sum((getattr(bounds.max, k) - v) ** 2 for k, v in zip('xyz', center)))
            capture = actors.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(center[0] + radius * 4, center[1], center[2]), unreal.Rotator(yaw=180), transient=True)
            component = capture.get_component_by_class(unreal.SceneCaptureComponent2D)
            component.set_editor_property('capture_every_frame', False); component.set_editor_property('capture_on_movement', False)
            component.set_editor_property('primitive_render_mode', unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
            component.show_only_actor_components(preview); component.set_editor_property('fov_angle', 40)
            component.set_editor_property('capture_source', unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
            component.set_editor_property('show_flag_settings', [unreal.EngineShowFlagsSetting(show_flag_name=n, enabled=False) for n in
                ('Fog', 'VolumetricFog', 'Atmosphere', 'PostProcessing', 'TemporalAA', 'AntiAliasing', 'MotionBlur')])
            target = unreal.RenderingLibrary.create_render_target2d(world, 256, 256, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            component.set_editor_property('texture_target', target); hashes = []; counts = []
            for seconds in (0, 3):
                material.set_scalar_parameter_value('PreviewTime', seconds); unreal.RenderingLibrary.clear_render_target2d(world, target, unreal.LinearColor(0, 0, 0, 1)); component.capture_scene()
                colors = unreal.RenderingLibrary.read_render_target_raw(world, target, False)
                if len(colors) != 256 * 256: raise RuntimeError('moon GPU readback dimensions differ')
                counts.append(sum(max(c.r, c.g, c.b) > 0.002 for c in colors)); hashes.append(hashlib.sha256(b''.join(struct.pack('<fff', c.r, c.g, c.b) for c in colors)).hexdigest())
                unreal.RenderingLibrary.export_render_target(world, target, str(ROOT / '.local'), entry['source_name'] + '-gpu-' + str(seconds) + '.png')
            expected = 2 if entry['yaw_turns_per_second'] else 1
            if min(counts) <= 10 or len(set(hashes)) != expected: raise RuntimeError('moon GPU rotation/static result differs: ' + entry['name'])
            reports.append(dict(name=entry['name'], sample_seconds=[0, 3], expected_distinct=expected, distinct=len(set(hashes)), nonblack_pixels=counts, hashes=hashes))
        finally:
            if capture and not actors.destroy_actor(capture): raise RuntimeError('capture cleanup failed')
            if preview and not actors.destroy_actor(preview): raise RuntimeError('preview cleanup failed')
            if target: unreal.RenderingLibrary.release_render_target2d(target)
    if Counter(a.get_path_name() for a in actors.get_all_level_actors()) != before: raise RuntimeError('GPU diagnostic actors leaked')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() and not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise RuntimeError('diagnostic cleanup save failed')
    return reports


def verify(plan_path, report_path):
    plan_path = Path(plan_path); helper = runpy.run_path(str(ROOT / 'tools/editor/apply_intro_moons.py')); plan = helper['checked_plan'](plan_path)
    baseline = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_sky.py'))['verify'](plan['sky_plan'], ROOT / '.local/logs/unreal-sky-verified.json')
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    stage = runpy.run_path(str(ROOT / 'tools/editor/verify_intro_materials.py')); record = stage['record']; edit = unreal.MaterialEditingLibrary
    parent = unreal.load_asset(helper['PARENT']); smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if parent.get_editor_property('is_sky') or parent.get_editor_property('blend_mode') != unreal.BlendMode.BLEND_OPAQUE or parent.get_editor_property('shading_model') != unreal.MaterialShadingModel.MSM_UNLIT:
        raise RuntimeError('moon parent shading differs')
    root = edit.get_material_property_input_node(parent, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    inputs = edit.get_inputs_for_material_expression(parent, root)
    if not isinstance(root, unreal.MaterialExpressionAdd) or not any(isinstance(v, unreal.MaterialExpressionRotateAboutAxis) for v in inputs): raise RuntimeError('moon rotation graph missing')
    pending = [root]; visited = set(); clock = False; parameters = set()
    while pending:
        expression = pending.pop()
        if not expression or expression.get_path_name() in visited: continue
        visited.add(expression.get_path_name()); clock |= isinstance(expression, unreal.MaterialExpressionTime)
        if isinstance(expression, (unreal.MaterialExpressionScalarParameter, unreal.MaterialExpressionVectorParameter)): parameters.add(str(expression.get_editor_property('parameter_name')))
        pending.extend(edit.get_inputs_for_material_expression(parent, expression))
    if not clock or not {'FollowCamera', 'RotationPivot', 'PlaybackRate', 'PreviewTime', 'YawTurnsPerSecond'} <= parameters: raise RuntimeError('moon clock/camera controls missing')
    for texture in plan['textures']:
        asset = unreal.load_asset(texture['asset_path'])
        if (asset.blueprint_get_size_x(), asset.blueprint_get_size_y()) != (texture['width'], texture['height']) or not asset.get_editor_property('srgb'): raise RuntimeError('moon image dimensions/color space differ')
    for entry in plan['meshes']:
        actor = actors[entry['name']]; c = actor.static_mesh_component; mesh = unreal.load_asset(entry['asset_path'])
        if c.static_mesh != mesh or not c.is_visible() or c.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION: raise RuntimeError('moon mesh/visibility/collision differs')
        if any(c.get_editor_property(k) for k in ('cast_shadow', 'affect_distance_field_lighting', 'visible_in_real_time_sky_captures', 'visible_in_reflection_captures', 'visible_in_ray_tracing')): raise RuntimeError('moon lighting participation differs')
        pos = actor.get_actor_location(); rot = actor.get_actor_rotation(); scale = actor.get_actor_scale3d()
        if any(abs(v) > 1e-6 for v in (pos.x, pos.y, pos.z, rot.pitch, rot.yaw, rot.roll)) or any(v != 1 for v in (scale.x, scale.y, scale.z)): raise RuntimeError('moon actor transform differs')
        if mesh.get_num_triangles(0) != entry['triangle_count'] or smes.get_nanite_settings(mesh).enabled: raise RuntimeError('moon triangle count/Nanite differs')
        build = smes.get_lod_build_settings(mesh, 0)
        if not build.use_full_precision_u_vs or build.distance_field_resolution_scale or build.max_lumen_mesh_cards: raise RuntimeError('moon build settings differ')
        data = json.loads((plan_path.parent / entry['source_file']).read_text())
        expected = Counter(record([data['vertices'][i] for i in tri], [data['uv0'][i] for i in tri], 0) for tri in data['triangles'])
        options = unreal.GeometryScriptCopyMeshFromAssetOptions(); options.apply_build_settings = False
        lod = unreal.GeometryScriptMeshReadLOD(); lod.lod_type = unreal.GeometryScriptLODType.SOURCE_MODEL
        dynamic, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(mesh, unreal.DynamicMesh(), options, lod)
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS: raise RuntimeError('moon mesh readback failed')
        actual = Counter()
        for i in range(dynamic.get_triangle_count()):
            valid, a, b, d = unreal.GeometryScript_MeshQueries.get_triangle_positions(dynamic, i); u, v, w, uv_valid = unreal.GeometryScript_MeshQueries.get_triangle_u_vs(dynamic, 0, i)
            if not valid or not uv_valid: raise RuntimeError('moon attributes missing')
            actual[record([(p.x, p.y, p.z) for p in (a, b, d)], [(p.x, p.y) for p in (u, v, w)], 0)] += 1
        if actual != expected: raise RuntimeError('saved moon positions/winding/UVs differ')
        material = unreal.load_asset(entry['material_path'])
        if c.get_material(0) != material or material.parent != parent: raise RuntimeError('moon material binding differs')
        texture = unreal.load_asset(next(t['asset_path'] for t in plan['textures'] if t['path'] == entry['texture']))
        if edit.get_material_instance_texture_parameter_value(material, 'OriginalColor') != texture: raise RuntimeError('moon texture binding differs')
        for name, value in dict(SkyBrightness=plan['preview_brightness'], FollowCamera=1, PlaybackRate=1, PreviewTime=0, YawTurnsPerSecond=entry['yaw_turns_per_second']).items():
            if abs(edit.get_material_instance_scalar_parameter_value(material, name) - value) > 1e-7: raise RuntimeError('moon parameter differs: ' + name)
        pivot = edit.get_material_instance_vector_parameter_value(material, 'RotationPivot')
        if any(abs(a - b) > 0.02 for a, b in zip((pivot.r, pivot.g, pivot.b), entry['rotation_pivot'])): raise RuntimeError('moon rotation pivot differs')
    report = dict(status='success', plan_sha256=helper['digest'](plan_path), world_triangles=baseline['world_triangles'], mover_triangles=baseline['mover_triangles'],
                  sky_triangles=baseline['sky_triangles'], moon_triangles=sum(e['triangle_count'] for e in plan['meshes']), gpu=verify_gpu(plan))
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n'); unreal.log('UR_MOONS_VERIFY_SUCCESS')
    return report


if __name__ == '__main__':
    verify(ROOT / 'data/converted/Unreal/Maps/Unreal/moons-ready/Unreal.moons.json', ROOT / '.local/logs/unreal-moons-verified.json')
