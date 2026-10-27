"""Source-space brush math; supports zero shear and the legacy rotator grid.

Reference: OldUnreal Unreal-PubSrc ABrush.h and UnMath.h, commit
2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6. No engine code is embedded here.
Python uses double precision; this is not bit-exact UE1 floating-point emulation.
"""

from dataclasses import dataclass
import math

from .t3d import Block, integer, number, parse_struct


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def matvec(matrix, vector):
    return tuple(dot(row, vector) for row in matrix)


def multiply(a, b):
    return tuple(tuple(dot(row, column) for column in zip(*b)) for row in a)


def transpose(matrix):
    return tuple(zip(*matrix))


def inverse(matrix):
    a, b, c = matrix
    columns = (cross(b, c), cross(c, a), cross(a, b))
    determinant = dot(a, columns[0])
    if determinant == 0 or not math.isfinite(determinant):
        raise ValueError("singular or non-finite brush transform")
    return tuple(tuple(v / determinant for v in row) for row in transpose(columns))


def diagonal(v):
    return tuple(tuple(v[i] if i == j else 0.0 for j in range(3)) for i in range(3))


def rotation_matrix(rotation):
    # UE1 table lookup drops two low rotator bits, including for negative angles.
    p, y, r = [math.tau * ((angle >> 2) & 16383) / 16384 for angle in rotation]
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    yaw = ((cy, -sy, 0), (sy, cy, 0), (0, 0, 1))
    pitch = ((cp, 0, -sp), (0, 1, 0), (sp, 0, cp))
    roll = ((1, 0, 0), (0, cr, sr), (0, -sr, cr))
    return multiply(multiply(yaw, pitch), roll)


@dataclass(frozen=True)
class BrushTransform:
    location: tuple = (0.0, 0.0, 0.0)
    pivot: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0, 0, 0)
    main_scale: tuple = (1.0, 1.0, 1.0)
    post_scale: tuple = (1.0, 1.0, 1.0)

    def __post_init__(self):
        if len(self.rotation) != 3 or not all(isinstance(v, int) and -2**31 <= v < 2**31 for v in self.rotation):
            raise ValueError("rotator components must be signed 32-bit integers")
        for value in (self.location, self.pivot, self.main_scale, self.post_scale):
            if len(value) != 3 or not all(math.isfinite(v) for v in value):
                raise ValueError("expected finite three-component transform fields")
        if 0 in self.main_scale or 0 in self.post_scale:
            raise ValueError("zero brush scale is unsupported")

    @property
    def linear(self):
        return multiply(multiply(diagonal(self.post_scale), rotation_matrix(self.rotation)), diagonal(self.main_scale))

    @property
    def reverses_winding(self):
        return math.prod(self.main_scale) * math.prod(self.post_scale) < 0

    def point(self, value):
        scaled = matvec(self.linear, tuple(v - p for v, p in zip(value, self.pivot, strict=True)))
        return tuple(v + l for v, l in zip(scaled, self.location, strict=True))

    def local_point(self, value):
        local = matvec(inverse(self.linear), tuple(v - l for v, l in zip(value, self.location, strict=True)))
        return tuple(v + p for v, p in zip(local, self.pivot, strict=True))

    def covector(self, value):
        """Texture gradients and normals use inverse transpose; do not normalize UVs."""
        return matvec(transpose(inverse(self.linear)), value)

    def normal(self, value):
        transformed = self.covector(value)
        length = math.sqrt(dot(transformed, transformed))
        if length == 0:
            raise ValueError("zero polygon normal")
        return tuple(v / length for v in transformed)


def from_actor(actor: Block, pivot_overrides: dict[str, float] | None = None) -> BrushTransform:
    if actor.attribute("Class") not in {"Brush", "Mover"}:
        raise ValueError("only Brush and Mover source transforms are supported")

    def components(value, keys, defaults, overrides=None, integers=False):
        specified = parse_struct(value, actor.line) if value is not None else ()
        if len({p.name for p in specified}) != len(specified) or any(p.name not in keys for p in specified):
            raise ValueError("unknown or repeated transform component")
        values = dict(zip(keys, defaults, strict=True))
        for p in specified:
            if overrides and p.name in overrides:
                values[p.name] = overrides[p.name]
            else:
                values[p.name] = integer(p.value, p.line) if integers else number(p.value, p.line)
        return tuple(values[k] for k in keys)

    def scale(name):
        fields = parse_struct(actor.property(name), actor.line) if actor.property(name) else ()
        if len({p.name for p in fields}) != len(fields):
            raise ValueError("repeated scale field")
        result = (1.0, 1.0, 1.0)
        for p in fields:
            if p.name == "Scale":
                result = components(p.value, "XYZ", result)
            elif p.name == "SheerRate":
                if number(p.value, p.line) != 0:
                    raise ValueError("nonzero shear requires separate validation")
            elif p.name == "SheerAxis":
                if p.value not in {"SHEER_None", "SHEER_XY", "SHEER_XZ", "SHEER_YX", "SHEER_YZ", "SHEER_ZX", "SHEER_ZY"}:
                    raise ValueError("unknown shear axis")
            else:
                raise ValueError("unknown scale field")
        return result

    # TempScale and DrawScale are not used by the published ABrush model transform.
    return BrushTransform(
        components(actor.property("Location"), "XYZ", (0.0, 0.0, 0.0)),
        components(actor.property("PrePivot"), "XYZ", (0.0, 0.0, 0.0), pivot_overrides),
        components(actor.property("Rotation"), ("Pitch", "Yaw", "Roll"), (0, 0, 0), integers=True),
        scale("MainScale"), scale("PostScale"))
