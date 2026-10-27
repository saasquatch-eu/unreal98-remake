"""Read selected Vector properties from the original, uncompressed UE1 v61 format.

This bounded reader never writes packages or loads native code. It deliberately
rejects other versions, state-frame objects, and array tags in selected objects.
"""

from dataclasses import dataclass
import math
import struct


class PackageError(ValueError):
    pass


class Reader:
    def __init__(self, data: bytes, offset: int = 0, end: int | None = None):
        self.data, self.offset = data, offset
        self.end = len(data) if end is None else end
        if not 0 <= offset <= self.end <= len(data):
            raise PackageError("range outside package")

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > self.end:
            raise PackageError(f"truncated data at byte {self.offset}")
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def unpack(self, fmt: str):
        result = struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))
        return result[0] if len(result) == 1 else result

    def compact(self) -> int:
        first = self.unpack("B")
        value, negative, more = first & 63, bool(first & 128), bool(first & 64)
        shift = 6
        for count in range(4):
            if not more:
                break
            byte = self.unpack("B")
            if count == 3:
                if byte > 31:
                    raise PackageError("compact index exceeds 32 bits")
                value |= byte << shift
                more = False
            else:
                value |= (byte & 127) << shift
                more = bool(byte & 128)
                shift += 7
        if value > (0x80000000 if negative else 0x7fffffff):
            raise PackageError("compact index outside signed 32-bit range")
        return -value if negative else value


@dataclass(frozen=True)
class Export:
    index: int
    name: str
    class_ref: int
    flags: int
    offset: int
    size: int
    outer: int = 0


@dataclass(frozen=True)
class VectorEvidence:
    export_index: int
    property_offset: int
    values: tuple[float, float, float]
    raw: bytes


class Package61:
    def __init__(self, data: bytes):
        self.data = data
        reader = Reader(data)
        signature, version, licensee, flags, nc, no, ec, eo, ic, io = reader.unpack("IHHIiiiiii")
        if (signature, version, licensee, flags) != (0x9E2A83C1, 61, 0, 0):
            raise PackageError("only uncompressed, licensee-zero package version 61 is supported")
        for count, offset, minimum in ((nc, no, 5), (ec, eo, 12), (ic, io, 7)):
            if count < 0 or offset < 36 or offset > len(data) or count > (len(data) - offset) // minimum:
                raise PackageError("invalid table count or offset")
        self.names = []
        reader = Reader(data, no)
        for _ in range(nc):
            end = data.find(b"\0", reader.offset)
            if end < 0:
                raise PackageError("unterminated name")
            self.names.append(reader.take(end - reader.offset + 1)[:-1].decode("latin1"))
            reader.take(4)  # Name flags.
        reader = Reader(data, io)
        self.imports = []
        for _ in range(ic):
            class_package, class_name = self.name(reader.compact()), self.name(reader.compact())
            outer = reader.unpack("i")
            name = self.name(reader.compact())
            self.imports.append((class_package, class_name, outer, name))
        reader = Reader(data, eo)
        self.exports = []
        for index in range(ec):
            cls = reader.compact()
            reader.compact()  # Super reference.
            outer = reader.unpack("i")
            name = self.name(reader.compact())
            flags, size = reader.unpack("I"), reader.compact()
            offset = reader.compact() if size > 0 else 0
            if size < 0 or offset < 0 or offset + size > len(data):
                raise PackageError("export data outside package")
            self.exports.append(Export(index, name, cls, flags, offset, size, outer))

    def name(self, index: int) -> str:
        if not 0 <= index < len(self.names):
            raise PackageError("invalid name index")
        return self.names[index]

    def class_name(self, export: Export) -> str:
        ref = export.class_ref
        if ref < 0 and -ref <= len(self.imports):
            return self.imports[-ref - 1][3]
        if 0 < ref <= len(self.exports):
            return self.exports[ref - 1].name
        raise PackageError("invalid class reference")

    def object_path(self, reference: int, package_name: str) -> str | None:
        if reference == 0:
            return None
        names, seen = [], set()
        while reference:
            if reference in seen:
                raise PackageError("cycle in object reference path")
            seen.add(reference)
            if reference < 0 and -reference <= len(self.imports):
                _, _, outer, name = self.imports[-reference - 1]
            elif 0 < reference <= len(self.exports):
                export = self.exports[reference - 1]
                name, outer = export.name, export.outer
                if outer == 0:
                    names.append(name)
                    names.append(package_name)
                    break
            else:
                raise PackageError("object reference outside package tables")
            names.append(name)
            reference = outer
        return ".".join(reversed(names))

    def vector_property(self, actor_name: str, actor_class: str, property_name: str) -> VectorEvidence:
        matches = [e for e in self.exports if e.name == actor_name and self.class_name(e) == actor_class]
        if len(matches) != 1:
            raise PackageError(f"{actor_class} {actor_name}: expected one binary export, found {len(matches)}")
        export = matches[0]
        if export.flags & 0x02000000:
            raise PackageError("selected export has a state frame; unsupported by this reader")
        reader = Reader(self.data, export.offset, export.offset + export.size)
        result = None
        while True:
            name = self.name(reader.compact())
            if name == "None":
                break
            info = reader.unpack("B")
            kind, size_code = info & 15, (info >> 4) & 7
            if kind == 0:
                raise PackageError("invalid property type")
            structure = self.name(reader.compact()) if kind == 10 else None
            size = (1, 2, 4, 12, 16)[size_code] if size_code < 5 else reader.unpack(("B", "H", "I")[size_code - 5])
            if info & 128 and kind != 3:
                raise PackageError("selected export contains an array tag; unsupported")
            if kind == 3:
                size = 0  # Boolean value lives in the tag's high bit.
            offset = reader.offset
            raw = reader.take(size)
            if name == property_name:
                if result is not None or kind != 10 or structure != "Vector" or size != 12:
                    raise PackageError("requested property is ambiguous or not a Vector")
                values = struct.unpack("<fff", raw)
                if not all(math.isfinite(v) for v in values):
                    raise PackageError("non-finite binary vector")
                result = VectorEvidence(export.index, offset, values, raw)
        if result is None:
            raise PackageError("requested property is omitted; defaults are not decoded")
        return result
