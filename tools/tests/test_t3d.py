"""Authored synthetic exports only; no original game geometry is a test fixture."""

import hashlib
import json
from pathlib import Path

import pytest

from ue1_converter.__main__ import main
from ue1_converter.inspection import inspect_document
from ue1_converter.t3d import T3DError, number, parse_struct, parse_t3d, read_polygon


FIXTURE = Path(__file__).parent / "fixtures" / "inspection.t3d"


@pytest.fixture
def source():
    return FIXTURE.read_text()


def report(source):
    return inspect_document(parse_t3d(source), "Example.t3d", source.encode())


def test_preserves_source_order_values_and_unknown_properties(source):
    text = source.replace("\n", "\r\n")
    doc = parse_t3d(text)
    assert doc.source_text == text
    assert [a.attribute("Name") for a in doc.actors][:4] == [
        "ExampleInfo", "ExampleBrush", "ExampleReuse", "ExampleMover"]
    brush = doc.actors[1]
    assert brush.line == 6
    assert brush.property("CsgOper") == "CSG_Subtract"
    assert brush.property("Rotation") == "(Yaw=8192)"
    assert brush.property("PrePivot") == "(Z=-2.0)"
    assert 'A="spaces, commas = stay"' in brush.property("UnknownSetting")
    scale = parse_struct(brush.property("MainScale"), brush.line)
    assert [(a.name, a.value) for a in scale] == [
        ("Scale", "(X=2.0,Z=-1.0)"), ("SheerRate", "0.25"), ("SheerAxis", "SHEER_XY")]
    assert doc.actors[3].property("KeyPos(1)") == "(Z=-48.0)"
    assert doc.actors[3].property("KeyRot(1)") == "(Yaw=-1024)"
    assert doc.actors[4].property("Position") is None
    assert doc.actors[5].property("Rotation") == "(Yaw=-16384,Roll=2048)"
    assert '\\"quote\\"' in doc.actors[-1].property("Message")


def test_polygon_retains_winding_uv_vectors_pan_flags_and_link(source):
    model = parse_t3d(source).actors[1].children("Brush")[0]
    polygon = read_polygon(model.children("PolyList")[0].children("Polygon")[0])
    assert polygon.block.attribute("Item") == '"Example Panel"'
    assert polygon.block.attribute("Texture") == "DemoPkg.Stone.Block"
    assert polygon.block.attribute("Flags") == "32"
    assert polygon.block.attribute("Link") == "2"
    assert polygon.origin == (1, -2, 3)
    assert polygon.normal == (0, 0, 1)
    assert polygon.texture_u == (2, 0, 0)
    assert polygon.texture_v == (0, -4, 0)
    assert polygon.pan == (-7, 11)
    assert polygon.vertices == ((1, -2, 3), (5, -2, 3), (1, 6, 3))


def test_inventory_resolves_shared_models_without_duplicating_polygons(source):
    result = report(source)
    assert result["counts"]["actors"] == 8
    assert result["counts"]["source_polygons"] == 1
    assert result["counts"]["source_vertices"] == 3
    assert result["counts"]["shared_brush_instances"] == 2
    assert [b["geometry_status"] for b in result["brushes"]] == ["inline", "shared", "shared"]
    assert [b["csg_operation"] for b in result["brushes"]] == ["CSG_Subtract", "CSG_Add", None]
    assert result["brushes"][1]["definitions"][0]["actor"] == "ExampleBrush"
    refs = {(r["kind"], r["path"]): r["occurrences"] for r in result["references"]}
    assert refs["Texture", "DemoPkg.Stone.Block"] == 1
    assert refs["Model", "Example.ExampleModel"] == 3
    assert refs["Object", "Example.Unknown"] == 1
    assert refs["Music", "DemoMusic.Theme"] == 1


def test_camera_ambiguities_and_malformed_transform_are_visible(source):
    result = report(source)
    group = result["camera_groups"][0]
    assert group["duplicate_positions"] == {"7": ["CameraLater", "CameraAlternate"]}
    assert group["omitted_positions"] == 1
    assert [p["name"] for p in result["camera_points"]] == ["CameraFirst", "CameraLater", "CameraAlternate"]
    assert result["camera_points"][0]["position"] is None
    assert result["camera_points"][0]["location_specified"] == {"X": 10, "Y": -20, "Z": 30}
    assert result["camera_points"][1]["location_specified"] is None
    codes = [d["code"] for d in result["diagnostics"]]
    assert sorted(codes) == ["duplicate-camera-position", "invalid-transform-number", "omitted-camera-position"]
    invalid = next(d for d in result["diagnostics"] if d["code"] == "invalid-transform-number")
    assert "3e-05.0" in invalid["message"]
    assert invalid["actor"] == "ExampleReuse"
    assert any(p["value"] == "(X=3e-05.0)" for p in result["brushes"][1]["properties"])
    assert report(source) == result  # Stable report ordering and source identity.


def test_unresolved_and_ambiguous_models_are_not_chosen(source):
    missing = source.replace("Brush=Model'Example.ExampleModel'", "Brush=Model'Other.Unavailable'", 1)
    result = report(missing)
    assert result["brushes"][1]["geometry_status"] == "unresolved"
    assert "unbound-model-definition" in {d["code"] for d in result["diagnostics"]}
    actor = source[source.index("    Begin Actor Class=Brush Name=ExampleBrush"):source.index("    Begin Actor Class=Brush Name=ExampleReuse")]
    ambiguous = source.replace("End Map", actor.replace("Name=ExampleBrush", "Name=DuplicateDefinition") + "End Map")
    result = report(ambiguous)
    assert all(b["geometry_status"] == "unresolved" for b in result["brushes"])
    assert len(result["brushes"][1]["definitions"]) == 2


def test_all_malformed_components_and_duplicate_actor_identities_are_retained(source):
    source = source.replace("(X=3e-05.0)", "(X=3e-05.0,Y=-2e-07.0)")
    source = source.replace("Name=ExampleReuse", "Name=ExampleBrush")
    result = report(source)
    invalid = [d for d in result["diagnostics"] if d["code"] == "invalid-transform-number"]
    assert len(invalid) == 2
    assert "PrePivot.X" in invalid[0]["message"]
    assert "PrePivot.Y" in invalid[1]["message"]
    repeated = [d for d in result["diagnostics"] if d["code"] == "duplicate-actor-name"]
    assert [d["actor_index"] for d in repeated] == [1, 2]
    assert [b["actor_index"] for b in result["brushes"]] == [1, 2, 3]
    assert [b["name"] for b in result["brushes"]][:2] == ["ExampleBrush", "ExampleBrush"]


def test_reference_inventory_ignores_reference_shaped_string_literals(source):
    source = source.replace('"Synthetic courtyard, not a game export"',
                            '"A literal Sound\'Fake.NotAnAsset\'"')
    result = report(source)
    assert not any(r["path"] == "Fake.NotAnAsset" for r in result["references"])
    assert any(r["path"] == "DemoSound.Mechanisms.Door" for r in result["references"])


@pytest.mark.parametrize("source,message,line", [
    ("", "missing Map", 1),
    ("Begin Map\nEnd Actor", "unexpected End Actor", 2),
    ("Begin Map\nBegin Actor Class=Brush Name=A", "unclosed Actor", 2),
    ("Begin Map\nBegin Object Name=NewSyntax", "unsupported Object", 2),
    ("Begin Map\nBegin Actor Name=A", "requires Class", 2),
    ("Begin Map\nBegin Actor Class=Brush Name=A Name=B", "duplicate header", 2),
    ("Begin Map\nEnd Map\nBegin Map", "unsupported Map", 3),
    ('Begin Map\nBegin Actor Class=Light Name=A\nTag="unterminated', "unterminated quote", 3),
    ("Begin Map\nLocation=(X=1)", "unsupported content", 2),
])
def test_structure_errors_have_source_lines(source, message, line):
    with pytest.raises(T3DError, match=message) as error:
        parse_t3d(source)
    assert error.value.line == line


def test_duplicate_properties_are_retained_but_inspection_rejects_ambiguity(source):
    text = source.replace("Position=7", "Position=7\n        Position=8", 1)
    document = parse_t3d(text)
    assert [p.value for p in document.actors[5].properties if p.name == "Position"] == ["7", "8"]
    with pytest.raises(T3DError, match="duplicate actor property"):
        report(text)


@pytest.mark.parametrize("token", ["3e-05.0", "nan", "Infinity", "1e999", "1,2", "1junk"])
def test_numeric_reader_does_not_repair_or_accept_nonfinite_values(token):
    with pytest.raises(T3DError):
        number(token, 9)


@pytest.mark.parametrize("before,after,message", [
    ("Vertex +00001.000000,+00006.000000,+00003.000000", "", "at least three"),
    ("Pan U=-7 V=11", "Pan U=-7 U=11", "requires U and V"),
    ("Normal   +00000.000000,+00000.000000,+00001.000000", "", "exactly one Normal"),
    ("TextureU +00002.000000,+00000.000000,+00000.000000", "TextureU 1,2", "three components"),
    ("Pan U=-7 V=11", "SmoothingGroup 4", "unsupported polygon record"),
])
def test_malformed_polygon_fails_instead_of_losing_geometry(source, before, after, message):
    with pytest.raises(T3DError, match=message):
        report(source.replace(before, after))


def test_cli_output_safety_and_source_hash(source, tmp_path, capsys):
    original = tmp_path / "Example.t3d"
    original.write_bytes(source.replace("\n", "\r\n").encode())
    baseline = original.read_bytes()
    output = tmp_path / "Example.inspection.json"
    assert main(["inspect-t3d", str(original), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["source"]["sha256"] == hashlib.sha256(baseline).hexdigest()
    assert result["source"]["byte_count"] == len(baseline)
    assert original.read_bytes() == baseline
    previous = output.read_bytes()
    assert main(["inspect-t3d", str(original), "-o", str(output)]) == 2
    assert output.read_bytes() == previous
    assert main(["inspect-t3d", str(original), "-o", str(output), "--force"]) == 0
    assert output.read_bytes() == previous
    alias = tmp_path / "alias.t3d"
    alias.symlink_to(original)
    for destination in (original, alias):
        assert main(["inspect-t3d", str(original), "-o", str(destination), "--force"]) == 2
    assert original.read_bytes() == baseline
    assert "must not overwrite" in capsys.readouterr().err


def test_cli_error_does_not_create_report_and_explicit_codec_works(source, tmp_path, capsys):
    original = tmp_path / "Example.t3d"
    output = tmp_path / "Example.inspection.json"
    original.write_text("Begin Map\nEnd Actor")
    assert main(["inspect-t3d", str(original), "-o", str(output)]) == 2
    assert not output.exists()
    assert "line 2" in capsys.readouterr().err
    original.write_bytes(source.replace("Synthetic courtyard", "Łąka").encode("cp1250"))
    assert main(["inspect-t3d", str(original), "--encoding", "cp1250"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source"]["encoding"] == "cp1250"
    assert main(["inspect-t3d", str(original)]) == 2
