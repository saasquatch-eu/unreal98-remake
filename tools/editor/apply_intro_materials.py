"""Apply checked private original-color assets to the existing inspection meshes.

Run inside UnrealGoldRemake. No source map or application files are modified.
"""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys
import time

import unreal

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/src'))
from ue1_converter.ue5_prepare import validate_buffers
sys.path.insert(0,str(ROOT/'tools/editor'))
from inspection_lighting import fixed_inspection_exposure


def new_parent(mode,assets):
    folder='/Game/Unreal/Materials/UE5'
    name='Original_'+mode+'_ue5';path=folder+'/'+name
    if unreal.EditorAssetLibrary.does_asset_exist(path):raise RuntimeError('material parent already exists: '+path)
    material=assets.create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
    material.set_editor_property('two_sided','two_sided' in mode)
    additive=mode.startswith('translucent')
    unlit=additive or mode.startswith('modulated') or mode.endswith('unlit')
    blend=unreal.BlendMode.BLEND_ADDITIVE if additive else unreal.BlendMode.BLEND_MODULATE if mode.startswith('modulated') else unreal.BlendMode.BLEND_MASKED if mode.startswith('masked') else unreal.BlendMode.BLEND_OPAQUE
    material.set_editor_property('blend_mode',blend)
    material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    edit=unreal.MaterialEditingLibrary
    if mode=='deferred':
        material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
        opacity=edit.create_material_expression(material,unreal.MaterialExpressionScalarParameter,-300,0)
        opacity.set_editor_property('parameter_name','PreviewOpacity');opacity.set_editor_property('default_value',0.0)
        if not edit.connect_material_property(opacity,'',unreal.MaterialProperty.MP_OPACITY):raise RuntimeError('deferred opacity connection failed')
        edit.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material):raise RuntimeError('deferred parent save failed')
        return material
    sample=edit.create_material_expression(material,unreal.MaterialExpressionTextureSampleParameter2D,-400,0)
    sample.set_editor_property('parameter_name','OriginalColor')
    sample.set_editor_property('texture',unreal.load_asset('/Engine/EngineResources/WhiteSquareTexture'))
    if not edit.connect_material_property(sample,'RGB',unreal.MaterialProperty.MP_EMISSIVE_COLOR if unlit else unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('texture color connection failed')
    if mode.startswith('masked'):
        if not edit.connect_material_property(sample,'A',unreal.MaterialProperty.MP_OPACITY_MASK):raise RuntimeError('mask connection failed')
    if not unlit:
        rough=edit.create_material_expression(material,unreal.MaterialExpressionScalarParameter,-400,250)
        rough.set_editor_property('parameter_name','Roughness');rough.set_editor_property('default_value',0.85)
        if not edit.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS):raise RuntimeError('roughness connection failed')
    edit.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material):raise RuntimeError('parent save failed')
    return material


def create_resources(plan,folder):
    assets=unreal.AssetToolsHelpers.get_asset_tools();textures={}
    for entry in plan['textures']:
        destination=entry['asset_path'];target,name=destination.rsplit('/',1)
        if unreal.EditorAssetLibrary.does_asset_exist(destination):raise RuntimeError('texture already exists: '+destination)
        task=unreal.AssetImportTask();task.filename=str(folder/entry['source_file']);task.destination_path=target
        task.destination_name=name;task.automated=True;task.replace_existing=False;task.save=False
        assets.import_asset_tasks([task])
        if len(task.imported_object_paths)!=1:raise RuntimeError('texture import did not produce one asset')
        texture=unreal.load_asset(task.imported_object_paths[0])
        if not isinstance(texture,unreal.Texture2D) or texture.get_path_name()!=destination+'.'+name:raise RuntimeError('unexpected imported texture path')
        texture.set_editor_property('srgb',True)
        texture.set_editor_property('address_x',unreal.TextureAddress.TA_WRAP);texture.set_editor_property('address_y',unreal.TextureAddress.TA_WRAP)
        if not unreal.EditorAssetLibrary.save_loaded_asset(texture):raise RuntimeError('texture save failed')
        textures[entry['path']]=texture
    parents={};materials=[]
    for entry in plan['materials']:
        if entry['texture'] is None and not entry.get('deferred'):materials.append(unreal.load_asset(entry['path']));continue
        mode=entry['mode']
        if mode not in parents:parents[mode]=new_parent(mode,assets)
        target,name=entry['path'].rsplit('/',1)
        if unreal.EditorAssetLibrary.does_asset_exist(entry['path']):raise RuntimeError('material instance already exists')
        material=assets.create_asset(name,target,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
        unreal.MaterialEditingLibrary.set_material_instance_parent(material,parents[mode])
        if entry['texture']:
            # UE5.8's setter returns false unconditionally; verify the actual value.
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material,'OriginalColor',textures[entry['texture']])
            observed=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material,'OriginalColor')
            if observed!=textures[entry['texture']]:raise RuntimeError('texture assignment readback failed')
        unreal.MaterialEditingLibrary.update_material_instance(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material):raise RuntimeError('material save failed')
        materials.append(material)
    return materials


def apply_meshes(plan,folder,materials):
    editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for entry in plan['meshes']:
        data=json.loads((folder/entry['source_file']).read_text());validate_buffers(data)
        asset=unreal.load_asset(entry['asset_path'])
        if asset.get_num_triangles(0)!=entry['triangle_count']:raise RuntimeError('existing triangle count differs')
        build=editor.get_lod_build_settings(asset,0)
        build.remove_degenerates=False;build.recompute_normals=False;build.recompute_tangents=False
        build.generate_lightmap_u_vs=False;build.use_full_precision_u_vs=True
        editor.set_lod_build_settings(asset,0,build)
        buffers=unreal.GeometryScriptSimpleMeshBuffers()
        buffers.vertices=[unreal.Vector(*v) for v in data['vertices']]
        buffers.normals=[unreal.Vector(*v) for v in data['normals']]
        buffers.uv0=[unreal.Vector2D(*v) for v in data['uv0']]
        buffers.triangles=[unreal.IntVector(*t) for t in data['triangles']]
        mesh=unreal.DynamicMesh();unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(mesh,buffers)
        unreal.GeometryScript_Materials.enable_material_i_ds(mesh)
        for i,material_id in enumerate(data['material_ids']):
            _,valid=unreal.GeometryScript_Materials.set_triangle_material_id(mesh,i,material_id,True)
            if not valid:raise RuntimeError('triangle material ID assignment failed')
        options=unreal.GeometryScriptCopyMeshToAssetOptions()
        options.enable_recompute_normals=False;options.enable_recompute_tangents=False;options.enable_remove_degenerates=False
        options.use_original_vertex_order=True;options.replace_materials=True
        options.new_materials=[materials[i] for i in entry['materials']]
        options.generate_lightmap_u_vs=unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS
        _,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh,asset,options,unreal.GeometryScriptMeshWriteLOD())
        if outcome!=unreal.GeometryScriptOutcomePins.SUCCESS or asset.get_num_triangles(0)!=entry['triangle_count']:raise RuntimeError('mesh update changed triangle count')
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset):raise RuntimeError('mesh save failed')


def run(plan_path):
    plan_path=Path(plan_path);folder=plan_path.parent;plan=json.loads(plan_path.read_text())
    if Path(unreal.Paths.get_project_file_path()).stem!='UnrealGoldRemake':raise RuntimeError('wrong project')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level.is_in_play_in_editor():raise RuntimeError('stop PIE')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():raise RuntimeError('save map before material pass')
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name()!=plan['map_path']+'.'+plan['map_path'].rsplit('/',1)[1]:raise RuntimeError('open the inspection map first')
    for entry in plan['textures']+plan['meshes']:
        if hashlib.sha256((folder/entry['source_file']).read_bytes()).hexdigest()!=entry['source_sha256']:raise RuntimeError('prepared source checksum changed')
    recipe=Path(plan['original_recipe'])
    if hashlib.sha256(recipe.read_bytes()).hexdigest()!=plan['original_recipe_sha256']:raise RuntimeError('original import recipe changed')
    for entry in plan['meshes']:validate_buffers(json.loads((folder/entry['source_file']).read_text()))
    # Do not replace geometry that has diverged from the preceding checkpoint.
    runpy.run_path(str(ROOT/'tools/editor/verify_intro.py'))['verify'](recipe,ROOT/'.local/logs/unreal-ue5-verified.json')
    backup=ROOT/'.local/materials-recovery'/('BeforeMaterials-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    content=ROOT/'ue5/UnrealGoldRemake/Content/Unreal'
    shutil.copytree(content/'Meshes',backup/'Meshes');shutil.copytree(content/'Maps',backup/'Maps')
    materials=create_resources(plan,folder)
    apply_meshes(plan,folder,materials)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    fixed_inspection_exposure(next(a for a in actors if a.get_actor_label()=='Unreal_InspectionExposure_ue5'))
    if not level.save_current_level():raise RuntimeError('level save failed')
    unreal.log('UR_MATERIALS_APPLIED')


if __name__=='__main__':
    run(ROOT/'data/converted/Unreal/Maps/Unreal/materials-ready/Unreal.materials.json')
