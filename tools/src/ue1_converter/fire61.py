"""Bounded v61 FireTexture records and an independent animated preview renderer.

The native fire update algorithm is not reproduced. All source records remain
available in metadata; unsupported spark types fail before preview generation.
"""
from dataclasses import dataclass
import hashlib
import random

from .package61 import PackageError
from .texture61 import properties, scalar, Texture, tga_bytes


@dataclass(frozen=True)
class Fire:
    width: int
    height: int
    palette: bytes
    sparks: tuple
    render_heat: int
    rising: bool
    draw_mode: int
    metadata: dict


def decode_fire(package, path, package_name):
    matches = [e for e in package.exports if package.object_path(e.index + 1, package_name) == path and package.class_name(e) == 'FireTexture']
    if len(matches) != 1:
        raise PackageError('expected one FireTexture: ' + path)
    export = matches[0]
    props, reader = properties(package, export)
    width, height = scalar(props, 'USize', 2), scalar(props, 'VSize', 2)
    if any(not isinstance(v, int) or not 1 <= v <= 256 or v & (v - 1) for v in (width, height)):
        raise PackageError('invalid byte-coordinate fire dimensions')
    if scalar(props, 'Format', 1, 0) != 0:
        raise PackageError('only P8 fire palettes are supported')
    for axis, size in (('U', width), ('V', height)):
        if scalar(props, axis + 'Bits', 1) != size.bit_length() - 1 or scalar(props, axis + 'Clamp', 2, size) != size:
            raise PackageError('fire dimensions disagree')
    palette_ref = scalar(props, 'Palette', 5)
    if not isinstance(palette_ref, int) or not 0 < palette_ref <= len(package.exports):
        raise PackageError('fire palette must be local')
    palette_export = package.exports[palette_ref - 1]
    if package.class_name(palette_export) != 'Palette':
        raise PackageError('fire palette has wrong class')
    _, palette_reader = properties(package, palette_export)
    if palette_reader.compact() != 256:
        raise PackageError('fire palette requires 256 colors')
    palette = palette_reader.take(1024)
    if palette_reader.offset != palette_reader.end:
        raise PackageError('unexplained fire palette bytes')
    # These v61 parametric textures store a single empty mip, then native sparks.
    if reader.compact() != 1 or reader.compact() != 0:
        raise PackageError('unsupported fire mip layout')
    if reader.unpack('iiBB') != (width, height, width.bit_length() - 1, height.bit_length() - 1):
        raise PackageError('fire mip header disagrees')
    count = reader.compact()
    if not 0 <= count <= 4096 or count != scalar(props, 'NumSparks', 2):
        raise PackageError('fire spark count disagrees')
    sparks = tuple(tuple(reader.take(8)) for _ in range(count))
    if reader.offset != reader.end:
        raise PackageError('unexplained fire native bytes')
    if any(s[0] > 28 or s[2] >= width or s[3] >= height for s in sparks):
        raise PackageError('invalid fire spark type or coordinates')
    heat, rising, mode = scalar(props, 'RenderHeat', 1), scalar(props, 'bRising', 3, False), scalar(props, 'DrawMode', 1, 0)
    if heat is None or mode not in range(5):
        raise PackageError('missing or invalid fire rendering properties')
    metadata = dict(path=path, export_index=export.index, width=width, height=height,
                    export_sha256=hashlib.sha256(package.data[export.offset:export.offset + export.size]).hexdigest(),
                    palette=package.object_path(palette_ref, package_name), palette_sha256=hashlib.sha256(palette).hexdigest(),
                    sparks=[dict(zip(('type', 'heat', 'x', 'y', 'byte_a', 'byte_b', 'byte_c', 'byte_d'), s)) for s in sparks],
                    properties=[dict(name=k[0], index=k[1], kind=v[0], structure=v[1], raw_hex=v[2].hex(), boolean=v[3]) for k, v in props.items()],
                    defaulted_properties=[k for k in ('bRising', 'DrawMode') if (k, 0) not in props])
    return Fire(width, height, palette, sparks, heat, rising, mode, metadata)


def render_fire(fire, *, frames=64, warmup=128, seed=0):
    """Deterministic heat advection preview; source palette/anchors, authored motion.

    Source byte_a..d are retained, not assigned unverified native meanings.
    Modes/sparks outside the bounded castle subset are deliberately rejected.
    """
    if not isinstance(frames, int) or not 2 <= frames <= 256 or not isinstance(warmup, int) or not 0 <= warmup <= 1024:
        raise ValueError('invalid fire preview duration')
    if fire.draw_mode not in (0, 1) or any(s[0] not in (4, 5, 8) for s in fire.sparks):
        raise ValueError('preview only supports Blaze, OzHasSpoken, BlazeLeft and Normal/Lathe')
    rng = random.Random(seed)
    width, height = fire.width, fire.height
    heat = bytearray(width * height)
    particles = []
    snapshots = []
    cooling = 1 + (255 - fire.render_heat) // 24
    for tick in range(warmup + frames * 2):
        for kind, strength, x, y, *_ in fire.sparks:
            if rng.random() < 0.7:
                spread = 0.5 if kind == 5 else 1.5
                vx = rng.uniform(-spread, spread) - (0.8 if kind == 8 else 0)
                particles.append([float(x), float(y), vx, rng.uniform(-1.5, -0.4), strength, rng.randrange(12, 28)])
            heat[y * width + x] = max(heat[y * width + x], int(strength * rng.uniform(0.6, 1.0)))
        alive = []
        for x, y, vx, vy, strength, age in particles:
            x += vx; y += vy if fire.rising else -vy
            strength = max(0, strength - cooling); age -= 1
            if 0 <= x < width and 0 <= y < height and age > 0 and strength > 0:
                i = int(y) * width + int(x)
                heat[i] = max(heat[i], strength)
                alive.append([x, y, vx, vy, strength, age])
        particles = alive
        output = bytearray(width * height)
        step = 1 if fire.rising else -1
        for y in range(height):
            below, further = y + step, y + step * 2
            if not (0 <= below < height and 0 <= further < height):
                continue
            row = y * width; other = below * width; distant = further * width
            for x in range(width):
                value = (heat[other + (x - 1) % width] + heat[other + x] + heat[other + (x + 1) % width] + heat[distant + x]) // 4
                output[row + x] = max(0, value - cooling)
        if fire.draw_mode == 1:
            for y in range(height):
                row = y * width
                for x in range(width // 2):
                    a, b = row + x, row + width - 1 - x
                    output[a] = output[b] = max(output[a], output[b])
        heat = output
        if tick >= warmup:
            snapshots.append(bytes(heat))
    # Crossfade two trajectories so the cycle joins the same trajectory at N.
    return [bytes(((frames - t) * b + t * a) // frames for a, b in zip(snapshots[t], snapshots[t + frames])) for t in range(frames)]


def atlas_tga(fire, frames, *, columns=8, padding=2, masked=True, wrap_padding=False):
    if not frames or not isinstance(columns, int) or columns <= 0 or len(frames) % columns or not isinstance(padding, int) or not 0 <= padding <= 16:
        raise ValueError('invalid fire atlas layout')
    if any(len(frame) != fire.width * fire.height for frame in frames):
        raise ValueError('fire frame dimensions differ')
    rows = len(frames) // columns
    cell_w, cell_h = fire.width + padding * 2, fire.height + padding * 2
    width, height = columns * cell_w, rows * cell_h
    if max(width, height) > 4096:
        raise ValueError('fire atlas exceeds bounded dimensions')
    pixels = bytearray(width * height)
    for index, frame in enumerate(frames):
        col, row = index % columns, index // columns
        if wrap_padding:
            for y in range(cell_h):
                start = (row * cell_h + y) * width + col * cell_w
                pixels[start:start + cell_w] = bytes(frame[((y - padding) % fire.height) * fire.width + (x - padding) % fire.width] for x in range(cell_w))
            continue
        for y in range(fire.height):
            start = (row * cell_h + padding + y) * width + col * cell_w + padding
            pixels[start:start + fire.width] = frame[y * fire.width:(y + 1) * fire.width]
    return tga_bytes(Texture(width, height, bytes(pixels), fire.palette, {}), masked=masked)
