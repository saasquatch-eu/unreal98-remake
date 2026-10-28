# Castle intro: original-image sky background

Completed locally on 2026-10-28 in UnrealGoldRemake / UE 5.8.4. The bright
background is replaced with the selected original sky's star textures and a
scrolling cloud sheet. The dark castle lighting, software Lumen, flames and water
remain in place. Moons, lightning, coronas and exact original-game matching remain
separate work.

## Source and projection

The map has two SkyZoneInfo actors. SkyZoneInfo1 explicitly sets bHighDetail=True;
its compiled BSP zone is 12. SkyZoneInfo0 belongs to zone 11 and remains deferred.
The source high-detail origin and raw properties are recorded in the private
recipe. Actor order and source indices are retained, including repeated names
among the deferred lightning actors.

The [pinned OldUnreal ZoneInfo reference](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Classes/ZoneInfo.uc)
selects a sky matching the level's detail mode. This is a later engine reference,
not proof of every original v61 runtime behavior. Selection here explicitly uses
the map's high-detail actor and compiled zone, without inferring omitted defaults.

The 33 selected sky faces contribute **82 triangles**: 76 opaque starfield
triangles and six translucent cloud-sheet triangles. Four derived meshes retain
source face indices, identity axes, source normals, UV texels normalized by the
actual image dimensions and the existing UE5 winding reversal. Positions become
`128 * (source_point - SkyZoneInfo1.location)`. The scale is a rendering choice
that preserves viewing angles; it does not establish physical gameplay scale.

A material vertex offset adds `camera_position - actor_position`, keeping the
miniature sky centered on the viewing camera. This removes camera-translation
parallax. The actors remain at identity transforms, use expanded render bounds,
and have collision, Nanite, shadows, distance fields and Lumen cards disabled.
The original 7,135 world and 116 Mover triangles remain untouched.

The decoded original P8 images are GenFluid.Sky.NghSky3 (128 × 128),
GenFluid.Sky.Ntskyt (128 × 128) and GenFluid.cloud1a (256 × 256). Resource spelling,
package/group paths and image colors are preserved; UE assets add `_ue5`.
Palette index zero remains opaque for the black starfields. All images, source
buffers, recipes and generated UE assets remain private and ignored.

## UE5 materials and lighting

Existing project/engine sky materials and functions were searched first. They
do not provide this source-UV miniature projection. Two small project parents
use source texture samples and camera-position offsets: opaque stars and an
additive, two-sided cloud preview. Instances expose SkyBrightness, FollowCamera
and, for clouds, PanRate and PreviewOffset. Saved brightness/follow values are 1;
the saved preview offset is zero.

The cloud's source flags enable U- and V-panning. The exported zone speeds are
both 0.3. The preview uses an **authored 32 texels/second multiplier**, yielding
0.0375 UV repeats/second on each axis for the 256-pixel image. This multiplier,
phase, unlit shading and additive blend are not a measured native-renderer match.
The source raw flags/speeds remain in the recipe for later comparison.

The final backdrop uses regular unlit materials with **Is Sky disabled** and is
excluded from realtime skylight and reflection captures. This preserves the
previous atmosphere-driven ambient rig rather than recalibrating illumination
around an unverified starfield brightness. It is a deliberate visual/lighting
approximation; sky reflections and source sky lightmaps are not reconstructed.

During integration, an Is Sky material excluded from realtime capture caused a
UE5 warning and incorrect red illumination. The accepted regular-unlit setup
removed that warning and restored the preceding lighting appearance. Three
result/refinement cycles were inspected; no additional lighting tuning followed.
An earlier material-input naming error stopped creation before any sky actor was
added. Only the new partial assets were backed up and removed before retrying.
No original assets, application bundles or world mesh buffers were modified.

## Run locally

Finish the gloom checkpoint first. With a new private destination:

```sh
.venv/bin/python -m ue1_converter.sky_prepare \
  data/converted/Unreal/Maps/Unreal/geometry-final/Unreal.geometry.json \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  "$HOME/Library/Application Support/Unreal/Maps/Unreal.unr" \
  --texture-root "$HOME/Library/Application Support/Unreal/Textures" \
  --output-dir data/converted/Unreal/Maps/Unreal/sky-ready
```

Preparation validates map/export hashes against the geometry provenance, selects
the explicit sky actor and compiled zone, checks supported surface flags, decodes
bounded P8 images and hashes every output. Existing directories are refused.

Save the map, stop PIE and run with the actual absolute repository path:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_sky.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_sky.py', run_name='__main__')
```

Apply verifies the complete gloom baseline, refuses existing destination assets,
and saves a unique map backup under `.local/sky-recovery/` before creating assets.
An interrupted import requires inspection and recovery before retrying. For
rollback, close the project before restoring its backed-up map; retain or remove
only the newly created sky assets after inspecting their references.

## Verification and remaining limits

- **209 Python tests passed**, including 13 synthetic source-sky tests for
  positions, winding, UVs, zone filtering, explicit detail selection, unsupported
  flags, finite scale, source immutability, naming, repeated actor identity,
  overwrite refusal, map/export provenance, flagged-axis motion and translation.
- Saved-map reload checks the complete preceding castle, then all 82 sky
  triangles, UVs, bindings, render/build settings, texture color space, parent
  settings, camera-centering graph and connected cloud clock/rate.
- GPU checks sample all three sky materials. Each is nonblank; two controlled
  cloud offsets produce distinct images. These use transient instances with
  camera following and clock rate disabled, preserving the saved material values.
  Both flames and water also retain their existing 64-frame GPU checks.
- Native fixed gate and moat views were inspected. The accepted gate view has a
  dark blue-black background with faint stars/cloud detail, without the earlier
  capture warning. No original-game matching frame or timed flyby was captured.

Source sky portals are approximated by the existing world openings; low-detail
sky, moons, lightning, coronas, native sky lighting, scrolling calibration and
reflection behavior remain unfinished. No C++ build, performance target, new
application or external generation service is claimed.
