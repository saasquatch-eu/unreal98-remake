# Python source inspection

Use the repository-local Python environment. The tool has no UE editor dependency
and does not install or call an exporter, change a map, or generate UE5 content.

```sh
.venv/bin/python -m ue1_converter inspect-t3d \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  --output data/converted/Unreal/Maps/Unreal/Unreal.inspection.json
bash scripts/run-tests.sh
```

Output directories must already exist. Existing reports require `--force` to
replace. Omitting `--output` prints JSON; its contents still belong in private
storage. The default text codec is UTF-8; use `--encoding` explicitly for another
known export encoding. Decoding errors are never silently replaced.

Success exits 0 even when the report contains source warnings. Invalid structure,
unsupported geometry records, malformed polygon vectors, decoding failures, and
file errors exit 2. Source warnings must be resolved before conversion. The CLI
rejects writing over its input, including an existing symlink or hardlink alias.

`ue1_converter.t3d.parse_t3d(text)` returns a document with the complete source
text and ordered blocks, header attributes, and raw actor property assignments.
Source lines are one-based. `read_polygon(block)` reads vertices and texture
basis/pan data without changing winding, coordinates, or mapping units. Header
flags, link values, and resource spelling remain available on the polygon block.
`parse_struct` reads specified fields without supplying omitted defaults.

The supported export subset is Map → Actor → Brush → PolyList → Polygon, with
single-line properties. Unknown actor properties are retained. Unsupported block
types and unknown polygon records produce errors rather than being discarded.
This is not a parser for arbitrary UE1/UE5 text objects. The inspection command
does not round-trip edited exports, apply transforms, repair malformed numbers,
evaluate CSG, triangulate, or reconstruct camera behavior. The separate coordinate
audit below applies a documented subset of published brush defaults.

`inspection.inspect_document` produces the inventory described in
`../schemas/t3d-inspection-v1.md`. Real-map reports stay under ignored
`data/converted/`; only manually authored synthetic fixtures belong in tests.
The reserved extract/convert/validate directories remain unused.

## Brush-coordinate validation

```sh
.venv/bin/python -m ue1_converter validate-brushes \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  --package "$HOME/Library/Application Support/Unreal/Maps/Unreal.unr" \
  --output data/converted/Unreal/Maps/Unreal/Unreal.brush-audit.json
```

Use `--force` to replace the report. This command reads the original binary map;
it never rewrites it, runs UCC, or changes an application. It requires matching
map/export hashes from the existing source-baseline and export-summary sidecars.
Use `--baseline` and `--export-summary` to specify those files explicitly.
The input map's resolved path must be present in the baseline. Every input,
including the provenance sidecars, is protected against output aliasing.

`package61` reads tables and selected Vector properties only for version 61,
licensee zero, flags zero. It rejects a selected object with a state frame or
array tag, ambiguous object names, omitted vectors, bad sizes, and out-of-range
data. It is not a general Unreal package converter. Binary values replace only
malformed pivot components in memory, with original tokens and exact byte
offsets recorded separately in the audit. Strict T3D parsing remains unchanged.

`brush_math` supports pivots, the published legacy rotator grid, main/post scales,
inverse transforms, mirrored winding detection, and inverse-transpose normal/UV
transforms. Nonzero shear and zero scale fail explicitly. TempScale is not baked
into model coordinates. Python double precision is not bit-exact native UE1 math.

`solid_reference` is a bounded, axis-aligned occupancy/volume oracle for authored
synthetic examples. Its explicit initial-solid setting and ordered operations
test subtraction, restoration, overlap, and idempotence. It does not consume map
brushes, implement BSP flags/tolerances, or produce mesh boundaries. Full castle
CSG evaluation and UE5 mesh generation are still unimplemented.
