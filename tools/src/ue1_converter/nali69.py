"""Bounded read-only extraction of UE1 v69 vertex-animated Nali meshes.

UnrealShare.u can contain malformed *later* export-table records on this install.
Only the validated prefix needed to resolve the requested mesh is admitted; no
claim is made about unrelated exports or native UE1 playback semantics.
"""

from dataclasses import dataclass
import hashlib
import math
import struct

from .moon69 import unpack_vertex
from .package61 import Export, Package61, PackageError, Reader
from .texture61 import properties


class TargetPackage69(Package61):
    """Read v69 tables through named target exports, never past that prefix."""

    def __init__(self, data: bytes, required_names: set[str], *, minimum_exports: int = 0):
        if not required_names or len(required_names) > 8:
            raise PackageError('invalid target export set')
        r = Reader(data)
        signature, version, licensee, flags, nc, no, ec, eo, ic, io = r.unpack('IHHIiiiiii')
        if (signature, version) != (0x9e2a83c1, 69) or licensee not in (0, 227) or flags not in (0, 1):
            raise PackageError('unsupported Nali package profile')
        for count, offset, minimum in ((nc, no, 6), (ec, eo, 12), (ic, io, 7)):
            if not 0 <= count <= 100000 or not 36 <= offset <= len(data) or count > (len(data) - offset) // minimum:
                raise PackageError('invalid Nali package table')
        if not 0 <= minimum_exports <= ec:
            raise PackageError('invalid required export prefix')
        self.data, self.flags, self.licensee = data, flags, licensee
        self.declared_export_count = ec
        self.names = []
        r = Reader(data, no)
        for _ in range(nc):
            n = r.compact()
            if not 1 <= n <= 1024:
                raise PackageError('invalid Nali package name length')
            raw = r.take(n)
            if raw[-1] or b'\0' in raw[:-1]:
                raise PackageError('invalid Nali package name')
            self.names.append(raw[:-1].decode('latin1'))
            r.take(4)
        self.imports = []
        r = Reader(data, io)
        for _ in range(ic):
            self.imports.append((self.name(r.compact()), self.name(r.compact()), r.unpack('i'), self.name(r.compact())))
        self.exports = []
        r = Reader(data, eo)
        found = set()
        for index in range(ec):
            cls = r.compact(); r.compact(); outer = r.unpack('i'); name = self.name(r.compact())
            export_flags = r.unpack('I'); size = r.compact(); offset = r.compact() if size > 0 else 0
            if size < 0 or offset < 0 or offset + size > len(data):
                raise PackageError('target export prefix outside package')
            self.exports.append(Export(index, name, cls, export_flags, offset, size, outer))
            if name in required_names:
                found.add(name)
            if found == required_names and len(self.exports) >= minimum_exports:
                break
        if found != required_names:
            raise PackageError('missing target exports')


@dataclass(frozen=True)
class Sequence:
    name: str
    group: str
    start: int
    count: int
    rate: float
    notifies: tuple[tuple[float, str], ...]


def read_sequences(reader: Reader, package: TargetPackage69, frame_limit: int):
    count = reader.compact()
    if not 1 <= count <= 256:
        raise PackageError('invalid animation sequence count')
    result = []
    for _ in range(count):
        name, group = package.name(reader.compact()), package.name(reader.compact())
        start, frames = reader.unpack('ii')
        notify_count = reader.compact()
        if not 0 <= notify_count <= 32:
            raise PackageError('invalid animation notify count')
        notifies = tuple((reader.unpack('f'), package.name(reader.compact())) for _ in range(notify_count))
        rate = reader.unpack('f')
        if not name or not 0 <= start < frame_limit or not 1 <= frames <= frame_limit - start or not math.isfinite(rate) or rate <= 0:
            raise PackageError('invalid animation sequence range or rate')
        if any(not math.isfinite(t) or not 0 <= t <= 1 or not event for t, event in notifies):
            raise PackageError('invalid animation notify')
        result.append(Sequence(name, group, start, frames, rate, notifies))
    if len({s.name for s in result}) != len(result):
        raise PackageError('duplicate animation sequence name')
    return tuple(result)


@dataclass(frozen=True)
class NaliMesh:
    name: str
    packed: bytes
    vertex_count: int
    frame_count: int
    sequences: tuple[Sequence, ...]
    faces: tuple[tuple[int, int, int, int], ...]
    wedges: tuple[tuple[int, int, int], ...]
    scale: tuple[float, float, float]
    origin: tuple[float, float, float]
    rotation: tuple[int, int, int]
    source: dict

    def frame(self, index: int):
        if not 0 <= index < self.frame_count:
            raise PackageError('animation frame outside mesh')
        start = index * self.vertex_count * 4
        return tuple(unpack_vertex(value) for (value,) in struct.iter_unpack('<I', self.packed[start:start + self.vertex_count * 4]))


def decode_nali_mesh(package: TargetPackage69, name: str, package_name: str):
    matches = [e for e in package.exports if e.name == name and e.class_ref and package.class_name(e) == 'LodMesh']
    if len(matches) != 1:
        raise PackageError('expected one Nali LodMesh')
    export = matches[0]
    props, r = properties(package, export)
    if props:
        raise PackageError('Nali mesh has unsupported tagged properties')

    def array(fmt, *, lazy=False, maximum=2_000_000):
        endpoint = r.unpack('i') if lazy else None
        count = r.compact()
        if not 0 <= count <= maximum:
            raise PackageError('Nali array count outside bound')
        raw = r.take(count * struct.calcsize('<' + fmt))
        if endpoint is not None and r.offset != endpoint:
            raise PackageError('Nali lazy array endpoint differs')
        return list(struct.iter_unpack('<' + fmt, raw)), raw

    def box():
        values = r.unpack('ffffffB')
        if values[-1] != 1 or not all(math.isfinite(v) for v in values[:-1]) or any(values[i] > values[i + 3] for i in range(3)):
            raise PackageError('invalid Nali bounds')
        return values

    def sphere():
        values = r.unpack('ffff')
        if not all(math.isfinite(v) for v in values) or values[-1] < 0:
            raise PackageError('invalid Nali sphere')
        return values

    box(); sphere()
    packed_values, packed = array('I', lazy=True)
    raw_faces, _ = array('HHHBBBBBBIi', lazy=True)
    # Sequence bounds are rechecked after the frame count is read below.
    sequences = read_sequences(r, package, max(1, len(packed_values)))
    connections, _ = array('ii', lazy=True)
    box(); sphere()
    links, _ = array('i', lazy=True)
    texture_count = r.compact()
    if not 1 <= texture_count <= 16:
        raise PackageError('invalid Nali texture count')
    textures = [package.object_path(r.compact(), package_name) for _ in range(texture_count)]
    frame_boxes, _ = array('ffffffB', maximum=10000)
    frame_spheres, _ = array('ffff', maximum=10000)
    vertex_count, frame_count, and_flags, or_flags = r.unpack('iiII')
    scale, origin, rotation = r.unpack('fff'), r.unpack('fff'), r.unpack('iii')
    middle = r.unpack('ii')
    floats, _ = array('f', maximum=1000)
    collapse, _ = array('H'); levels, _ = array('H'); faces, _ = array('HHHH')
    collapse_wedges, _ = array('H'); wedges, _ = array('HBB'); materials, _ = array('Ii', maximum=64)
    special, _ = array('HHHH'); model_vertices, special_vertices = r.unpack('ii')
    lod = r.unpack('fffiff'); remap, _ = array('H'); old_frames = r.unpack('i')
    if r.offset != r.end or raw_faces or connections or links or special or remap or old_frames or middle != (0, 0):
        raise PackageError('unsupported Nali mesh tail')
    if not 1 <= vertex_count <= 100000 or not 1 <= frame_count <= 10000 or len(packed_values) != vertex_count * frame_count:
        raise PackageError('Nali frame/vertex counts differ')
    if len(frame_boxes) != frame_count or len(frame_spheres) != frame_count:
        raise PackageError('Nali frame bounds differ')
    if any(v[-1] != 1 or not all(math.isfinite(x) for x in v[:-1]) or any(v[i] > v[i + 3] for i in range(3)) for v in frame_boxes):
        raise PackageError('invalid Nali frame box')
    if any(not all(math.isfinite(x) for x in v) or v[-1] < 0 for v in frame_spheres):
        raise PackageError('invalid Nali frame sphere')
    if len(collapse) != vertex_count or len(levels) != len(faces) or len(collapse_wedges) != len(wedges):
        raise PackageError('Nali LOD array lengths differ')
    if model_vertices != vertex_count or special_vertices or not faces or not wedges or not materials or not textures[0]:
        raise PackageError('unsupported Nali LOD representation')
    if any(v[0] >= vertex_count for v in wedges) or any(v >= vertex_count for (v,) in collapse):
        raise PackageError('Nali vertex reference outside range')
    if any(v >= len(wedges) for face in faces for v in face[:3]) or any(face[3] >= len(materials) for face in faces):
        raise PackageError('Nali face wedge/material outside range')
    if any(len({wedges[w][0] for w in face[:3]}) != 3 for face in faces):
        raise PackageError('degenerate Nali full-detail face')
    if any(v[0] >= len(wedges) for v in collapse_wedges) or any(v[0] > vertex_count for v in levels):
        raise PackageError('Nali LOD reference outside range')
    if not all(math.isfinite(v) and v > 0 for v in scale) or not all(math.isfinite(v) for v in origin + lod[:3] + lod[4:]) or or_flags or and_flags not in (0, 0xffffffff):
        raise PackageError('unsupported Nali scale/LOD/flags')
    if any(s.start + s.count > frame_count for s in sequences):
        raise PackageError('Nali sequence exceeds frame count')
    if any(not math.isfinite(v[0]) for v in floats):
        raise PackageError('invalid Nali float array')
    source = dict(package_sha256=hashlib.sha256(package.data).hexdigest(), export_index=export.index,
                  export_sha256=hashlib.sha256(package.data[export.offset:r.end]).hexdigest(),
                  export_table_prefix=len(package.exports), declared_export_count=package.declared_export_count,
                  texture_paths=textures, materials=[list(v) for v in materials])
    return NaliMesh(name, packed, vertex_count, frame_count, sequences, tuple(faces), tuple(wedges), scale, origin, rotation, source)
