# Castle intro: source inspection checkpoint

Completed on 2026-10-26 using the existing repository-local Python environment.
No additional software, exporter, asset provider, or UE5 editor operation was used.

## Deliverable

The Python package now provides a source T3D parser and `inspect-t3d` CLI. It
preserves actor order, repeated names, raw properties and transforms, model
references, polygon winding, texture basis/pan records, and header metadata.
The private JSON report is at
`data/converted/Unreal/Maps/Unreal/Unreal.inspection.json`.
Its contract is documented in `../../schemas/t3d-inspection-v1.md`.

The source `Unreal.t3d` remains 918,281 bytes with SHA-256
`d7b86d1698991d69528f1c6e4238eea961be9d6a63dabccbe31cb6f02abbfb52`.
It was inspected, not rewritten. No source geometry or detailed game-derived
report is included in Git; tests use an authored synthetic export.

## Observations

| Source item | Count |
| --- | --- |
| Actors | 359 |
| Brush actors / Movers | 184 / 2 |
| Inline geometry definitions | 184 |
| Source polygons / vertices | 1,501 / 5,642 |
| Explicit CSG_Add / CSG_Subtract properties | 122 / 61 |
| Shared brush instances | 2 |
| Polygons without an explicit Texture header | 115 |
| InterpolationPoint actors | 31 |
| Unique explicit texture / sound / music references | 41 / 5 / 1 |

These are source counts, not evaluated geometry or a complete asset dependency
inventory. One Brush and both Movers omit CsgOper; class defaults are unresolved.
Shared instances refer to definitions earlier in the export. Instances and
definitions must remain distinct, with each instance's transform and order intact.
Missing texture headers are preserved, not filled with guessed materials.

The report contains 14 warnings:

- Four malformed numeric tokens across three brush PrePivot properties. They
  include exponent notation with an extra decimal suffix. The raw tokens are
  retained; stripping the suffix or replacing values has not been authorized by
  source evidence. This observation concerns the text export, not proven damage
  to the original binary map.
- Eight actor occurrences share four repeated names. Two pairs are brush
  definitions/instances and two pairs are lightning actors. Actor index and
  source line distinguish them; no actors were dropped or renamed.
- One camera point omits Position. The report leaves it unresolved rather than
  assuming its class default is zero.
- Two camera points in the same Tag group explicitly use Position 17. A name
  suffix or source order is not sufficient evidence for intended playback order.

Camera rates, rotations, tags, and other exported properties remain available as
raw values. Timing, looping, FOV, and class-default behavior are not reconstructed.

## Validation

- `bash scripts/run-tests.sh`: 31 passed, including the installation smoke test.
- Synthetic cases exercise nested/quoted properties, CRLF retention, polygon
  winding and UV data, shared/ambiguous/missing models, repeated names and
  properties, omitted defaults, malformed numeric tokens, invalid structure,
  explicit encodings, and CLI input/output safety.
- The real intro report matches the earlier independent export block counts and
  recorded checksum. Every source polygon passed strict record/vector parsing.
- Source/export hashes, report determinism, ignored output paths, and
  `git diff --check` were verified before committing.

This change requires no C++ build: no C++ or engine configuration was changed.

## Subsequent coordinate validation

The next bounded checkpoint is complete; see `006-brush-validation.md`. It
resolves the four malformed pivot components with binary evidence and tests
source transforms plus synthetic box operations. Full castle BSP evaluation
and camera behavior remain unresolved.

## Geometry questions recorded at this checkpoint

1. Establish how the original runtime reads the malformed export values, or obtain
   verified values directly from the binary map with the existing tooling.
2. Validate the brush transform sequence, pivots, negative/nonuniform scales,
   flags, and ordered add/subtract evaluation with small synthetic solids.
3. Evaluate the castle's solid geometry before making UE5 meshes. Validate scale,
   orientation, openings, sky zones, UV application, and the two Movers separately.
4. Resolve class defaults and camera-position conflicts against original runtime
   behavior before reconstructing the flyby.

No geometry conversion, triangulation, UE5 import, generated map, or gameplay is
part of this checkpoint. UnrealGoldRemake still opens the engine Entry map.
