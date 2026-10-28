# Castle intro: source-position lightning preview

Completed locally on 2026-10-28 in UnrealGoldRemake / UE 5.8.4. The castle now
has a native looping lightning preview: 18 source-position movable lights and
11 localized brightness pulses on the original cloud sheet. Saved editor lights
start at zero. Simulate/Play starts the sequence automatically; the dark overcast
baseline remains between bursts. Original world, Mover, sky and moon buffers are
unchanged. Generated assets, recipes, reports and captures remain private.

## Source evidence and preview limits

The [pinned OldUnreal DistanceLightning class](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/DistanceLightning.uc)
resets its light to off in BeginPlay, waits 5–15 seconds initially, then alternates
0.4–0.45-second flickering bursts and 9–29-second quiet intervals. This applies
even to map instances exported as steady lights. The class itself supplies light
flashes, without a bolt mesh or thunder playback.

The checked original v61 map/export contains 35 DistanceLightning records.
Binary BSP point-zone classification selects 11 in the high-detail sky and seven
in the world. Thirteen low-detail-sky records and four out-of-bounds records stay
excluded and documented. Source indices, repeated names, raw properties and
locations remain intact. Omitted values use the pinned class defaults; the
original v61 class-default object has not been decoded, so this does not establish
an exact release-specific default match.

`lightning_prepare.py` creates deterministic, independently seeded schedules in a
128-second loop. Every initial delay, burst and quiet interval, including the
periodic boundary, stays within those source ranges. The 40 ms stepped flicker
waveform and repeated loop approximate the native random behavior. They do not
reproduce its random generator or renderer flicker algorithm.

The seven world lights use VSM shadows. The 11 miniature-sky point lights are
non-shadowing. An authored material addition translates pixel positions back to
source sky coordinates and applies squared radial falloff from each sky light.
The original cloud material is unlit, so this shader pulse is necessary for the
cloud sheet to respond. Existing UV panning, camera following, texture bindings
and sky/reflection capture exclusions remain intact.

World lumens, cloud gain 32 and spatial falloff are artistic calibrations, not a
UE1 lightmap match. No sun, skylight, exposure, fog or volumetric-cloud preset is
retuned. Software Lumen, Nanite and VSM remain the rendering foundation. No new
geometry, textures, audio, Blueprint runtime or C++ system is added. Source-frame
matching, native sky-light calibration, coronas, collision and camera playback
remain unfinished.

## Reproduce and recover

Complete the moon checkpoint, then choose a new private destination:

```sh
.venv/bin/python -m ue1_converter.lightning_prepare \
  data/converted/Unreal/Maps/Unreal/moons-ready/Unreal.moons.json \
  --output-dir data/converted/Unreal/Maps/Unreal/lightning-ready
```

Preparation checks prior-stage/source/package/geometry provenance and refuses
existing output folders. In the correct project, save work, stop PIE and wait for
asset compilation before running these commands with the actual repository path:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_lightning.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_lightning.py', run_name='__main__')
```

Apply verifies the complete preceding scene and saves unique copies of the map,
cloud parent and idle GPU evidence under `.local/lightning-recovery/` before
editing. It refuses existing destination assets or actors. The new resources are
`/Game/Unreal/Materials/UE5/DistanceLightning_ue5` (parameter collection) and
`/Game/Unreal/Cinematics/DistanceLightning_ue5` (LevelSequence), plus 18 original
actor stems suffixed `_ue5` and the `DistanceLightning_ue5` sequence actor.

After starting Simulate, run `verify_pie(plan_path, report_path)` from the verifier
module. It checks autoplay, pauses and seeks every authored transition, then
returns to paused time zero. `verify_loop(plan_path, report_path)` schedules a
one-second native check across the end of the sequence; wait for its success
report before stopping Simulate. These are diagnostic checks and intentionally
pause the player; a new simulation session restores automatic preview playback.

An interruption requires inspecting the partial state before retrying. For
rollback, close the project and restore both the map and cloud parent from the
same recovery folder. Inspect references before removing only the new lightning
assets. Do not restore unrelated content. A cold editor initially reported zero
sizes for asynchronously preparing textures; the exact checks were rerun after
loading settled. No size/count check was relaxed.

## Executed checks

- **246 Python tests passed**, including 17 lightning tests for zone selection,
  repeated identities, exported steady lights starting off, rejected inputs,
  timer ranges and loop seams across 100 seeds, spatial falloff, reproducibility,
  provenance and overwrite refusal.
- Saved-map reload verifies all preceding geometry, UVs, materials, lighting,
  fire/water GPU animation, sky and moon motion. Counts remain **7,135 world,
  116 Mover, 82 sky and 672 moon triangles**. All 18 source transforms, radii,
  colors, mobility/shadow flags and zero saved intensities pass. Both actor and
  component possessables resolve, with exact saved key times/values and constant
  interpolation, 11 collection curves, playback range and loop settings checked.
- Idle sky GPU output is identical to the pre-edit evidence. Isolated 128 × 128
  HDR captures use the actual cloud mesh/material, freeze UV motion and exercise
  each sky parameter independently off/on/off. All 11 brighten their patch
  (4.86–17.89 times the isolated baseline energy) and return to identical off
  pixels. Capture actors/targets are cleaned up and all parameters return to zero.
- All **134 prepared-file hash checks across 127 distinct files** pass, and a
  fresh preparation reproduces the lightning recipe byte for byte.
- Native simulation autoplay passes. At **1,481 transition times**, all **26,658
  light values** and **16,291 cloud values** match the prepared schedules. The
  player crosses the 128-second boundary and continues playing.
- Native entrance, moat, west-castle and sky views were inspected. The controlled
  flash captures pause at recipe time 13.838 seconds; these are diagnostic views,
  not matched original flyby frames. No shadow-overflow banner was visible in
  the inspected views; this is not a performance benchmark.

No additional application or provider, application-management permission, C++
change/build, or original-asset publication is part of this checkpoint.
