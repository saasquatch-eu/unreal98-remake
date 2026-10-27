# Castle intro: original evaluated BSP extraction

Completed on 2026-10-27 using Python and existing local libraries. No software was
installed, no application bundle was changed, and no app-management permission
was requested. Unreal Editor was not controlled by this checkpoint.

## Result and approach

The original map contains its already evaluated world BSP. Extraction follows the
serialized Level.Model reference into that geometry, preserving the original
editor cuts without implementing a replacement CSG builder. The earlier T3D and
numeric-evidence work remains useful for source inspection and separate Movers.

Private outputs are under `data/converted/Unreal/Maps/Unreal/geometry-final/`:

- `Unreal.geometry.json`: classified geometry, original paths/flags, texel UVs,
  zones, original face boundaries, triangulation diagnostics, and Mover metadata.
- `Unreal_ue5.obj`: untextured visible world and separately named Mover rest geometry.
- `Unreal.overview.png` and `Unreal.camera0.png`: inspected offline clay previews.

These are local game-derived artifacts and remain ignored by Git. They are not
UE5 `.uasset`/`.umap` resources. No original map or export was rewritten.

## Observations

| Item | Count |
| --- | --- |
| Reachable / stored world BSP nodes | 2,762 / 2,762 |
| Native surface records | 933 |
| Native points / direction vectors | 4,245 / 797 |
| Stored vertex-pool entries | 42,181 |
| Stale invalid indices in unused pool slots | 3,372 |
| Visible world face fragments | 2,574 |
| Separate Mover source faces | 55 across two Movers |
| Visible world / Mover triangles | 7,135 / 116 |
| Total OBJ triangles | 7,251 |
| Sky masks / sky-zone face fragments | 90 / 66 |
| Other non-rendered fragments | 31 solid-interior, 1 invisible |

Every referenced point is valid; stale unused pool slots are counted and never
used as geometry. The model is selected through the level link, not by size or
name heuristics. Each supported geometry table is consumed exactly, and graph
cycles/out-of-range references are rejected.

All 31 flyby points and the PlayerStart resolve to world zone 1. The two original
SkyZoneInfo actors resolve to their corresponding stored zones 11 and 12. This
checks the extracted tree against independently exported actor positions; it does
not prove full collision or camera playback behavior.

Surface data preserves 108 portal-flagged face fragments, including visible
transparent surfaces, plus semi/non-solid flags. Hidden portal/sky surfaces are
not converted to opaque walls. Render roles do not define UE5 collision.

Triangulation retains ordinary collinear boundary points. Two original native
nodes contain zero-width projected edge reversals; their omitted corner indices
are recorded, and complete original boundaries remain in JSON. Projected areas
are checked for all faces. The maximum stored point-to-node-plane deviation is
approximately 0.234 source units; no vertex snapping or reprojection is applied.

The original compiled world contains no baked Mover surfaces. `Mover37` and
`Mover49` use separate source-model geometry, preserving names and rest transforms.
Their source properties and keys are retained for later animation work.

## Verification

- `bash scripts/run-tests.sh`: **93 passed**, including all 65 prior tests.
- Authored synthetic native packages cover level/model linking, a larger decoy
  model, object-path hierarchy/cycles, native references, stale unused pool slots,
  malformed vertex spans/children, BSP cycles, unexplained table bytes, and zones.
- Synthetic triangulation covers convex/concave boundaries, reversed winding,
  collinear corners, zero-width spurs, non-finite/degenerate/self-intersecting
  polygons, projected area, and bounded vertex counts.
- CLI tests cover matching provenance and refusal to overwrite existing outputs.
- Original input hashes, deterministic geometry/OBJ output, finite UVs, triangle
  winding/index validity, and ignored output paths were checked before committing.
- Overview and source-camera previews were rendered and visually inspected with
  the already installed Pillow/NumPy libraries. They show the castle and entrance
  geometry without original materials. No original-game screenshot comparison or
  live UE5 import is claimed.

Primary references are the pinned OldUnreal public
[legacy geometry containers](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UnModel.h),
[BSP structures](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UnObj.h),
and [surface flags](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UnPolyFlag.h).
Engine source is referenced rather than copied into the repository. The bounded
native layouts are validated against the actual map's geometry-table sizes and
cross-references; this is not a universal Unreal package decoder.

## Next checkpoint

Import `Unreal_ue5` into the UE5 project with explicit source-to-UE5 scale and axis
mapping. Establish texture dimensions and normalized UVs, build materials, then
validate openings, sky behavior, collision, and the separate Movers in-editor.
Camera timing, duplicate path positions, looping, and original effects remain
separate work. The current project still opens the engine Entry map.
