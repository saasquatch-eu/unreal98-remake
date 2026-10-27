"""Extract the original compiled BSP as a private, classified geometry bundle."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from .brush_audit import audit_brushes
from .brush_math import dot,from_actor
from .native_bsp import read_world_bsp
from .package61 import Package61,PackageError
from .t3d import number,parse_struct,parse_t3d,read_polygon
from .triangulation import triangulate


INVISIBLE,NOT_SOLID,SEMISOLID,SKY,PORTAL = 1,8,32,128,0x04000000
RENDER_ROLES = {"world","mover"}


def surface_role(flags,zones,sky_zones):
    if not any(zones): return "solid_interior"
    if flags & INVISIBLE: return "invisible_portal" if flags & PORTAL else "invisible"
    if flags & SKY: return "sky_mask"
    if any(z in sky_zones for z in zones if z): return "sky_geometry"
    return "world"


def extract_geometry(source,package_data,source_name,expected_source_sha256,expected_package_sha256):
    audit = audit_brushes(source,package_data,source_name,expected_source_sha256,expected_package_sha256)
    document = parse_t3d(source.decode("utf-8"))
    package = Package61(package_data)
    bsp = read_world_bsp(package)
    stem = Path(source_name).stem
    sky_zones = set()
    zones = []
    for index,zone in enumerate(bsp.zones):
        ref=zone["actor_reference"]
        kind=package.class_name(package.exports[ref-1]) if ref>0 else None
        if kind=="SkyZoneInfo":sky_zones.add(index)
        zones.append(dict(index=index,actor=package.object_path(ref,stem),actor_class=kind,
                          connectivity=zone["connectivity"],visibility=zone["visibility"]))
    points = list(bsp.points)
    surfaces = []
    for index,surface in enumerate(bsp.surfaces):
        if surface["actor_reference"]>0 and package.class_name(package.exports[surface["actor_reference"]-1])=="Mover":
            raise PackageError("Mover unexpectedly baked into static world surface table")
        surfaces.append(dict(index=index,texture=package.object_path(surface["texture_reference"],stem),
                             flags=surface["flags"],normal=bsp.vectors[surface["normal"]],
                             origin=bsp.points[surface["base"]],texture_u=bsp.vectors[surface["u"]],
                             texture_v=bsp.vectors[surface["v"]],pan=surface["pan"],
                             actor=package.object_path(surface["actor_reference"],stem),
                             brush_polygon=surface["brush_polygon"]))
    faces=[]
    max_plane_error=0.0

    def face(indices,surface,role,**metadata):
        local=[points[i] for i in indices]
        try:triangles=triangulate(local,surface["normal"])
        except ValueError as error:raise ValueError(f"{metadata}: {error}") from error
        uv=[]
        for point in local:
            delta=tuple(a-b for a,b in zip(point,surface["origin"],strict=True))
            uv.append([dot(delta,surface[axis])+pan for axis,pan in zip(("texture_u","texture_v"),surface["pan"],strict=True)])
        faces.append(dict(points=indices,triangles=[[indices[k] for k in triangle] for triangle in triangles],
                          omitted_corner_indices=[i for i in range(len(indices)) if not any(i in t for t in triangles)],
                          surface=surface["index"],role=role,uv_texels=uv,**metadata))

    for index in bsp.reachable:
        node=bsp.nodes[index]
        if node["vertex_count"]<3:continue
        indices=[bsp.vertices[i][0] for i in range(node["first_vertex"],node["first_vertex"]+node["vertex_count"])]
        surface=surfaces[node["surface"]]
        for i in indices:
            max_plane_error=max(max_plane_error,abs(dot(node["plane"][:3],points[i])-node["plane"][3]))
        face(indices,surface,surface_role(surface["flags"],node["zones"],sky_zones),
             node=index,zones=node["zones"],node_flags=node["flags"],node_plane=node["plane"],object=f"{stem}_ue5")

    movers=[]
    for actor_index,actor in enumerate(document.actors):
        if actor.attribute("Class")!="Mover":continue
        model=actor.children("Brush")
        if len(model)!=1:raise ValueError("Mover requires one explicit source model in this extraction")
        transform=from_actor(actor)
        name=actor.attribute("Name")
        first_face=len(faces)
        for polygon in model[0].children("PolyList")[0].children("Polygon"):
            p=read_polygon(polygon)
            local=list(p.vertices)
            if transform.reverses_winding:local.reverse()
            start=len(points);points.extend(transform.point(v) for v in local)
            flags=int(polygon.attribute("Flags") or "0") | int(actor.property("PolyFlags") or "0")
            surface=dict(index=len(surfaces),texture=polygon.attribute("Texture"),flags=flags,
                         normal=transform.normal(p.normal),origin=transform.point(p.origin),
                         texture_u=transform.covector(p.texture_u),texture_v=transform.covector(p.texture_v),
                         pan=p.pan,actor=name,brush_polygon=None)
            surfaces.append(surface)
            role="invisible" if flags & INVISIBLE else "mover"
            face(list(range(start,len(points))),surface,role,object=f"{name}_ue5",source_actor_index=actor_index)
        movers.append(dict(name=name,source_actor_index=actor_index,face_range=[first_face,len(faces)],
                           properties=[dict(name=p.name,value=p.value,line=p.line) for p in actor.properties]))
    samples=[]
    for actor_index,actor in enumerate(document.actors):
        if actor.attribute("Class") not in {"InterpolationPoint","SkyZoneInfo","PlayerStart"}:continue
        specified={p.name:number(p.value,p.line) for p in parse_struct(actor.property("Location"),actor.line)}
        position=tuple(specified.get(axis,0.0) for axis in "XYZ")
        samples.append(dict(actor=actor.attribute("Name"),actor_class=actor.attribute("Class"),
                            actor_index=actor_index,position=position,zone=bsp.point_zone(position),
                            rotation=actor.property("Rotation")))
    used={i for f in faces if f["role"] in RENDER_ROLES for t in f["triangles"] for i in t}
    return dict(schema_version=1,stage="original compiled BSP geometry; untextured extraction",
                source=dict(name=source_name,sha256=hashlib.sha256(source).hexdigest()),
                package=dict(version=61,sha256=hashlib.sha256(package_data).hexdigest(),world_model_reference=bsp.model_reference,
                             world_model_name=package.exports[bsp.model_reference-1].name,table_references=bsp.table_references),
                coordinate_space="original UE1 world units; UE5 scale and axis mapping not applied",
                points=points,surfaces=surfaces,faces=faces,zones=zones,movers=movers,zone_samples=samples,
                diagnostics=dict(reachable_nodes=len(bsp.reachable),stored_nodes=len(bsp.nodes),
                                 native_surfaces=len(bsp.surfaces),native_points=len(bsp.points),native_vectors=len(bsp.vectors),
                                 stored_vertex_pool_entries=len(bsp.vertices),unused_invalid_pool_entries=bsp.unused_invalid_pool_entries,
                                 max_native_node_plane_error=max_plane_error,
                                 omitted_triangulation_corners=sum(len(f["omitted_corner_indices"]) for f in faces),
                                 roles=dict(sorted(Counter(f["role"] for f in faces).items())),
                                 render_triangles=sum(len(f["triangles"]) for f in faces if f["role"] in RENDER_ROLES),
                                 bounds=dict(minimum=[min(points[i][axis] for i in used) for axis in range(3)],
                                             maximum=[max(points[i][axis] for i in used) for axis in range(3)])),
                limitations=["Original stored BSP is extracted; the brush sequence is not rebuilt",
                             "Sky masks, invisible portals and sky-zone geometry are retained as separate roles, not opaque walls",
                             "Mover rest geometry uses T3D precision; animation not implemented",
                             "Texture names and texel-space UVs preserved; dimensions and normalized UE5 UVs unresolved",
                             "No game collision, lighting, sky rendering, or UE5 import is established"])


def obj_text(geometry):
    selected=[face for face in geometry["faces"] if face["role"] in RENDER_ROLES]
    used=sorted({i for face in selected for triangle in face["triangles"] for i in triangle})
    remap={i:j+1 for j,i in enumerate(used)}
    lines=["# Private untextured source-unit extraction; no normalized UVs or collision"]
    lines.extend("v "+" ".join(format(v,".9g") for v in geometry["points"][i]) for i in used)
    normal_indices={}
    for face in selected:
        s=face["surface"]
        if s not in normal_indices:
            normal_indices[s]=len(normal_indices)+1
            lines.append("vn "+" ".join(format(v,".9g") for v in geometry["surfaces"][s]["normal"]))
    for face in selected:
        lines.append("o "+re.sub(r"[^A-Za-z0-9_]","_",face["object"]))
        lines.append(f"g surface_{face['surface']}_ue5")
        normal=normal_indices[face["surface"]]
        lines.extend("f "+" ".join(f"{remap[i]}//{normal}" for i in triangle) for triangle in face["triangles"])
    return "\n".join(lines)+"\n"


def write_bundle(geometry,destination):
    destination=Path(destination)
    stem=Path(geometry["source"]["name"]).stem
    if not re.fullmatch(r"[A-Za-z0-9_-]+",stem):raise ValueError("unsafe source filename stem")
    payload=json.dumps(geometry,indent=2,allow_nan=False)+"\n"
    obj=obj_text(geometry)
    # Validate/serialize first; refuse to replace any existing directory or input.
    destination.mkdir()
    with (destination/f"{stem}.geometry.json").open("x",encoding="utf-8") as output:
        output.write(payload)
    with (destination/f"{stem}_ue5.obj").open("x",encoding="utf-8") as output:
        output.write(obj)
