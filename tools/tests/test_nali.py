"""Synthetic Nali animation fixtures; no original game data is committed."""

from dataclasses import replace
import hashlib
import math
import struct

import pytest

from ue1_converter.nali69 import Sequence, TargetPackage69, decode_nali_mesh, read_sequences
from ue1_converter.nali_prepare import obj_frame, prepare
from ue1_converter.package61 import Package61, PackageError, Reader


def ci(value):
    negative = value < 0
    value = abs(value)
    result = bytearray([(128 if negative else 0) | (64 if value >= 64 else 0) | (value & 63)])
    value >>= 6
    while value:
        result.append((128 if value >= 128 else 0) | (value & 127))
        value >>= 7
    return bytes(result)


def fixture(*, bad_endpoint=False, bad_wedge=False, bad_triangle=False, bad_notify=False,
            bad_frame_box=False, bad_tail=False):
    names = ['None', 'Core', 'Class', 'LodMesh', 'Texture', 'Nali1', 'JNali1', 'Walk', 'Step', 'Default']
    n = lambda name: ci(names.index(name))
    name_data = b''.join(ci(len(s) + 1) + s.encode() + b'\0' + bytes(4) for s in names)
    imports = b''.join(n('Core') + n('Class') + bytes(4) + n(name) for name in ('LodMesh', 'Texture'))
    start = 60 + len(name_data) + len(imports)
    box = struct.pack('<ffffffB', 0, 0, 0, 20, 20, 20, 1)
    sphere = struct.pack('<ffff', 10, 10, 10, 20)
    body = bytearray(n('None') + box + sphere)

    def array(fmt, values, *, lazy=False):
        raw = ci(len(values)) + b''.join(struct.pack('<' + fmt, *(v if isinstance(v, tuple) else (v,))) for v in values)
        if lazy:
            body.extend(struct.pack('<i', start + len(body) + 4 + len(raw) + int(bad_endpoint)))
        body.extend(raw)

    array('I', [0, 1, 2, 3, 4, 5], lazy=True)
    array('HHHBBBBBBIi', [], lazy=True)
    body.extend(ci(1) + n('Walk') + n('Default') + struct.pack('<ii', 0, 2))
    body.extend(ci(1) + struct.pack('<f', math.nan if bad_notify else 0.25) + n('Step') + struct.pack('<f', 15))
    array('ii', [], lazy=True)
    body.extend(box + sphere)
    array('i', [], lazy=True)
    body.extend(ci(1) + ci(2))  # One local texture export.
    frame_box = struct.pack('<ffffffB', 0, 0, 0, -1, 20, 20, 1) if bad_frame_box else box
    body.extend(ci(2) + frame_box + box + ci(2) + sphere * 2)
    body.extend(struct.pack('<iiIIffffffiiiii', 3, 2, 0, 0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 0))
    array('f', [1])
    array('H', [0, 1, 2])
    array('H', [3])
    array('HHHH', [(0, 1, 1 if bad_triangle else 2, 0)])
    array('H', [0, 1, 2])
    array('HBB', [(0, 0, 0), (1, 255, 0), (9 if bad_wedge else 2, 0, 255)])
    array('Ii', [(0, 0)])
    array('HHHH', [])
    body.extend(struct.pack('<iifffiff', 3, 0, 1, 0, 1, 1, 0, 0) + ci(0) + struct.pack('<i', 0))
    if bad_tail:
        body.extend(b'?')
    texture = n('None')
    export_offset = start + len(body) + len(texture)
    exports = b''.join((ci(cls) + ci(0) + bytes(4) + n(name) + bytes(4) + ci(len(payload)) + ci(offset))
                       for cls, name, payload, offset in [(-1, 'Nali1', body, start), (-2, 'JNali1', texture, start + len(body))])
    header = struct.pack('<IHHIiiiiii', 0x9e2a83c1, 69, 0, 1, len(names), 60, 3, export_offset, 2, 60 + len(name_data))
    return header.ljust(60, b'\0') + name_data + imports + body + texture + exports + b'\xff' * 16


def test_bounded_export_reader_stops_after_required_prefix_and_keeps_v61_strict():
    raw = fixture()
    package = TargetPackage69(raw, {'Nali1', 'JNali1'}, minimum_exports=2)
    assert len(package.exports) == 2 and package.declared_export_count == 3
    with pytest.raises(PackageError): Package61(raw, allow_download_flag=True)
    with pytest.raises(PackageError): TargetPackage69(raw, {'Nali1', 'Missing'})
    with pytest.raises(PackageError): TargetPackage69(raw, {'Nali1', 'JNali1'}, minimum_exports=3)


def test_decode_full_two_frame_walk_preserves_indices_uvs_and_notifies():
    package = TargetPackage69(fixture(), {'Nali1', 'JNali1'})
    mesh = decode_nali_mesh(package, 'Nali1', 'UnrealShare')
    assert (mesh.vertex_count, mesh.frame_count) == (3, 2)
    assert mesh.frame(0) == ((0, 0, 0), (1, 0, 0), (2, 0, 0))
    assert mesh.frame(1) == ((3, 0, 0), (4, 0, 0), (5, 0, 0))
    assert mesh.sequences == (Sequence('Walk', 'Default', 0, 2, 15, ((0.25, 'Step'),)),)
    assert mesh.faces == ((0, 1, 2, 0),)
    assert mesh.wedges == ((0, 0, 0), (1, 255, 0), (2, 0, 255))
    assert mesh.source['texture_paths'] == ['UnrealShare.JNali1']
    assert mesh.source['package_sha256'] == hashlib.sha256(package.data).hexdigest()
    with pytest.raises(PackageError): mesh.frame(2)


@pytest.mark.parametrize('change', [{'bad_endpoint': True}, {'bad_wedge': True}, {'bad_triangle': True},
                                    {'bad_notify': True}, {'bad_frame_box': True}, {'bad_tail': True}])
def test_mesh_validation_rejects_malformed_evidence(change):
    with pytest.raises(PackageError):
        decode_nali_mesh(TargetPackage69(fixture(**change), {'Nali1', 'JNali1'}), 'Nali1', 'UnrealShare')


def test_obj_frames_keep_source_winding_uvs_and_only_apply_mesh_scale():
    mesh = decode_nali_mesh(TargetPackage69(fixture(), {'Nali1', 'JNali1'}), 'Nali1', 'UnrealShare')
    text = obj_frame(replace(mesh, scale=(2, 3, 4), origin=(10, 20, 30), rotation=(100, 200, 300)), 1).decode()
    assert 'v 6 0 0\nv 8 0 0\nv 10 0 0\n' in text
    assert 'vt 0 1\nvt 0.99609375 1\nvt 0 0.00390625\n' in text
    assert 'f 1/1 2/2 3/3\n' in text
    assert 'v 16' not in text  # Mesh origin is deliberately not applied.


def test_sequence_reader_rejects_out_of_range_and_nonfinite_rate():
    class Names:
        def name(self, index):
            return ('Walk', 'Default', 'Step')[index]
    def encoded(start, count, rate):
        return ci(1) + ci(0) + ci(1) + struct.pack('<ii', start, count) + ci(0) + struct.pack('<f', rate)
    for data in (encoded(2, 2, 15), encoded(0, 0, 15), encoded(0, 2, math.nan), encoded(0, 2, 0)):
        with pytest.raises(PackageError): read_sequences(Reader(data), Names(), 2)


def test_prepare_rejects_unpinned_package_before_creating_output(tmp_path):
    source = tmp_path / 'UnrealShare.u'
    source.write_bytes(fixture())
    output = tmp_path / 'Nali1'
    with pytest.raises(PackageError, match='differs'):
        prepare(source, output)
    assert not output.exists()
    output.mkdir()
    with pytest.raises(FileExistsError):
        prepare(source, output)
