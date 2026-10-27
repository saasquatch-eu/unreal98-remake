"""Finite-window, axis-aligned CSG reference for synthetic validation only.

This does not consume brushes or generate mesh boundaries. Half-open boxes give
deterministic membership at faces; they do not emulate UE1's BSP tolerances.
"""

from dataclasses import dataclass
from itertools import product
import math


@dataclass(frozen=True)
class Box:
    minimum: tuple
    maximum: tuple

    def __post_init__(self):
        if len(self.minimum) != 3 or len(self.maximum) != 3:
            raise ValueError("box requires three dimensions")
        if not all(math.isfinite(a) and math.isfinite(b) and a < b
                   for a, b in zip(self.minimum, self.maximum, strict=True)):
            raise ValueError("box requires finite increasing bounds")

    def contains(self, point):
        return all(a <= v < b for a, v, b in zip(self.minimum, point, self.maximum, strict=True))


@dataclass(frozen=True)
class Operation:
    kind: str
    box: Box

    def __post_init__(self):
        if self.kind not in {"CSG_Add", "CSG_Subtract"}:
            raise ValueError("unsupported CSG operation")


def is_solid(point, operations, *, initial_solid):
    result = initial_solid
    for operation in operations:
        if operation.box.contains(point):
            result = operation.kind == "CSG_Add"
    return result


def solid_volume(window: Box, operations: tuple[Operation, ...], *, initial_solid: bool):
    cuts = []
    for axis in range(3):
        lo, hi = window.minimum[axis], window.maximum[axis]
        values = {lo, hi}
        values.update(v for op in operations for v in (op.box.minimum[axis], op.box.maximum[axis]) if lo < v < hi)
        ordered = sorted(values)
        cuts.append(list(zip(ordered, ordered[1:])))
    if math.prod(map(len, cuts)) > 100000:
        raise ValueError("synthetic reference cell budget exceeded")
    volume = 0.0
    for cell in product(*cuts):
        if is_solid(tuple((a + b) / 2 for a, b in cell), operations, initial_solid=initial_solid):
            volume += math.prod(b - a for a, b in cell)
    return volume
