"""Read bounded v61 Sound/Music payloads; optionally render IT with an explicit libxmp."""
import ctypes
import hashlib
import io
import math
from pathlib import Path
import struct
import sys
import wave

from .package61 import PackageError
from .texture61 import properties


def wave_info(data):
    if len(data) < 44 or data[:4] != b'RIFF' or data[8:12] != b'WAVE' or struct.unpack_from('<I', data, 4)[0] + 8 != len(data): raise PackageError('invalid complete RIFF/WAVE payload')
    try:
        with wave.open(io.BytesIO(data), 'rb') as sound:
            channels, width, rate, frames = sound.getnchannels(), sound.getsampwidth(), sound.getframerate(), sound.getnframes()
            if sound.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (1, 2) or not 8000 <= rate <= 96000 or not 0 < frames <= rate * 1800: raise PackageError('unsupported PCM wave profile')
            pcm = sound.readframes(frames)
            if len(pcm) != channels * width * frames: raise PackageError('truncated PCM frames')
    except (wave.Error, EOFError) as error: raise PackageError('invalid PCM wave') from error
    loops = []; offset = 12
    while offset + 8 <= len(data):
        kind, size = data[offset:offset + 4], struct.unpack_from('<I', data, offset + 4)[0]; start = offset + 8; end = start + size
        if end > len(data): raise PackageError('wave chunk outside payload')
        if kind == b'smpl':
            if size < 36: raise PackageError('truncated sample-loop header')
            count = struct.unpack_from('<I', data, start + 28)[0]
            if 36 + count * 24 > size: raise PackageError('truncated sample loops')
            for i in range(count):
                _, mode, first, last, fraction, plays = struct.unpack_from('<6I', data, start + 36 + i * 24)
                if mode != 0 or fraction or not 0 <= first <= last < frames: raise PackageError('unsupported sample loop')
                loops.append(dict(start_frame=first, end_frame_inclusive=last, play_count=plays))
        offset = end + size % 2
    if offset not in (len(data), len(data) + 1): raise PackageError('unexplained wave tail')
    return dict(channels=channels, sample_width=width, sample_rate=rate, frames=frames, duration_seconds=frames / rate, pcm_sha256=hashlib.sha256(pcm).hexdigest(), sample_loops=loops)


def decode_audio(package, path, package_name, kind):
    if kind not in ('Sound', 'Music'): raise ValueError('unsupported audio class')
    matches = [e for e in package.exports if package.class_name(e) == kind and package.object_path(e.index + 1, package_name) == path]
    if len(matches) != 1: raise PackageError('expected one audio export: ' + path)
    export = matches[0]; props, reader = properties(package, export)
    if props: raise PackageError('tagged audio properties are unsupported')
    file_type = package.name(reader.compact()).lower(); size = reader.compact()
    if not 0 < size <= 32 * 1024 * 1024: raise PackageError('invalid audio payload size')
    data = reader.take(size)
    if reader.offset != reader.end: raise PackageError('unexplained audio native bytes')
    info = dict(path=path, kind=kind, file_type=file_type, export_index=export.index, payload_sha256=hashlib.sha256(data).hexdigest(), export_sha256=hashlib.sha256(package.data[export.offset:export.offset + export.size]).hexdigest())
    if kind == 'Sound':
        if file_type != 'wav': raise PackageError('only source PCM WAVE sounds are supported')
        info.update(wave_info(data))
    elif file_type != 'it' or len(data) < 192 or data[:4] != b'IMPM': raise PackageError('only source Impulse Tracker music is supported')
    return data, info


class _Sequence(ctypes.Structure):
    _fields_ = [('entry_point', ctypes.c_int), ('duration', ctypes.c_int)]


class _ModuleInfo(ctypes.Structure):
    _fields_ = [('md5', ctypes.c_ubyte * 16), ('vol_base', ctypes.c_int), ('mod', ctypes.c_void_p), ('comment', ctypes.c_char_p), ('num_sequences', ctypes.c_int), ('seq_data', ctypes.POINTER(_Sequence))]


def render_it(data, library_path, *, sample_rate=48000):
    """Use only a caller-selected installed 4.6 libxmp; no library search or install."""
    if not Path(library_path).is_file() or sys.byteorder != 'little': raise ValueError('explicit compatible libxmp path required')
    if data[:4] != b'IMPM' or not 192 <= len(data) <= 32 * 1024 * 1024 or sample_rate not in (44100, 48000): raise ValueError('unsupported tracker rendering input')
    library = ctypes.CDLL(str(Path(library_path).resolve()))
    version = ctypes.c_char_p.in_dll(library, 'xmp_version').value.decode('ascii')
    if not version.startswith('4.6.'): raise ValueError('only libxmp 4.6 ABI is admitted')
    for name, args, result in [('xmp_create_context', [], ctypes.c_void_p), ('xmp_free_context', [ctypes.c_void_p], None), ('xmp_load_module_from_memory', [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long], ctypes.c_int), ('xmp_release_module', [ctypes.c_void_p], None), ('xmp_get_module_info', [ctypes.c_void_p, ctypes.POINTER(_ModuleInfo)], None), ('xmp_start_player', [ctypes.c_void_p, ctypes.c_int, ctypes.c_int], ctypes.c_int), ('xmp_play_buffer', [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int], ctypes.c_int), ('xmp_end_player', [ctypes.c_void_p], None)]:
        function = getattr(library, name); function.argtypes = args; function.restype = result
    context = library.xmp_create_context(); loaded = playing = False
    if not context: raise RuntimeError('tracker context creation failed')
    try:
        source = ctypes.create_string_buffer(data)
        if library.xmp_load_module_from_memory(context, source, len(data)) != 0: raise RuntimeError('tracker decode failed')
        loaded = True; info = _ModuleInfo(); library.xmp_get_module_info(context, ctypes.byref(info))
        if info.num_sequences != 1 or info.seq_data[0].entry_point != 0 or not 0 < info.seq_data[0].duration <= 1800000: raise ValueError('unsupported music sequences or duration')
        frames = math.ceil(info.seq_data[0].duration * sample_rate / 1000)
        if library.xmp_start_player(context, sample_rate, 0) != 0: raise RuntimeError('tracker start failed')
        playing = True; pcm = bytearray(); block = sample_rate // 10 * 4; buffer = ctypes.create_string_buffer(block)
        for _ in range(math.ceil(frames * 4 / block)):
            result = library.xmp_play_buffer(context, buffer, block, 1)
            if result not in (0, -1): raise RuntimeError('tracker rendering failed')
            pcm.extend(buffer.raw)
        pcm = bytes(pcm[:frames * 4]); output = io.BytesIO()
        with wave.open(output, 'wb') as sound: sound.setnchannels(2); sound.setsampwidth(2); sound.setframerate(sample_rate); sound.writeframes(pcm)
        if not any(pcm): raise RuntimeError('tracker rendered silence')
        return output.getvalue(), dict(decoder='libxmp', decoder_version=version, library_sha256=hashlib.sha256(Path(library_path).read_bytes()).hexdigest(), **wave_info(output.getvalue()))
    finally:
        if playing: library.xmp_end_player(context)
        if loaded: library.xmp_release_module(context)
        library.xmp_free_context(context)


def compare_pcm(source, readback):
    """Require matching layout and a bounded signed-16-bit import rounding error."""
    from array import array
    first, second = wave_info(source), wave_info(readback)
    if any(first[k] != second[k] for k in ('channels', 'sample_rate', 'frames')): raise PackageError('PCM readback layout differs')
    def samples(data):
        with wave.open(io.BytesIO(data), 'rb') as sound:
            raw = sound.readframes(sound.getnframes())
            if sound.getsampwidth() == 1: return array('h', ((v - 128) * 256 for v in raw))
            values = array('h', raw)
            if sys.byteorder != 'little': values.byteswap()
            return values
    a, b = samples(source), samples(readback); maximum = max((abs(x - y) for x, y in zip(a, b)), default=0)
    bound = 2 if first['sample_width'] == 1 else 1
    if maximum > bound: raise PackageError('PCM readback differs beyond source-bit-depth float conversion bound')
    return dict(source_pcm_sha256=first['pcm_sha256'], readback_pcm_sha256=second['pcm_sha256'], max_signed_16bit_sample_error=maximum, exact=maximum == 0, samples_checked=len(a))
