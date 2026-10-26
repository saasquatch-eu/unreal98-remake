"""Source inventory for T3D maps; this does not evaluate CSG or class defaults."""

from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import re

from .t3d import Assignment, Block, Document, T3DError, integer, number, parse_struct, read_polygon


_REFERENCE = re.compile(r"\b([A-Za-z_]\w*)'([^'\r\n]+)'")
_TRANSFORMS = {"Location", "Rotation", "PrePivot", "MainScale", "PostScale",
               "TempScale", "DrawScale", "BasePos", "BaseRot", "SavedPos", "SavedRot"}


def _references_in(value):
    """Ignore reference-shaped text inside double-quoted string literals."""
    index, in_string = 0, False
    while index < len(value):
        char = value[index]
        if in_string and char == "\\":
            index += 2
            continue
        if char == '"':
            in_string = not in_string
        if not in_string:
            match = _REFERENCE.match(value, index)
            if match:
                yield match[1], match[2]
                index = match.end()
                continue
        index += 1


def inspect_document(document: Document, source_name: str, source_bytes: bytes,
                     encoding: str = "utf-8") -> dict:
    """Return a deterministic JSON-compatible inventory with explicit caveats."""
    diagnostics = []
    references = Counter()
    actors = document.actors
    actor_indices = {id(actor): index for index, actor in enumerate(actors)}

    def warn(code, message, actor, line):
        diagnostics.append(dict(code=code, severity="warning", message=message,
                                actor=actor.attribute("Name"),
                                actor_index=actor_indices[id(actor)], line=line))

    def fields(actor):
        return [asdict(prop) for prop in actor.properties]

    def decode(value, line):
        if value.startswith("("):
            specified = parse_struct(value, line)
            if len({v.name for v in specified}) != len(specified):
                raise T3DError("duplicate struct field", line)
            return {v.name: decode(v.value, line) for v in specified}
        if value.startswith("SHEER_"):
            return value
        return number(value, line)

    def validate_transform(value, line, actor, path):
        # Inspect every specified leaf so one malformed component cannot hide another.
        try:
            if value.startswith("("):
                specified = parse_struct(value, line)
                if len({v.name for v in specified}) != len(specified):
                    raise T3DError("duplicate struct field", line)
            else:
                decode(value, line)
                return
        except T3DError as error:
            warn("invalid-transform-number", f"{path}: {error}", actor, line)
            return
        for child in specified:
            validate_transform(child.value, line, actor, f"{path}.{child.name}")

    def visit(block):
        for attribute in block.attributes:
            for kind, path in _references_in(attribute.value):
                references[kind, path] += 1
            if attribute.name == "Texture" and not _REFERENCE.fullmatch(attribute.value):
                references["Texture", attribute.value] += 1
        for entry in block.entries:
            if isinstance(entry, Block):
                visit(entry)
            elif isinstance(entry, Assignment):
                for kind, path in _references_in(entry.value):
                    references[kind, path] += 1

    visit(document.root)
    names = Counter(a.attribute("Name") for a in actors)
    for actor in actors:
        if names[actor.attribute("Name")] > 1:
            warn("duplicate-actor-name", "Actor name occurs more than once", actor, actor.line)
        keys = Counter(p.name for p in actor.properties)
        for key, count in keys.items():
            if count > 1:
                # Preserve repeats in the parser, but never silently choose among them.
                raise T3DError(f"duplicate actor property {key!r}", actor.line)
        for prop in actor.properties:
            if prop.name in _TRANSFORMS or re.fullmatch(r"Key(?:Pos|Rot)\(\d+\)", prop.name):
                validate_transform(prop.value, prop.line, actor, prop.name)

    # Definitions bind to their owning actor's exact exported Model reference.
    # Shared instances therefore resolve without inventing a package name.
    definitions = defaultdict(list)
    models = []
    polygons = []
    for index, actor in enumerate(actors):
        for brush in actor.children("Brush"):
            polylists = brush.children("PolyList")
            if len(polylists) != 1:
                raise T3DError("Brush requires exactly one PolyList", brush.line)
            decoded = [read_polygon(p) for p in polylists[0].children("Polygon")]
            polygons.extend(decoded)
            ref = actor.property("Brush")
            model = dict(name=brush.attribute("Name"), actor=actor.attribute("Name"),
                         actor_index=index, line=brush.line, reference=ref,
                         polygon_count=len(decoded))
            models.append(model)
            match = _REFERENCE.fullmatch(ref or "")
            if (match and match[1] == "Model" and
                    match[2].rsplit(".", 1)[-1] == brush.attribute("Name")):
                definitions[ref].append(model)
            else:
                warn("unbound-model-definition", "Inline brush does not match its Model reference",
                     actor, brush.line)

    brushes, cameras, events = [], [], []
    groups = defaultdict(list)
    classes = Counter(a.attribute("Class") for a in actors)
    for index, actor in enumerate(actors):
        cls, name = actor.attribute("Class"), actor.attribute("Name")
        if cls in {"Brush", "Mover"}:
            ref = actor.property("Brush")
            candidates = definitions.get(ref, [])
            status = "unresolved"
            if len(candidates) == 1:
                status = "inline" if candidates[0]["actor_index"] == index else "shared"
            if status == "unresolved":
                warn("unresolved-model", "Model reference has zero or multiple definitions", actor, actor.line)
            brushes.append(dict(actor_index=index, name=name, actor_class=cls, line=actor.line,
                                csg_operation=actor.property("CsgOper"), model_reference=ref,
                                geometry_status=status, definitions=candidates, properties=fields(actor)))
        if cls == "InterpolationPoint":
            position, location = None, None
            raw = actor.property("Position")
            if raw is not None:
                position = integer(raw, actor.line)
            else:
                warn("omitted-camera-position", "Position is omitted; class default not resolved",
                     actor, actor.line)
            if actor.property("Location") is not None:
                try:
                    location = decode(actor.property("Location"), actor.line)
                except T3DError:
                    pass  # Already diagnosed above; preserve raw properties below.
            point = dict(actor_index=index, name=name, line=actor.line, tag=actor.property("Tag"),
                         position=position, location_specified=location, properties=fields(actor))
            cameras.append(point)
            groups[point["tag"]].append(point)
        if cls in {"LevelInfo", "SpecialEvent", "Trigger", "PlayerStart", "SkyZoneInfo"}:
            events.append(dict(actor_index=index, name=name, actor_class=cls,
                               line=actor.line, properties=fields(actor)))

    camera_groups = []
    for tag, points in groups.items():
        by_position = defaultdict(list)
        for point in points:
            if point["position"] is not None:
                by_position[point["position"]].append(point)
        duplicates = {str(pos): [p["name"] for p in matches]
                      for pos, matches in sorted(by_position.items()) if len(matches) > 1}
        for pos, duplicate_names in duplicates.items():
            first = by_position[int(pos)][0]
            warn("duplicate-camera-position", f"Tag {tag}: Position {pos} shared by {', '.join(duplicate_names)}",
                 actors[first["actor_index"]], first["line"])
        camera_groups.append(dict(tag=tag, point_count=len(points), duplicate_positions=duplicates,
                                  omitted_positions=sum(p["position"] is None for p in points),
                                  explicit_positions=sorted(by_position)))

    operations = Counter(b["csg_operation"] for b in brushes if b["csg_operation"] is not None)
    return dict(
        schema_version=1,
        source=dict(name=source_name, sha256=hashlib.sha256(source_bytes).hexdigest(),
                    byte_count=len(source_bytes), line_count=len(document.source_text.splitlines()),
                    encoding=encoding),
        interpretation=dict(stage="source inspection", geometry="unevaluated source brush polygons",
                            units="source units; no UE5 scale or axis conversion applied",
                            defaults="omitted properties remain unresolved",
                            references="explicit export references only; not a package dependency closure",
                            camera="source order retained; timing, linking, looping and FOV unresolved"),
        counts=dict(actors=len(actors), brush_actors=classes["Brush"], movers=classes["Mover"],
                    inline_models=len(models), source_polygons=len(polygons),
                    source_vertices=sum(len(p.vertices) for p in polygons),
                    polygons_without_explicit_texture=sum(p.block.attribute("Texture") is None for p in polygons),
                    interpolation_points=len(cameras),
                    shared_brush_instances=sum(b["geometry_status"] == "shared" for b in brushes)),
        actor_classes=dict(sorted(classes.items())),
        explicit_csg_operations=dict(sorted(operations.items())),
        models=models, brushes=brushes, camera_points=cameras, camera_groups=camera_groups,
        scene_controls=events,
        references=[dict(kind=kind, path=path, occurrences=count)
                    for (kind, path), count in sorted(references.items())],
        diagnostics=sorted(diagnostics, key=lambda d: (d["line"], d["code"])),
    )
