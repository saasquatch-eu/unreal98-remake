# Castle intro: source moons and rotation preview

Completed locally on 2026-10-28 in UnrealGoldRemake / UE 5.8.4. Three moon actors
now use the installed game's original mesh/image payloads in the camera-centered
sky. Two spin at their exported yaw rates and the third remains stationary.
The castle lighting, world geometry, star/cloud background, flames and water
remain intact. Lightning and original-game frame matching remain unfinished.

## Resource evidence and bounded decoding

The installed UnrealI.u in Unreal.app uses package version 69, licensee 227.
UT99's installed shared UnrealI.u uses version 69, licensee zero. The existing
v61 map decoder deliberately rejects both. `moon69.py` provides a separate
read-only resource profile for version 69, licensee 0/227, package flags 0/1 and
bounded ANSI names/tables. It does not broaden `Package61` or the original map,
BSP, texture or procedural-effect admission profiles.

Only selected ordinary P8 textures and one-frame Mesh/LodMesh records are
supported. Counts, signed packed vertices, lazy-array endpoints, texture/palette
references, mip layouts, complete consumed sizes, material indices and full-detail
LOD indices are checked. State frames, unsupported LOD attachments/remaps,
nonzero material flags, multiple animation frames and unexplained tails fail.
This is not a general v69 or patched-engine converter.

The [pinned mesh structure reference](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UnMesh.h)
and [UEViewer's UE1 serializer](https://github.com/gildor2/UEViewer/blob/a0bfb468d42be831b126632fd8a0ae6b3614f981/Unreal/UnrealMesh/UnMesh1.cpp)
were inspected to establish field layouts, then checked against exact byte
consumption and synthetic fixtures. No engine implementation or game-derived
binary fixture is copied into the repository.

Both installed copies have matching full-detail triangle positions, cyclic
winding, per-corner UVs and stored scale/origin/rotation for Moon1 and Moon3M.
Moon1 is a Mesh in UT99 and a LodMesh in the patched Unreal installation; their
full-detail representations are semantically identical. Both have 114 packed
vertices and 224 triangles. LOD reduction is not used in the UE5 preview.

All three skins also match across installations: dimensions, every P8 pixel and
every palette byte. These comparisons do not claim that the patched package
files equal an original v61 release. The source used is the local Unreal package;
UT99 supplies independent matching payload evidence. Both package hashes and
selected export hashes are retained privately. Application bundles are read only.

## Actor transforms and appearance

The selected map/export hashes are checked through the preceding sky recipe.
Actor order, names, raw properties and source indices are retained. These are the
three original actor-to-resource assignments:

| Actor | Class | Mesh | Skin | DrawScale | Yaw units/second |
| --- | --- | --- | --- | --- | --- |
| Moon0 | Moon | Moon1 | UnrealI.Skins.JMoon1 | 1 | -500 |
| Moon1 | Moon3 | Moon3M | UnrealI.Skins.JMoon3 | 0.5 | 0 |
| Moon2 | Moon2 | Moon1 | UnrealI.Skins.MoonTwo | 0.8 | -2300 |

The [Moon](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/Moon.uc),
[Moon2](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/Moon2.uc) and
[Moon3](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/Moon3.uc)
references supply mesh/skin assignments and omitted class rate components.
Instance overrides are applied component by component. Moon1 overrides both
inherited yaw and roll to zero; Moon2 explicitly overrides inherited pitch to
zero. Original v61 class default objects are not decoded.

The stored mesh origin is subtracted, mesh scale and legacy-grid RotOrigin are
applied, then actor rotation/DrawScale and the preceding sky projection scale
(128) produce camera-relative source positions. Moon3M's nonzero mesh origin is
preserved. The chosen transform convention is tested synthetically; an original
runtime frame comparison remains outstanding. UV bytes are divided by 256;
there is no additional flip. Source triangle winding is reversed once for UE5.

Three separate derived preview meshes use the original actor stems plus `_ue5`.
They add **672 triangles**, separate from the 82 sky background and unchanged
7,135 world + 116 Mover triangles. Original resource stems remain in the recipe;
skin textures preserve their actual UnrealI/Skins paths with `_ue5` appended.
All game data and generated meshes/textures/materials remain private and ignored.

The moon parent duplicates the project's existing source-sky material and adds
UE5's RotateAboutAxis node. A world-Z pivot and yaw/65536 turns per second produce
continuous rotation, added to the existing camera-follow offset. This is a source-
rate preview using material time; native quantized physics, initial time/phase,
sky lighting and pixel-identical animation are not established.

The regular unlit parent keeps Is Sky disabled, with no collision, shadows,
Nanite, distance fields, Lumen cards, realtime sky capture or reflection-capture
participation. Authored moon brightness is 8 for readability; source image colors
and all scene lights/exposure remain unchanged. This approximates the original
sky lighting. The first view was dim and foreground-occluded; a brightness
refinement and elevated diagnostic cameras made all three readable. No source
moon positions or sizes were moved to force visibility from the entrance.

## Reproduce and recover

Complete the sky background checkpoint. Supply the two existing local resource
packages explicitly, choosing a new private destination:

```sh
.venv/bin/python -m ue1_converter.moon_prepare \
  data/converted/Unreal/Maps/Unreal/sky-ready/Unreal.sky.json \
  /Applications/Unreal.app/Contents/Resources/System/UnrealI.u \
  /Applications/UnrealTournament.app/Contents/MacOS/System/UnrealI.u \
  --output-dir data/converted/Unreal/Maps/Unreal/moons-ready
```

Use the installed paths on the actual machine. The command refuses mismatching
cross-installation payloads, changed sky provenance and existing output folders.
It reads application resources without changing them or running native game code.

Save work, stop PIE and use the actual absolute repository path:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_moons.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_moons.py', run_name='__main__')
```

Apply verifies the complete prior scene, refuses existing destinations, and saves
a unique map backup under `.local/moons-recovery/` before creating resources.
The later local brightness refinement retained copies of all three preceding
material instances and its recipe. Interrupted creation requires inspection and
recovery before retrying. For rollback, close the project before restoring the
backed-up map; inspect references before removing only the new moon assets.

## Executed checks

- **229 Python tests passed**, including 20 synthetic moon checks covering the
  bounded package profile, unchanged v61 rejection, packed signed coordinates,
  equivalent Mesh/LodMesh payloads, malformed indices/endpoints/tails, unsupported
  animation/attachments, palette/image bytes, transforms, component overrides,
  complete preparation, provenance, cross-installation mismatch and overwrite
  refusal.
- Saved-map reload verifies the entire preceding castle/sky/effects stage and all
  672 moon triangle positions, winding and UVs, source texture bindings, render
  flags, saved material controls, pivots and connected rotation/clock graph.
- Isolated 256 × 256 GPU scene captures exercise the actual moon mesh and vertex
  shader at preview times 0 and 3 seconds. Moon0 and Moon2 produce distinct
  nonblank frames; stationary Moon1 produces identical nonblank frames. Transient
  instances disable camera following and the runtime clock only for this check.
  Preview/capture actors and targets are removed, with actor inventory checked
  before/after. Saved playback remains enabled and preview time remains zero.
- The existing two flame and one water materials retain their 64 distinct,
  nonblank GPU frames each. All 127 source/recipe/buffer/image/package integrity
  checks pass. A fresh preparation reproduces the serialized moon recipe and
  every prepared image/buffer exactly.
- Native elevated views of all three moons were inspected. Entrance occlusion is
  expected; these cameras use diagnostic height and 75-degree FOV rather than a
  verified source flyby frame. No lighting or original world geometry was altered.

No new application, external generation service, C++ change/build or measured
performance target is part of this checkpoint. Lightning, coronas, sky reflection
behavior, native sky-light calibration and timed original-game comparison remain
future work.
