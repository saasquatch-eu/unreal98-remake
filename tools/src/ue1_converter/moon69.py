"""Bounded read-only v69 moon-resource decoding; the v61 map reader stays strict."""
from dataclasses import dataclass
import hashlib
import math
import struct

from .package61 import Export, Package61, PackageError, Reader
from .texture61 import Texture, properties, scalar


class MoonPackage69(Package61):
    """Only v69, licensee 0/227, ANSI names, ordinary tables and selected assets."""
    def __init__(self, data):
        r = Reader(data)
        signature, version, licensee, flags, nc, no, ec, eo, ic, io = r.unpack('IHHIiiiiii')
        if (signature, version) != (0x9e2a83c1, 69) or licensee not in (0, 227) or flags not in (0, 1):
            raise PackageError('unsupported moon resource package')
        for n, offset, minimum in ((nc, no, 6), (ec, eo, 12), (ic, io, 7)):
            if not 0 <= n <= 100000 or not 36 <= offset <= len(data) or n > (len(data) - offset) // minimum:
                raise PackageError('invalid moon package table')
        self.data, self.flags, self.licensee = data, flags, licensee
        self.names = []; r = Reader(data, no)
        for _ in range(nc):
            n = r.compact()
            if not 1 <= n <= 1024: raise PackageError('unsupported moon package name')
            raw = r.take(n)
            if raw[-1] or b'\0' in raw[:-1]: raise PackageError('invalid moon package name terminator')
            self.names.append(raw[:-1].decode('latin1')); r.take(4)
        self.imports = []; r = Reader(data, io)
        for _ in range(ic): self.imports.append((self.name(r.compact()), self.name(r.compact()), r.unpack('i'), self.name(r.compact())))
        self.exports = []; r = Reader(data, eo)
        for i in range(ec):
            cls = r.compact(); r.compact(); outer = r.unpack('i'); name = self.name(r.compact()); ef = r.unpack('I'); size = r.compact(); offset = r.compact() if size else 0
            if size < 0 or offset < 0 or offset + size > len(data): raise PackageError('moon export outside package')
            self.exports.append(Export(i, name, cls, ef, offset, size, outer))


def selected(package, name, classes):
    matches = [e for e in package.exports if e.name == name and e.class_ref and package.class_name(e) in classes]
    if len(matches) != 1: raise PackageError('ambiguous or missing moon resource: ' + name)
    return matches[0]


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def unpack_vertex(value):
    return (signed(value & 2047, 11), signed((value >> 11) & 2047, 11), signed((value >> 22) & 1023, 10))


@dataclass(frozen=True)
class MoonMesh:
    vertices: list
    triangles: list
    uvs: list
    texture: str
    scale: tuple
    origin: tuple
    rotation: tuple
    metadata: dict


def decode_mesh(package, name):
    export = selected(package, name, ('Mesh', 'LodMesh')); props, r = properties(package, export)
    if props: raise PackageError('unexpected moon mesh properties')
    def count(maximum=10000):
        n = r.compact()
        if not 0 <= n <= maximum: raise PackageError('moon array count outside bound')
        return n
    def array(fmt, lazy=False):
        end = r.unpack('i') if lazy else None
        values = [r.unpack(fmt) for _ in range(count())]
        if end is not None and end != r.offset: raise PackageError('moon lazy array endpoint differs')
        return values
    def box():
        values = r.unpack('ffffffB')
        if values[-1] != 1 or not all(math.isfinite(v) for v in values[:-1]) or any(values[i] > values[i + 3] for i in range(3)):
            raise PackageError('invalid moon bounds')
        return values
    def sphere():
        values = r.unpack('ffff')
        if not all(math.isfinite(v) for v in values) or values[-1] < 0: raise PackageError('invalid moon sphere')
        return values
    box(); sphere(); packed = array('I', True); raw_tris = array('HHHBBBBBBIi', True)
    for _ in range(count(32)):
        package.name(r.compact()); package.name(r.compact()); start, frames = r.unpack('ii')
        if (start, frames) != (0, 1) or count(0): raise PackageError('only one-frame moon sequences supported')
        rate = r.unpack('f')
        if not math.isfinite(rate): raise PackageError('invalid moon sequence rate')
    connects = array('ii', True); box(); sphere(); links = array('i', True)
    textures = [package.object_path(r.compact(), 'UnrealI') for _ in range(count(16))]
    for _ in range(count(1)): box()
    for _ in range(count(1)): sphere()
    frame_vertices, frames, and_flags, or_flags = r.unpack('iiII')
    scale, origin, rotation = r.unpack('fff'), r.unpack('fff'), r.unpack('iii'); r.unpack('ii'); array('f')
    if frames != 1 or frame_vertices != len(packed) or not packed or len(textures) != 1 or not textures[0] or or_flags or and_flags not in (0, 0xffffffff):
        raise PackageError('unsupported moon frame/texture/flags')
    if not all(math.isfinite(v) for v in scale + origin) or any(v <= 0 for v in scale): raise PackageError('invalid moon transform')
    vertices = [unpack_vertex(v) for v in packed]; triangles = []; uvs = []
    if package.class_name(export) == 'LodMesh':
        collapse = array('H'); levels = array('H'); faces = array('HHHH'); collapse_wedges = array('H'); wedges = array('HBB'); materials = array('Ii'); special = array('HHHH')
        model_vertices, special_vertices = r.unpack('ii'); lod = r.unpack('fffiff'); remap = array('H'); old_frames = r.unpack('i')
        if raw_tris or connects or links or special or special_vertices or remap or old_frames or model_vertices != frame_vertices or materials != [(0, 0)]:
            raise PackageError('unsupported moon LOD representation')
        if len(collapse) != frame_vertices or len(levels) != len(faces) or len(collapse_wedges) != len(wedges) or not all(math.isfinite(v) for v in lod):
            raise PackageError('moon LOD table sizes differ')
        if any(v >= frame_vertices for v in collapse) or any(v > frame_vertices for v in levels) or any(v >= len(wedges) for v in collapse_wedges):
            raise PackageError('moon LOD collapse index outside table')
        for a, b, c, material in faces:
            if material or any(v >= len(wedges) for v in (a, b, c)): raise PackageError('moon face wedge/material outside table')
            corners = [wedges[v] for v in (a, b, c)]; triangles.append([v[0] for v in corners]); uvs.append([[v[1] / 256, v[2] / 256] for v in corners])
    else:
        if len(connects) != frame_vertices: raise PackageError('moon connection count differs')
        if any(n < 0 or offset < 0 or offset + n > len(links) for n, offset in connects) or any(v < 0 or v >= len(raw_tris) for v in links):
            raise PackageError('moon connectivity outside table')
        for tri in raw_tris:
            if tri[-2:] != (0, 0): raise PackageError('unsupported moon triangle material/flags')
            triangles.append(list(tri[:3])); uvs.append([[tri[3 + i * 2] / 256, tri[4 + i * 2] / 256] for i in range(3)])
    if r.offset != r.end: raise PackageError('unconsumed moon mesh bytes')
    if not triangles or any(len(set(t)) != 3 or any(v < 0 or v >= len(vertices) for v in t) for t in triangles): raise PackageError('invalid moon triangles')
    metadata = dict(name=name, mesh_class=package.class_name(export), export_index=export.index, export_sha256=hashlib.sha256(package.data[export.offset:r.end]).hexdigest(),
                    vertex_count=frame_vertices, triangle_count=len(triangles), and_flags=and_flags, or_flags=or_flags)
    return MoonMesh(vertices, triangles, uvs, textures[0], scale, origin, rotation, metadata)


def decode_moon_texture(package, name):
    export = selected(package, name, ('Texture',)); props, r = properties(package, export)
    width, height = scalar(props, 'USize', 2), scalar(props, 'VSize', 2)
    if scalar(props, 'Format', 1, 0) != 0 or any(not isinstance(v, int) or not 1 <= v <= 1024 or v & (v - 1) for v in (width, height)):
        raise PackageError('unsupported moon texture dimensions/format')
    for field, dim in [('UBits', width), ('VBits', height)]:
        if scalar(props, field, 1, dim.bit_length() - 1) != dim.bit_length() - 1: raise PackageError('moon texture bit size differs')
    ref = scalar(props, 'Palette', 5)
    if not isinstance(ref, int) or not 0 < ref <= len(package.exports): raise PackageError('moon palette must be local')
    palette_export = package.exports[ref - 1]
    if package.class_name(palette_export) != 'Palette': raise PackageError('moon palette has wrong class')
    _, pr = properties(package, palette_export)
    if pr.compact() != 256: raise PackageError('moon palette requires 256 colors')
    palette = pr.take(1024)
    if pr.offset != pr.end: raise PackageError('unconsumed moon palette bytes')
    count = r.compact()
    if not 1 <= count <= max(width, height).bit_length(): raise PackageError('invalid moon mip count')
    mips = []; pixels = None
    for level in range(count):
        end, size = r.unpack('i'), r.compact(); offset = r.offset; data = r.take(size)
        if r.offset != end: raise PackageError('moon mip endpoint differs')
        w, h, u, v = r.unpack('iiBB')
        if (w, h) != (max(1, width >> level), max(1, height >> level)) or size != w * h or (u, v) != (w.bit_length() - 1, h.bit_length() - 1):
            raise PackageError('moon mip dimensions differ')
        if level == 0: pixels = data
        mips.append(dict(width=w, height=h, offset=offset, size=size, sha256=hashlib.sha256(data).hexdigest()))
    if r.offset != r.end: raise PackageError('unconsumed moon texture bytes')
    path = package.object_path(export.index + 1, 'UnrealI')
    return Texture(width, height, pixels, palette, dict(path=path, width=width, height=height, export_sha256=hashlib.sha256(package.data[export.offset:r.end]).hexdigest(),
                   palette_sha256=hashlib.sha256(palette).hexdigest(), pixels_sha256=hashlib.sha256(pixels).hexdigest(), mips=mips))
