"""Bounded v61 WetTexture records and an independently authored horizontal warp."""
from dataclasses import dataclass
import hashlib
import math

from .package61 import PackageError
from .texture61 import properties, scalar


@dataclass(frozen=True)
class Wet:
    width: int
    height: int
    source_texture: str
    palette_path: str
    wave_amp: int
    drops: tuple
    metadata: dict


def decode_wet(package, path, package_name):
    matches = [e for e in package.exports if package.object_path(e.index + 1, package_name) == path and package.class_name(e) == 'WetTexture']
    if len(matches) != 1: raise PackageError('expected one WetTexture: ' + path)
    export = matches[0]; props, reader = properties(package, export)
    width, height = scalar(props, 'USize', 2), scalar(props, 'VSize', 2)
    if any(not isinstance(v, int) or not 2 <= v <= 256 or v & (v - 1) for v in (width, height)):
        raise PackageError('invalid bounded water dimensions')
    if scalar(props, 'Format', 1, 0) != 0: raise PackageError('only P8 wet textures are supported')
    for axis, size in (('U', width), ('V', height)):
        if scalar(props, axis + 'Bits', 1) != size.bit_length() - 1 or scalar(props, axis + 'Clamp', 2, size) != size:
            raise PackageError('water dimensions disagree')
    if reader.compact() != 1 or reader.compact() != 0:
        raise PackageError('unsupported water mip layout')
    if reader.unpack('iiBB') != (width, height, width.bit_length() - 1, height.bit_length() - 1):
        raise PackageError('water mip header disagrees')
    if reader.offset != reader.end: raise PackageError('unexplained water native bytes')
    count = scalar(props, 'NumDrops', 2)
    if not isinstance(count, int) or not 0 <= count <= 128:
        raise PackageError('unsupported water drop count')
    stored = {index: value for (name, index), value in props.items() if name == 'Drops'}
    if set(stored) != set(range(count)): raise PackageError('water drop indices disagree')
    drops = []
    for index in range(count):
        kind, structure, raw, _ = stored[index]
        if kind != 10 or structure != 'ADrop' or len(raw) != 8:
            raise PackageError('unsupported water drop record')
        drop = tuple(raw)
        if drop[0] > 19 or drop[2] >= width or drop[3] >= height:
            raise PackageError('invalid water drop type or coordinates')
        drops.append(drop)
    refs = [scalar(props, k, 5) for k in ('SourceTexture', 'Palette')]
    if any(not isinstance(r, int) or r == 0 for r in refs): raise PackageError('water source image/palette missing')
    source, palette = [package.object_path(r, package_name) for r in refs]
    wave_amp = scalar(props, 'WaveAmp', 1)
    if wave_amp is None: raise PackageError('water amplitude missing')
    metadata = dict(path=path, width=width, height=height, source_texture=source, palette=palette,
                    export_index=export.index, export_sha256=hashlib.sha256(package.data[export.offset:export.offset + export.size]).hexdigest(),
                    drops=[dict(zip(('type', 'depth', 'x', 'y', 'byte_a', 'byte_b', 'byte_c', 'byte_d'), d)) for d in drops],
                    properties=[dict(name=k[0], index=k[1], kind=v[0], structure=v[1], raw_hex=v[2].hex(), boolean=v[3]) for k, v in props.items()])
    return Wet(width, height, source, palette, wave_amp, tuple(drops), metadata)


def water_frame(wet, texture, phase, *, displacement=16.0):
    """Periodic horizontal-only source-pixel resampling; no native solver equivalence.

    Raw source X/Y coordinates anchor authored oscillators. Native simulation-grid
    scaling and byte_a..d behavior are deliberately not inferred.
    """
    if not math.isfinite(phase) or not math.isfinite(displacement) or not 0 <= displacement <= 32:
        raise ValueError('invalid water preview phase/displacement')
    if (wet.width, wet.height) != (texture.width, texture.height): raise ValueError('water source dimensions differ')
    if any(d[0] != 12 for d in wet.drops): raise ValueError('preview only supports HorizontalOsc drops')
    width, height = wet.width, wet.height
    strength = displacement * wet.wave_amp / 255
    envelopes = [[((1 + math.cos(math.tau * (x - d[2]) / width)) / 2) ** 2 * d[1] / 255 for x in range(width)] for d in wet.drops]
    phase %= 1.0
    output = bytearray(width * height)
    for y in range(height):
        waves = [math.sin(math.tau * (4 * (y - d[3]) / height - (1 + i % 3) * phase)) for i, d in enumerate(wet.drops)]
        row = y * width
        for x in range(width):
            offset = round(strength * sum(e[x] * wave for e, wave in zip(envelopes, waves)))
            output[row + x] = texture.pixels[row + (x + offset) % width]
    return bytes(output)
