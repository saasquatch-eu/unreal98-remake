"""Read the geometry-bearing legacy v61 BSP tables, without executing the game.

Wire fields are checked against the published OldUnreal UnModel/UnObj definitions
and cross-table bounds. This does not deserialize lighting, hulls or gameplay.
"""

from dataclasses import dataclass
import math

from .package61 import Package61, PackageError, Reader


def _finite(values):
    if not all(math.isfinite(v) for v in values):
        raise PackageError("non-finite native geometry")
    return values


def _native(package, reference, kind):
    if not 0 < reference <= len(package.exports):
        raise PackageError("native geometry requires a local export reference")
    export = package.exports[reference - 1]
    if package.class_name(export) != kind or export.flags & 0x02000000:
        raise PackageError(f"expected plain native {kind} export")
    reader = Reader(package.data, export.offset, export.offset + export.size)
    if package.name(reader.compact()) != "None":
        raise PackageError("native geometry with tagged properties is unsupported")
    return reader


def _array(package, reference, kind, minimum_record_size):
    reader = _native(package, reference, kind)
    count, capacity = reader.unpack("ii")
    if not 0 <= count <= capacity or count > (reader.end - reader.offset) // minimum_record_size:
        raise PackageError("invalid native array count")
    return reader, count


def _end(reader):
    if reader.offset != reader.end:
        raise PackageError("native table has unexplained trailing bytes")


def _string(reader):
    count = reader.compact()
    if count < 1:
        raise PackageError("expected legacy ANSI URL string")
    raw = reader.take(count)
    if raw[-1] != 0 or b"\0" in raw[:-1]:
        raise PackageError("invalid legacy URL string")
    return raw[:-1].decode("latin1")


def world_model_reference(package):
    levels = [e for e in package.exports if e.class_ref and package.class_name(e) == "Level"]
    if len(levels) != 1:
        raise PackageError("expected one Level export")
    reader, count = _array(package, levels[0].index + 1, "Level", 1)
    for _ in range(count):
        actor = reader.compact()
        if not 0 <= actor <= len(package.exports):
            raise PackageError("invalid level actor reference")
    for _ in range(4):  # Protocol, host, map, portal.
        _string(reader)
    options = reader.compact()
    if not 0 <= options <= reader.end - reader.offset:
        raise PackageError("invalid URL option count")
    for _ in range(options):
        _string(reader)
    reader.unpack("i")  # Port.
    if reader.unpack("i") not in (0, 1):
        raise PackageError("invalid URL validity flag")
    reference = reader.compact()
    _native(package, reference, "Model")
    return reference


@dataclass(frozen=True)
class NativeBsp:
    model_reference: int
    table_references: dict
    points: tuple
    vectors: tuple
    vertices: tuple
    surfaces: tuple
    nodes: tuple
    zones: tuple
    reachable: tuple
    unused_invalid_pool_entries: int

    def point_zone(self, point):
        _finite(point)
        if not self.nodes:
            raise PackageError("empty BSP has no queried zone")
        index, seen = 0, set()
        while True:
            if index in seen:
                raise PackageError("cycle in BSP query")
            seen.add(index)
            node = self.nodes[index]
            side = int(sum(a*b for a,b in zip(node["plane"][:3],point,strict=True)) >= node["plane"][3])
            child = node["front" if side else "back"]
            if child == -1:
                return node["zones"][side]
            index = child


def read_world_bsp(package: Package61) -> NativeBsp:
    reference = world_model_reference(package)
    reader = _native(package, reference, "Model")
    _finite(reader.unpack("6f"))  # UPrimitive bounding box.
    if reader.unpack("B") not in (0, 1):
        raise PackageError("invalid primitive bounds flag")
    _finite(reader.unpack("3f"))  # v61 sphere omits radius.
    refs = dict(zip(("vectors", "points", "nodes", "surfaces", "vertices", "polys"),
                    (reader.compact() for _ in range(6)), strict=True))
    _native(package, refs["polys"], "Polys")

    def vectors(key):
        cursor, count = _array(package, refs[key], "Vectors", 12)
        result = tuple(_finite(cursor.unpack("3f")) for _ in range(count))
        _end(cursor)
        return result

    points, bases = vectors("points"), vectors("vectors")
    cursor, count = _array(package, refs["vertices"], "Verts", 2)
    vertices = tuple((cursor.compact(), cursor.compact()) for _ in range(count))
    shared_sides = cursor.compact()
    if shared_sides < 0:
        raise PackageError("invalid shared side count")
    _end(cursor)

    cursor, count = _array(package, refs["surfaces"], "BspSurfs", 13)
    surfaces = []
    for _ in range(count):
        surface = dict(texture_reference=cursor.compact(), flags=cursor.unpack("I"),
                       base=cursor.compact(), normal=cursor.compact(), u=cursor.compact(), v=cursor.compact(),
                       lightmap=cursor.compact(), brush_polygon=cursor.compact(),
                       pan=cursor.unpack("hh"), actor_reference=cursor.compact())
        if not 0 <= surface["base"] < len(points) or not all(0 <= surface[k] < len(bases) for k in ("normal","u","v")):
            raise PackageError("surface index outside point/vector tables")
        package.object_path(surface["texture_reference"], "Source")
        package.object_path(surface["actor_reference"], "Source")
        surfaces.append(surface)
    _end(cursor)

    cursor, count = _array(package, refs["nodes"], "BspNodes", 39)
    nodes = []
    for _ in range(count):
        node = dict(plane=_finite(cursor.unpack("4f")), zone_mask=cursor.unpack("Q"), flags=cursor.unpack("B"),
                    first_vertex=cursor.compact(), surface=cursor.compact(), back=cursor.compact(),
                    front=cursor.compact(), coplanar=cursor.compact(), collision_bound=cursor.compact(),
                    render_bound=cursor.compact(), zones=cursor.unpack("BB"),
                    vertex_count=cursor.unpack("B"), leaves=cursor.unpack("ii"))
        if not 0 <= node["surface"] < len(surfaces):
            raise PackageError("node surface outside table")
        if not 0 <= node["first_vertex"] <= len(vertices) - node["vertex_count"]:
            raise PackageError("node vertex span outside pool")
        if any(i != -1 and not 0 <= i < count for i in (node["back"],node["front"],node["coplanar"])):
            raise PackageError("node child outside table")
        for point_index, side in vertices[node["first_vertex"]:node["first_vertex"]+node["vertex_count"]]:
            if not 0 <= point_index < len(points):
                raise PackageError("referenced node point outside table")
        nodes.append(node)
    zone_count = cursor.compact()
    if not 0 <= zone_count <= 64:
        raise PackageError("invalid BSP zone count")
    zones = tuple(dict(actor_reference=cursor.compact(), connectivity=cursor.unpack("Q"), visibility=cursor.unpack("Q"))
                  for _ in range(zone_count))
    for zone in zones:
        package.object_path(zone["actor_reference"], "Source")
    if any(z >= zone_count for node in nodes for z in node["zones"]):
        raise PackageError("node zone outside table")
    _end(cursor)

    # Validate cycles, while allowing a table to retain unreferenced native slots.
    done, active = set(), set()
    todo = [(0, False)] if nodes else []
    while todo:
        index, leaving = todo.pop()
        if index == -1:
            continue
        if leaving:
            active.remove(index)
            done.add(index)
        elif index in active:
            raise PackageError("cycle in BSP graph")
        elif index not in done:
            active.add(index)
            todo.append((index, True))
            todo.extend((nodes[index][k], False) for k in ("coplanar","back","front"))
    unused_invalid = sum(not 0 <= p < len(points) for p,s in vertices)
    return NativeBsp(reference, refs, points, bases, vertices, tuple(surfaces), tuple(nodes), zones,
                     tuple(sorted(done)), unused_invalid)
