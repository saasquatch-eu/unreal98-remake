"""Synthetic package bytes and analytic solids; no original game data."""

import hashlib
import json
import math
from pathlib import Path
import struct

import pytest

from ue1_converter.brush_audit import audit_brushes
from ue1_converter.__main__ import main
from ue1_converter.brush_math import BrushTransform, cross, dot, from_actor, matvec, rotation_matrix
from ue1_converter.package61 import Package61, PackageError, Reader
from ue1_converter.solid_reference import Box, Operation, is_solid, solid_volume
from ue1_converter.t3d import T3DError, parse_t3d


def compact(value):
    magnitude = abs(value)
    out = bytearray([(128 if value < 0 else 0) | (64 if magnitude >= 64 else 0) | (magnitude & 63)])
    magnitude >>= 6
    while magnitude:
        out.append((128 if magnitude >= 128 else 0) | (magnitude & 127))
        magnitude >>= 7
    return bytes(out)


def synthetic_package(*, flags=0, duplicate=False, property_data=None):
    names = ["None", "Core", "Class", "Brush", "ExampleReuse", "PrePivot", "Vector", "bHidden"]
    name_data = b"".join(n.encode() + b"\0" + bytes(4) for n in names)
    imports = compact(1) + compact(2) + bytes(4) + compact(3)
    if property_data is None:
        # Bool value is in the high tag bit, followed by a native Vector struct.
        property_data = compact(7) + b"\x83" + compact(5) + b"\x3a" + compact(6) + struct.pack("<fff", 3e-5, 0, -2) + compact(0)
    names_offset = 60
    imports_offset = names_offset + len(name_data)
    payload_offset = imports_offset + len(imports)
    exports_offset = payload_offset + len(property_data)
    export = compact(-1) + compact(0) + bytes(4) + compact(4) + struct.pack("<I", flags)
    export += compact(len(property_data)) + compact(payload_offset)
    header = struct.pack("<IHHIiiiiii", 0x9E2A83C1, 61, 0, 0, len(names), names_offset,
                         2 if duplicate else 1, exports_offset, 1, imports_offset)
    return header.ljust(60, b"\0") + name_data + imports + property_data + export * (2 if duplicate else 1)


@pytest.mark.parametrize("value", [0, 63, 64, -1, -8191, 8192, 2**20, 2**27, 2**31-1, -2**31])
def test_compact_indices(value):
    data = compact(value)
    reader = Reader(data)
    assert reader.compact() == value
    assert reader.offset == len(data)


def test_binary_vector_bytes_offsets_and_boolean_tag():
    data = synthetic_package()
    proof = Package61(data).vector_property("ExampleReuse", "Brush", "PrePivot")
    assert proof.export_index == 0
    assert proof.values == struct.unpack("<fff", struct.pack("<fff", 3e-5, 0, -2))
    assert data[proof.property_offset:proof.property_offset+12] == proof.raw
    assert proof.raw[:4] == struct.pack("<f", 3e-5)


@pytest.mark.parametrize("change", ["version", "table", "truncated", "negative-index", "state-frame", "array", "nonfinite", "duplicate", "missing"])
def test_binary_reader_refuses_unproven_or_invalid_data(change):
    data = bytearray(synthetic_package())
    if change == "version": struct.pack_into("<H", data, 4, 69)
    elif change == "table": struct.pack_into("<i", data, 12, 1000000)
    elif change == "truncated": data = data[:65]
    elif change == "negative-index": data = bytearray(synthetic_package(property_data=b"\x81"))
    elif change == "state-frame": data = bytearray(synthetic_package(flags=0x02000000))
    elif change == "array": data = bytearray(synthetic_package(property_data=compact(5)+b"\xba"+compact(6)+bytes(12)+b"\0"))
    elif change == "nonfinite": data = bytearray(synthetic_package(property_data=compact(5)+b"\x3a"+compact(6)+struct.pack("<fff", math.inf,0,0)+b"\0"))
    elif change == "duplicate": data = bytearray(synthetic_package(duplicate=True))
    elif change == "missing": data = bytearray(synthetic_package(property_data=b"\0"))
    with pytest.raises(PackageError):
        Package61(bytes(data)).vector_property("ExampleReuse", "Brush", "PrePivot")


def test_binary_reader_bounds_and_index_overflow():
    with pytest.raises(PackageError): Reader(b"\x40").compact()
    with pytest.raises(PackageError): Reader(b"\x7f\xff\xff\xff\xff").compact()
    with pytest.raises(PackageError): Reader(b"x", 2)


def test_pivot_main_rotation_post_location_order_and_round_trip():
    transform = BrushTransform(location=(10,20,30), pivot=(1,0,1), rotation=(0,16384,0),
                               main_scale=(2,-3,4), post_scale=(5,6,7))
    # Subtract pivot -> (2,2,4); main -> (4,-6,16); yaw -> (6,4,16).
    assert transform.point((3,2,5)) == pytest.approx((40,44,142))
    assert transform.local_point((40,44,142)) == pytest.approx((3,2,5))
    assert transform.reverses_winding


def test_pitch_roll_signs_and_legacy_angle_grid():
    assert matvec(rotation_matrix((16384,0,0)),(1,0,0)) == pytest.approx((0,0,1),abs=1e-12)
    assert matvec(rotation_matrix((0,0,16384)),(0,1,0)) == pytest.approx((0,0,-1),abs=1e-12)
    assert matvec(rotation_matrix((0,3,0)),(1000,0,0)) == pytest.approx((1000,0,0))
    step = math.tau / 16384
    assert matvec(rotation_matrix((0,4,0)),(1000,0,0)) == pytest.approx((1000*math.cos(step),1000*math.sin(step),0))
    assert matvec(rotation_matrix((0,-1,0)),(1000,0,0)) == pytest.approx((1000*math.cos(step),-1000*math.sin(step),0))


def test_mixed_rotation_round_trip_normal_and_texture_covectors():
    transform = BrushTransform(location=(7,-8,9),pivot=(-1,3,2),rotation=(8192,12345,-4096),
                               main_scale=(-2,3,0.5),post_scale=(4,0.75,6))
    origin, point = (2,4,6), (7,-3,2)
    assert transform.local_point(transform.point(point)) == pytest.approx(point)
    for uv, pan in [((2,0,-1),13), ((0,-4,3),-7)]:
        delta = tuple(p-o for p,o in zip(point,origin))
        world_delta = tuple(p-o for p,o in zip(transform.point(point),transform.point(origin)))
        assert dot(transform.covector(uv),world_delta)+pan == pytest.approx(dot(uv,delta)+pan)
    # An original plane normal must stay perpendicular to its transformed tangent.
    normal = transform.normal((0,0,1))
    tangent = matvec(transform.linear,(1,2,0))
    assert dot(normal,tangent) == pytest.approx(0,abs=1e-12)
    assert dot(normal,normal) == pytest.approx(1)


def test_mirror_requires_reversing_polygon_winding():
    transform = BrushTransform(main_scale=(-2,3,4))
    a,b,c = [transform.point(p) for p in [(0,0,0),(1,0,0),(0,1,0)]]
    raw_normal = cross(tuple(y-x for x,y in zip(a,b)), tuple(y-x for x,y in zip(a,c)))
    assert dot(raw_normal,transform.normal((0,0,1))) < 0
    corrected_normal = cross(tuple(y-x for x,y in zip(a,c)), tuple(y-x for x,y in zip(a,b)))
    assert dot(corrected_normal,transform.normal((0,0,1))) > 0


def test_sparse_published_defaults_temp_scale_and_strict_numeric_tokens():
    actor=parse_t3d('''Begin Map
Begin Actor Class=Brush Name=Synthetic
MainScale=(Scale=(X=2),SheerAxis=SHEER_ZX)
TempScale=(Scale=(X=99,Y=99,Z=99))
Rotation=(Yaw=16384)
PrePivot=(X=3e-05.0)
End Actor
End Map''').actors[0]
    with pytest.raises(T3DError): from_actor(actor)
    transform=from_actor(actor,{"X":3e-5})
    assert transform.main_scale == (2,1,1)
    assert transform.post_scale == (1,1,1)
    assert transform.point((1,0,0)) == pytest.approx((0,1.99994,0),abs=1e-12)


@pytest.mark.parametrize("value", ["(SheerRate=0.25)","(Scale=(X=0))","(Mystery=1)"])
def test_unvalidated_transform_cases_fail(value):
    actor=parse_t3d(f"Begin Map\nBegin Actor Class=Brush Name=A\nMainScale={value}\nEnd Actor\nEnd Map").actors[0]
    with pytest.raises(ValueError): from_actor(actor)


def test_subtractive_world_room_with_restored_pillar_and_cut_opening():
    window=Box((0,0,0),(10,10,10))
    room=Box((1,1,1),(9,9,9))
    pillar=Box((4,4,1),(6,6,9))
    opening=Box((4,4,4),(6,6,6))
    ops=(Operation("CSG_Subtract",room),Operation("CSG_Add",pillar),Operation("CSG_Subtract",opening))
    assert solid_volume(window,ops,initial_solid=True) == 1000-512+32-8
    assert is_solid((0.5,0.5,0.5),ops,initial_solid=True)
    assert not is_solid((2,2,2),ops,initial_solid=True)
    assert is_solid((5,5,3),ops,initial_solid=True)
    assert not is_solid((5,5,5),ops,initial_solid=True)
    assert solid_volume(window,tuple(reversed(ops)),initial_solid=True) == 1000-512


def test_overlapping_solids_idempotence_and_finite_window_clipping():
    window=Box((0,0,0),(4,4,4))
    left=Operation("CSG_Add",Box((-1,0,0),(3,4,4)))
    right=Operation("CSG_Add",Box((1,0,0),(5,4,4)))
    assert solid_volume(window,(left,right),initial_solid=False) == 64
    assert solid_volume(window,(left,left),initial_solid=False) == 48
    cut=Operation("CSG_Subtract",Box((1,0,0),(3,4,4)))
    assert solid_volume(window,(cut,cut),initial_solid=True) == 32
    with pytest.raises(ValueError): Operation("CSG_Intersect",window)
    with pytest.raises(ValueError): Box((0,0,0),(0,1,1))


def test_audit_checksum_binding_and_separate_binary_evidence():
    source=(Path(__file__).parent/'fixtures/inspection.t3d').read_text().replace('SheerRate=0.25','SheerRate=0').encode()
    original=source
    package=synthetic_package()
    args=(source,package,'Example.t3d',hashlib.sha256(source).hexdigest(),hashlib.sha256(package).hexdigest())
    audit=audit_brushes(*args)
    assert audit['counts']['corrected_components'] == 1
    proof=audit['numeric_evidence'][0]
    assert proof['original_token'] == '3e-05.0'
    assert proof['value'] == struct.unpack('<f',struct.pack('<f',3e-5))[0]
    assert proof['little_endian_float32_hex'] == struct.pack('<f',3e-5).hex()
    assert source == original
    assert audit['counts']['brush_instances'] == 3
    with pytest.raises(ValueError,match='checksum'):
        audit_brushes(source+b'\n',*args[1:])


def test_brush_audit_cli_protects_every_input_and_requires_matching_provenance(tmp_path, capsys):
    source=tmp_path/'Example.t3d'
    source.write_text((Path(__file__).parent/'fixtures/inspection.t3d').read_text().replace('SheerRate=0.25','SheerRate=0'))
    package=tmp_path/'Example.unr'
    package.write_bytes(synthetic_package())
    baseline=source.with_suffix('.source-baseline.json')
    summary=source.with_suffix('.export-summary.json')
    baseline.write_text(json.dumps({str(package.resolve()):hashlib.sha256(package.read_bytes()).hexdigest()}))
    summary.write_text(json.dumps({'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}))
    command=['validate-brushes',str(source),'--package',str(package)]
    output=tmp_path/'Example.brush-audit.json'
    assert main(command+['-o',str(output)]) == 0
    assert json.loads(output.read_text())['counts']['corrected_components'] == 1
    originals={p:p.read_bytes() for p in (source,package,baseline,summary)}
    for p in originals:
        assert main(command+['-o',str(p),'--force']) == 2
        assert p.read_bytes() == originals[p]
    alias=tmp_path/'package-alias.unr'
    alias.hardlink_to(package)
    assert main(command+['-o',str(alias),'--force']) == 2
    package.write_bytes(package.read_bytes()+b'changed')
    assert main(command+['-o',str(output),'--force']) == 2
    assert 'checksum' in capsys.readouterr().err


def test_rotator_values_must_fit_source_integer_representation():
    with pytest.raises(ValueError): BrushTransform(rotation=(0,2**10000,0))
    with pytest.raises(ValueError): BrushTransform(rotation=(0,1.5,0))
