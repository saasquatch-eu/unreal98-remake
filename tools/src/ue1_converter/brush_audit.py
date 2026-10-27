"""Bind source numeric corrections to binary evidence and audit brush coordinates."""

import hashlib
import math

from .brush_math import from_actor
from .inspection import inspect_document
from .package61 import Package61
from .t3d import T3DError, number, parse_struct, parse_t3d, read_polygon


def audit_brushes(source: bytes, package: bytes, source_name: str,
                 expected_source_sha256: str, expected_package_sha256: str) -> dict:
    source_hash = hashlib.sha256(source).hexdigest()
    package_hash = hashlib.sha256(package).hexdigest()
    if source_hash != expected_source_sha256 or package_hash != expected_package_sha256:
        raise ValueError("source/package checksum does not match the recorded export provenance")
    document = parse_t3d(source.decode("utf-8"))
    inventory = inspect_document(document, source_name, source)
    binary = Package61(package)
    evidence, brushes = [], []
    for item in inventory["brushes"]:
        actor = document.actors[item["actor_index"]]
        overrides = {}
        pivots = [p for p in actor.properties if p.name == "PrePivot"]
        if pivots:
            for component in parse_struct(pivots[0].value, pivots[0].line):
                try:
                    number(component.value, component.line)
                except T3DError:
                    if component.name not in "XYZ" or len(component.name) != 1:
                        raise ValueError("unsupported pivot field")
                    proof = binary.vector_property(item["name"], item["actor_class"], "PrePivot")
                    axis = "XYZ".index(component.name)
                    overrides[component.name] = proof.values[axis]
                    evidence.append(dict(actor_index=item["actor_index"], actor=item["name"],
                                         line=component.line, property="PrePivot", component=component.name,
                                         original_token=component.value, value=proof.values[axis],
                                         binary_export_index=proof.export_index,
                                         binary_byte_offset=proof.property_offset + 4 * axis,
                                         little_endian_float32_hex=proof.raw[4*axis:4*axis+4].hex()))
        transform = from_actor(actor, overrides)
        if len(item["definitions"]) != 1:
            raise ValueError("brush model does not have one proven definition")
        owner = document.actors[item["definitions"][0]["actor_index"]]
        matching = [b for b in owner.children("Brush") if b.attribute("Name") == item["definitions"][0]["name"]]
        if len(matching) != 1:
            raise ValueError("ambiguous inline brush definition")
        polygons = [read_polygon(p) for p in matching[0].children("PolyList")[0].children("Polygon")]
        points = [transform.point(v) for p in polygons for v in p.vertices]
        if not points or not all(math.isfinite(c) for p in points for c in p):
            raise ValueError("empty or non-finite transformed brush")
        operation = actor.property("CsgOper")
        if item["actor_class"] == "Mover":
            category = "mover; kept separate from static CSG"
        elif operation is None:
            category = "active brush by published default; excluded from static CSG"
        else:
            category = "ordered static brush; BSP flags still require evaluation"
        brushes.append(dict(actor_index=item["actor_index"], name=item["name"],
                            actor_class=item["actor_class"], category=category,
                            explicit_csg_operation=operation, poly_flags=actor.property("PolyFlags"),
                            model_reference=item["model_reference"], polygon_count=len(polygons),
                            reverses_winding=transform.reverses_winding,
                            source_space_bounds=dict(minimum=[min(p[i] for p in points) for i in range(3)],
                                                     maximum=[max(p[i] for p in points) for i in range(3)])))
    return dict(schema_version=1, stage="source coordinate audit; no evaluated BSP or mesh",
                source=dict(name=source_name, sha256=source_hash),
                package=dict(version=61, sha256=package_hash),
                reference_commit="2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6",
                limitations=["No original-runtime oracle was run",
                             "Zero shear only; nonzero shear fails explicitly",
                             "Double precision with the published legacy angle grid; not bit-exact engine float math",
                             "Uncorrected values retain T3D decimal precision",
                             "PolyFlags, solidity, portals, sky zones, Movers and camera playback are not reconstructed"],
                numeric_evidence=evidence,
                counts=dict(brush_instances=len(brushes), corrected_components=len(evidence),
                            mirrored_instances=sum(b["reverses_winding"] for b in brushes),
                            static_operation_instances=sum(b["actor_class"] == "Brush" and b["explicit_csg_operation"] is not None for b in brushes),
                            movers=sum(b["actor_class"] == "Mover" for b in brushes)),
                brushes=brushes)
