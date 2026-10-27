# Castle intro: first UE5 geometry import

Checked on 2026-10-27 in UnrealGoldRemake with UE 5.8.4 on Mac arm64. The
castle is now a saved, private UE5 map. This is a geometry inspection checkpoint;
materials, original atmosphere, collision and camera playback are not complete.
The lit viewport is still overexposed, so visual presentation is not accepted.

## Saved resources

| UE5 path | Purpose / triangles |
| --- | --- |
| `/Game/Unreal/Maps/Unreal_ue5` | Inspection level |
| `/Game/Unreal/Meshes/Unreal_ue5` | Original evaluated visible world: 7,135 |
| `/Game/Unreal/Meshes/Mover37_ue5` | Separate rest mesh: 12 |
| `/Game/Unreal/Meshes/Mover49_ue5` | Separate rest mesh: 104 |
| `Unreal_Camera_ue5` actor | First original interpolation-point pose; diagnostic 75° FOV |

Original names and case are retained, with `_ue5` on new resources. The map has
three mesh actors, the camera, and four explicitly named inspection lighting /
exposure actors. They use existing engine classes and BasicShapeMaterial. No
original textures, third-party generated models or new audio were used.

All generated `.uasset` / `.umap` files, recipes, buffers, logs, backups and
screenshots stay ignored. The repository contains tooling and synthetic tests.
The project still starts with the engine Entry map: open the private
`Content/Unreal/Maps/Unreal_ue5.umap` to inspect this checkpoint. Fresh clones do
not contain that map. No Cinematics asset or playable level is claimed.

## Conversion contract

`tools/src/ue1_converter/ue5_prepare.py` prepares a create-only recipe and mesh
buffers from the previous geometry bundle. Axes remain `(X,Y,Z)`. One source
unit currently becomes one UE5 centimetre, a coordinate-preserving inspection
scale; physical gameplay scale remains unresolved. Compiled world points are
not transformed again. Each Mover mesh is rebased around its original Location;
its actor restores that position, with source rotation and scale already baked.

UE5 StaticMesh normals use the reverse cross product compared with the source
triangulation. Triangle winding is reversed while positions and surface normals
are retained. Disconnected triangle corners avoid welding / manifold assumptions.
The importer disables Nanite, collision and removal of degenerate triangles.
Each actor uses the saved NoCollision profile, verified after map reload.

UV0 is a per-triangle diagnostic basis. It is mandatory even for an untextured
static mesh. It is **not** the original normalized texture mapping. Original
texture paths, flags and texel coordinates remain in `Unreal.geometry.json`.
Opaque neutral inspection shading does not reproduce translucent surfaces, sky
masks, the original sky zones, material animation or original lighting.

## Run locally

Use the existing repository `.venv`; Geometry Scripting is an Editor-only project
plugin supplied with the installed engine. No new application is installed.

```sh
.venv/bin/python -m ue1_converter.ue5_prepare \
  data/converted/Unreal/Maps/Unreal/geometry-final/Unreal.geometry.json \
  --output-dir data/converted/Unreal/Maps/Unreal/ue5-import-ready
```

The output directory must not exist. Inside the connected UnrealGoldRemake
editor, save work, stop PIE and run through its existing Python console:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/import_intro.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro.py', run_name='__main__')
```

Use the real repository path. The importer refuses existing destination maps or
meshes and checks geometry / buffer SHA-256 values before building. It checks
triangle counts and bounds before creating the level, then saves resources.
A failure can leave newly created assets; inspect its private report rather than
blindly retrying or automatically deleting assets. Verification switches away
and reloads the saved map, so open work must already be saved. Reports are under
`.local/logs/unreal-ue5-import-result.json` and `unreal-ue5-verified.json`.

`smoke_test(report_path)` in the editor importer builds a one-triangle diagnostic
asset. Use it before changing the native mesh build path, with the correct
project connected and no unsaved work. It is an API smoke test, not castle proof.

## Executed verification and recovery

- Python checks: **106 passed**, including previous 93 tests. Added cases cover
  identity axes, winding, separate pivots, explicit scale, overwrite refusal,
  mandatory finite UVs / normals, UV degeneracy and invalid triangle indices.
- A legacy OBJ/FBX probe reflected Y and dropped three world triangles. Its
  output was rejected. The final route builds direct Geometry Script buffers.
- The initial direct build crashed at `UStaticMesh::EnforceLightmapRestrictions`
  (`NumUVs > 0`). Missing UV0 was the cause. Mandatory UV validation and a
  successful tiny-mesh check preceded the successful full retry. No original
  source was modified or castle map saved by the crashed attempt.
- The final importer created all three meshes and the level. Saved-map readback
  compares **all 7,251 triangle positions and cyclic winding**, independently of
  triangle IDs, at StaticMesh float precision. Mesh counts, actor placements,
  identity rotation/scale, assignments, UV-channel presence and NoCollision
  state are checked. Original package, raw export and geometry hashes remain
  unchanged.
- The saved map reload completed with zero map-check errors or warnings.
  The import recipe / generated assets remain ignored. Calibration probes were
  removed after their checks; a private recovery backup remains.
- Camera captures established the entrance orientation after winding correction.
  The lit inspection view remains overexposed after three refinement captures.
  This is an open visual issue, not a fidelity pass. Further lighting work is
  deferred under the loaded project lighting Agent Skill's three-cycle limit.
- The C++ module was unchanged. `scripts/build-ue5.sh` stopped at the Xcode first
  launch preflight (`xcodebuild -checkFirstLaunchStatus`, exit 69). **No new C++
  build pass is claimed.** The installed Geometry Scripting binaries loaded and
  ran in the editor. Application installation / updates / removal remain manual.

## Next checkpoint

Resolve the viewport exposure, then reconstruct original texture dimensions,
normalized UVs and material assignments while preserving the compiled geometry.
Validate original sky behavior and transparent surfaces before judging visual
fidelity. Collision, physical scale, Mover animation and complete flyby timing /
looping remain separate tasks.
