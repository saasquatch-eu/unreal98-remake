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
brushes, implement BSP flags/tolerances, or produce mesh boundaries. A replacement
brush-order CSG evaluator and UE5 asset creation remain unimplemented; the next
section describes extraction of already evaluated original geometry.

## Original evaluated BSP extraction

```sh
.venv/bin/python -m ue1_converter extract-bsp \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  --package "$HOME/Library/Application Support/Unreal/Maps/Unreal.unr" \
  --output-dir data/converted/Unreal/Maps/Unreal/geometry
```

The destination directory must not exist; choose a new name for a repeat run.
This command uses the same map/export provenance sidecars as `validate-brushes`.
It writes the classified `<Map>.geometry.json` and untextured `<Map>_ue5.obj`.
No export, original map, existing directory, app, or UE5 project asset is replaced.
Detailed outputs remain in ignored local storage.

`native_bsp` follows the Level's serialized model reference, then validates the
v61 geometry-table counts, object types, vertex spans, references, graph cycles,
zones, and exact consumed sizes. Unused legacy vertex-pool slots can contain
stale indices: these are counted, while every referenced point is bounds-checked.
Lighting, hulls, gameplay, other package versions, and native runtime behavior
are not reconstructed. The brush sequence is not evaluated by a new CSG engine.

Triangulation preserves ordinary collinear boundary corners and checks projected
area. Duplicate projected corners and zero-width collinear reversals can be
omitted from triangles; original boundaries and omitted corner indices remain
in the JSON. Unsafe boundaries fail explicitly. Surface UVs remain in texels,
without guessed texture dimensions. The diagnostic OBJ contains no normalized UVs.

Optional `tools/preview/render_geometry.py` uses Pillow and NumPy to render a CPU
clay preview. These libraries already exist in the workstation's bundled Python;
they were not installed into `.venv` and are not required by the extraction CLI.
Use an interpreter where they are available; the script never installs anything:

```sh
python tools/preview/render_geometry.py <Map>.geometry.json --output overview.png
python tools/preview/render_geometry.py <Map>.geometry.json \
  --sample InterpolationPoint0 --output camera0.png
```

The preview uses a fixed 75-degree diagnostic field of view, not a verified
original camera FOV. An offline preview is not an Unreal Editor screenshot. Original textures,
lighting, transparency, sky behavior, collision, and playback are not established.

## Modern intro lighting

`python -m ue1_converter.lighting_prepare` prepares lossless spatial render chunks
and a source-position light inventory from the checked material bundle and map.
Use `tools/editor/apply_lumen_lighting.py` only on the saved material baseline;
`verify_lumen_lighting.py` checks the resulting saved map, source geometry, UVs,
materials, Nanite fallbacks and renderer/light settings. See
[the lighting checkpoint](../docs/milestones/010-lumen-lighting.md) for commands,
backups, Mac rendering choices and unfinished source effects.

## Animated flame preview

`python -m ue1_converter.fire_prepare` reads the bounded v61 fire records and
creates private deterministic source-palette atlases and explicit slot bindings.
`tools/editor/apply_intro_fire.py` admits these through raster actor overrides;
`verify_intro_fire.py` reloads the saved scene, checks geometry and bindings, and
draws every animation frame on the GPU to reject blank/static output. See
[the flame checkpoint](../docs/milestones/011-source-flame-preview.md) for commands,
recovery notes and the distinction between this preview and native UE1 simulation.

## Animated water preview

`python -m ue1_converter.water_prepare` reads bounded v61 WetTexture records and
the referenced P8 image, then creates a private periodic horizontal-warp atlas
with repeat-safe padding and exact slot bindings. `apply_intro_water.py` creates
a lit translucent preview with a map recovery copy. `verify_intro_water.py`
checks the complete saved water/flame scene and every GPU animation frame. See
[the water checkpoint](../docs/milestones/012-source-water-preview.md) for commands
and limitations; this is not the native water solver or a gameplay-water volume.

## Darker intro atmosphere

`tools/presets/Unreal_Gloom_ue5.json` records an authored overcast correction.
`apply_intro_mood.py` validates the preceding saved scene and backs up the map
and project cloud material before editing. `verify_intro_mood.py` checks the
combined scene, atmosphere settings, source light colors and animation frames.
See [the gloom checkpoint](../docs/milestones/013-gloom-lighting.md) for initial
application, safe refinement and recovery. The preset does not establish an
original-game lighting or sky match.

## Original-image sky background

`python -m ue1_converter.sky_prepare` selects the explicitly marked high-detail
sky and prepares original P8 images plus compiled sky buffers in private storage.
`apply_intro_sky.py` creates a camera-centered backdrop after complete baseline
verification and a map backup. `verify_intro_sky.py` reloads the combined scene
and checks sky buffers, camera-offset graph, bindings and GPU cloud sampling.
See [the sky checkpoint](../docs/milestones/014-original-sky-background.md) for
commands and the limits of this preview, including deferred moons and lightning.
