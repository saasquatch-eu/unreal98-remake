"""Prepare source-coordinate mesh buffers for UE5 Geometry Scripting."""

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

from .t3d import number,parse_struct


def validate_buffers(data):
    if not {"vertices","normals","uv0","triangles"}<=data.keys():
        raise ValueError("vertices, normals, UV0 and triangles are mandatory before an Unreal build")
    vertices,normals,uvs,triangles=(data[k] for k in ("vertices","normals","uv0","triangles"))
    if not vertices or len(normals)!=len(vertices) or len(uvs)!=len(vertices):
        raise ValueError("one normal and UV0 coordinate are required per vertex")
    if any(len(v)!=3 for v in vertices+normals) or any(len(v)!=2 for v in uvs):
        raise ValueError("invalid vector/UV dimensions")
    if not all(math.isfinite(v) for row in vertices+normals+uvs for v in row):
        raise ValueError("non-finite mesh buffers")
    if any(sum(v*v for v in n)==0 for n in normals):raise ValueError("zero mesh normal")
    for triangle in triangles:
        if len(triangle)!=3 or len(set(triangle))!=3 or any(not isinstance(i,int) or not 0<=i<len(vertices) for i in triangle):
            raise ValueError("invalid triangle indices")
        a,b,c=(uvs[i] for i in triangle)
        if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])==0:
            raise ValueError("diagnostic UV triangle is degenerate")
    if not triangles:raise ValueError("mesh has no triangles")


def prepare_import(geometry_path,destination,*,centimeters_per_source_unit=1.0):
    geometry_path=Path(geometry_path)
    destination=Path(destination)
    scale=centimeters_per_source_unit
    if not math.isfinite(scale) or scale<=0:raise ValueError("scale must be finite and positive")
    raw=geometry_path.read_bytes();geometry=json.loads(raw)
    if geometry.get("schema_version")!=1:raise ValueError("unsupported geometry schema")
    stem=Path(geometry["source"]["name"]).stem
    if not re.fullmatch(r"[A-Za-z0-9_]+",stem):raise ValueError("unsafe map stem")
    groups=defaultdict(list)
    for face in geometry["faces"]:
        if face["role"] in {"world","mover"}:groups[face["object"]].append(face)
    pivots={f"{stem}_ue5":(0.0,0.0,0.0)}
    for mover in geometry["movers"]:
        prop=next(p for p in mover["properties"] if p["name"]=="Location")
        fields={p.name:number(p.value,p.line) for p in parse_struct(prop["value"],prop["line"])}
        pivots[mover["name"]+"_ue5"]=tuple(fields.get(k,0.0) for k in "XYZ")
    files={};meshes=[]
    for name,faces in groups.items():
        if not re.fullmatch(r"[A-Za-z0-9_]+_ue5",name) or name not in pivots:
            raise ValueError("unsafe or unknown mesh object name")
        pivot=pivots[name]
        local=[];normals=[];triangles=[];uvs=[]
        for face in faces:
            normal=geometry["surfaces"][face["surface"]]["normal"]
            for tri in face["triangles"]:
                start=len(local)
                # Disconnected triangle corners avoid imposing manifold/welding assumptions.
                for i in tri:
                    local.append(tuple((v-p)*scale for v,p in zip(geometry["points"][i],pivot,strict=True)))
                    normals.append(normal)
                # UE5 StaticMesh normals use (P2-P0) cross (P1-P0).
                # Source triangulation uses the opposite cross product.
                triangles.append([start,start+2,start+1])
                # Required by UE5 StaticMesh lightmap validation, even for a clay scene.
                # This is a diagnostic basis, not reconstructed original material UVs.
                uvs.extend([(0.0,0.0),(1.0,0.0),(0.0,1.0)])
        if not local or not all(math.isfinite(v) for p in local+normals for v in p):
            raise ValueError("empty or non-finite mesh data")
        filename=name+".mesh.json"
        data=dict(vertices=local,normals=normals,uv0=uvs,triangles=triangles)
        validate_buffers(data)
        payload=json.dumps(data,allow_nan=False)+"\n"
        files[filename]=payload
        meshes.append(dict(name=name,asset_path=f"/Game/Unreal/Meshes/{name}",source_file=filename,
                           source_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                           actor_location=[v*scale for v in pivot],
                           expected_bounds=dict(minimum=[min(v[k] for v in local) for k in range(3)],
                                                maximum=[max(v[k] for v in local) for k in range(3)]),
                           triangle_count=sum(len(f["triangles"]) for f in faces),
                           role="world" if name==stem+"_ue5" else "mover"))
    camera=next(s for s in geometry["zone_samples"] if s["actor_class"]=="InterpolationPoint")
    rotation={p.name:int(p.value) for p in parse_struct(camera["rotation"] or "()",1)}
    plan=dict(schema_version=1,project_name="UnrealGoldRemake",map_path=f"/Game/Unreal/Maps/{stem}_ue5",
              geometry_file=str(geometry_path.resolve()),geometry_sha256=hashlib.sha256(raw).hexdigest(),
              source=geometry["source"],package=geometry["package"],
              centimeters_per_source_unit=scale,scale_status="coordinate-preserving inspection scale; physical gameplay scale unresolved",
              importer_profile="UE5.8 GeometryScript direct buffers; identity axes; reversed triangle winding; no OBJ conversion",meshes=meshes,
              uv0_mode="per-triangle diagnostic basis; original texture UVs are not reconstructed",
              camera=dict(name=stem+"_Camera_ue5",location=[v*scale for v in camera["position"]],
                          rotation={k.lower():((rotation.get(k,0)>>2)&16383)*360/16384 for k in ("Pitch","Yaw","Roll")},
                          diagnostic_fov=75.0),
              limitations=["Untextured inspection scene; original UV/material mapping remains in geometry JSON",
                           "Collision intentionally disabled; sky masks and portals not reconstructed",
                           "Mover rest meshes are separate; native rotation is baked, animation remains unresolved"])
    payload=json.dumps(plan,indent=2,allow_nan=False)+"\n"
    destination.mkdir()
    for filename,content in files.items():
        with (destination/filename).open("x",encoding="utf-8") as output:output.write(content)
    with (destination/f"{stem}.import.json").open("x",encoding="utf-8") as output:output.write(payload)
    return plan


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry",type=Path)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--centimeters-per-source-unit",type=float,default=1.0)
    args=parser.parse_args()
    prepare_import(args.geometry,args.output_dir,centimeters_per_source_unit=args.centimeters_per_source_unit)
