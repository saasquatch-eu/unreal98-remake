# Castle intro: camera, original audio and visibility corrections

Completed locally on 2026-10-28 in UnrealGoldRemake / UE 5.8.4. Play now starts a
looping source-path camera with the original Flyby music and ten source-position
ambient emitters. The moat stays visible from elevated views, the entrance floor
renders solid, and the dark sky no longer becomes fog-bright when the backdrop
is moved away. The original world/Mover/sky/moon mesh buffers remain unchanged.

## Visibility and material corrections

The previous camera-centered miniature sky had an opaque lower surface only
4,096 cm below the camera. At an altitude of 8,500 cm it covered the water at
1,712 cm and lower castle geometry. Component draw distances and the viewport
far plane were unlimited; increasing general view distance was not the fix.

`extend_intro_sky.py` adds a 64× presentation expansion in the authored sky vertex
shader, placing that lower surface about 2.62 km away. It leaves the 82 source
triangles and actor transforms intact. The cloud lightning coordinate conversion
uses the same effective expansion, including FollowCamera=0 for GPU diagnostics.

Moving a regular opaque backdrop far away also increased atmospheric fog on it.
`correct_intro_surfaces.py` makes the stars a full-opacity unlit translucent
background, disables material fogging on both source sky parents and sorts stars
and cloud sheets before water/effects. It retains depth testing, source images,
UV scrolling and the existing capture exclusions. No IsSky flag or warning
suppression is used. The sun, skylight, exposure, atmosphere, volumetric-cloud
and fog rig values still match the existing gloom preset.

The apparent missing entrance floor has 39 source triangles using
`NaliCast.Floor.n-floor6` with source flags 0x08000004. The additive preview made
it appear absent against the background. Its existing material instance now
reuses the existing opaque lit parent, retaining its original texture, UVs,
material slots and recorded flags. This is an explicit presentation correction,
not a claim that the original surface flag was opaque. No replacement floor mesh
or collision is introduced. The instance's source-role path remains unchanged.

## Camera evidence and reconstruction

The checked v61 Level actor array and T3D agree on all 31 camera-point identities
and their order. Binary camera locations, rotations, Position and RateModifier
are checked against the text. Point zero's omitted Position resolves to zero.

The [pinned public InterpolationPoint class](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Classes/InterpolationPoint.uc)
links neighbors with ordered writes, so simply sorting Position would be wrong.
Two records have Position 17. Under those linking rules, the later
InterpolationPoint20 is reached and InterpolationPoint15 is excluded from the
30-point loop. Both raw records remain in the private recipe.

The [public Intro class](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/UnrealI/Classes/Intro.uc)
starts the Path group with interpolating physics. A
[description by an OldUnreal engine developer](https://www.oldunreal.com/phpBB3/viewtopic.php?p=30028)
identifies four-point positional evaluation and linearly blended modifiers.
The authored reconstruction uses a uniform cubic B-spline, shortest-angle Euler
unwrapping and analytic integration of linearly varying rates. It is baked at
60 Hz into 18,696 native transform keys over approximately 51.914 seconds.
All 3,116 sampled positions classify inside the source active world.

The camera uses raw path height. Native player eye-height/bob, exact rotation
semantics, the initial timer and release-specific physics have not been matched
to captured original frames. The source 90-degree horizontal FOV at 4:3 becomes
106.26 degrees at 16:9 to retain its vertical framing. Camera post-process blend
is zero; the existing exposure rig remains authoritative.

## Original audio

`audio61.py` is a separate bounded Sound/Music payload reader using the existing
v61 table/property helpers. It admits complete PCM WAVE sounds and the selected
Impulse Tracker music format, with strict size, tail and source-hash checks.
Package61's general admission profile is unchanged. No game code is executed.

The local Flyby.umx supplies the exact FlyBy IT payload. The user was informed
before using the existing Unreal installation's libxmp 4.6.0 through Python;
no program, dependency or provider was installed. The decoder path is an explicit
CLI argument and its version/hash are recorded. Music is rendered to 48 kHz
stereo PCM, approximately 51.891 seconds. The three referenced ambient recordings
are Mflare2, swmp10 and wind01; their original PCM sample loops span their full
recordings. Original package/group/resource spelling is retained, including the
binary resource's FlyBy case. Every new UE resource has the `_ue5` suffix.

Music is non-spatial and loops independently of the camera. Ten spatial ambient
emitters retain source positions, volume/pitch bytes and radius evidence.
Playback uses authored volume calibration and linear attenuation, not an exact
native mixer reconstruction. Virtual playback preserves phase outside audible
range. An actual six-second UE mixer recording was non-silent, with peak 0.175,
RMS 0.033 and zero clipped samples.

## Reproduce and recover

Start from the saved lightning checkpoint. In the correct editor project, save
work and stop PIE. Run, using the actual absolute repository path:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/extend_intro_sky.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/correct_intro_surfaces.py', run_name='__main__')
```

Prepare the intro using explicit existing local resources and a new destination:

```sh
.venv/bin/python -m ue1_converter.intro_prepare \
  data/converted/Unreal/Maps/Unreal/lightning-ready/Unreal.lightning.json \
  '/path/to/local/Unreal' --libxmp '/path/to/installed/libxmp.4.6.0.dylib' \
  --output-dir data/converted/Unreal/Maps/Unreal/intro-ready
```

```python
runpy.run_path('/absolute/repo/tools/editor/apply_intro_experience.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_experience.py', run_name='__main__')
```

Apply refuses existing destinations and verifies the prior scene before creating
`/Game/Unreal/Cinematics/Unreal_ue5`, `Unreal_FlybyCamera_ue5`, `Unreal_Intro_ue5`,
the music actor and ambient actors. Maps and affected materials are copied to
unique `.local/intro-recovery/` folders before their stages. Interrupted creation
requires inspection and recovery before retrying. Restore corresponding map and
material copies with the project closed, retaining later checkpoints if needed.
Do not overwrite unrelated work or remove shared resources.

Use **Play** to watch/listen. Stop exits the preview. The original HUD/title and
menu are not implemented; Escape uses the editor's normal Play-mode behavior.
The verifier's `verify_playback(plan_path, report_path)` requires Play mode and
runs asynchronously until it observes a real loop. It seeks diagnostic frames,
checks the player camera/audio, records mixer output, then leaves playback running;
stop Play after the success report. Simulate alone is not the cinematic-camera test.

## Executed checks and remaining work

- **268 Python tests passed**, including 22 synthetic intro/audio cases covering
  native payload bounds, sample loops, binary camera order/conflicts, duplicate
  link side effects, rate integration, curve continuity, Euler wrap, preparation,
  source immutability, provenance and overwrite refusal.
- Complete saved-scene verification passes: exact prior geometry/UV/material
  evidence, fire/water animation, moon motion, idle sky GPU parity and all 11
  cloud lightning responses. Counts stay **7,135 world + 116 Mover + 82 sky +
  672 moon triangles**. The extended projection/compositing graph, floor parent,
  camera framing, all transform keys, cut binding and audio emitters are checked.
- Native SoundWave WAV exports preserve rates, channels and frame counts. Every
  sample is compared; measured maximum PCM16 rounding error is one unit for
  16-bit sources and two for the 8-bit sources, with explicit tests enforcing
  these bounds. Source extraction and prepared WAVs remain byte-identical.
- Play automatically controlled the player camera; nine sampled frames matched
  the recipe. A real full loop completed while all 11 audio components kept
  playing. Final in-game and matching entrance/overhead views were inspected.
- All **144 file-hash checks across 135 distinct files** pass. Fresh preparation
  reproduces the entire recipe and all four audio files byte for byte. Original/generated game content and recordings remain private.

Broader, coordinated storm lighting remains an art pass: the existing localized
lightning is still a source-position approximation. Original HUD/menu/logos,
Nali and birds, decoration/flag animations, triggered Movers, their event sounds,
collision and captured original-frame comparison remain unfinished. This is a
working camera/audio preview, not the complete original runtime. No C++ build or
measured performance benchmark is claimed.
