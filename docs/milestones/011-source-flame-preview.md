# Castle intro: animated source-palette flame preview

Completed locally on 2026-10-27 in UnrealGoldRemake / UE 5.8.4 on the existing
M4 Max. The previously transparent `NALIFX.SHANEFX.TORCHES2` and `NALIFX.flames1`
surfaces now show animated additive flames. This is an independent reconstruction
using the original palettes and spark anchors, not an emulation of the original
native Fire engine. Water, original sky behavior and flyby playback remain pending.

## Source evidence and deliberate limits

The bounded v61 reader checks a single empty parametric mip, dimensions, a local
256-color palette, native spark count and exact native-tail consumption. Spark
records contain eight bytes. The original records, all tagged properties, default
assumptions and export/palette/package hashes remain in the private recipe.
The generic static Texture decoder remains unchanged and still rejects FireTexture.

The actual source provides:

| Resource | Dimensions | Spark records | Types observed | Visible triangles |
| --- | --- | --- | --- | --- |
| `NALIFX.SHANEFX.TORCHES2` | 128 × 128 | 32 | OzHasSpoken | 50 |
| `NALIFX.flames1` | 128 × 128 | 8 | Blaze, BlazeLeft | 78 |

Record order, positions, heat, palette colors, RenderHeat and bRising are retained
as inputs. The preview uses authored deterministic particle motion and heat
advection. Raw byte_a..d values are preserved without assigning unverified native
motion meanings. Normal/Lathe modes and the three observed spark types are the
only admitted preview subset; other motion types fail rather than being silently
substituted. Lathe is approximated by mirror symmetry. A fixed warmup and a
crossfade between two trajectories produce a repeatable loop.

The 16 FPS, four-second duration, particle movement and emissive gain are preview
choices. They are not measured original timing or validated native fire behavior.
No original-game frame comparison has been completed. These limits are explicit
in the recipe and should stay visible when judging fidelity.

Reference layouts were read from OldUnreal's pinned
[FireTexture definition](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Fire/Classes/FireTexture.uc)
and [FractalTexture definition](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Fire/Classes/FractalTexture.uc),
and checked against complete consumption of the actual v61 objects and authored
synthetic fixtures. Reference code and original assets are not copied into Git.

## UE5 representation

Each source generates a 64-frame, 8 × 8 atlas with two-pixel padding around every
128 × 128 frame, yielding a 1,056 × 1,056 TGA. P8 colors become RGBA; palette index
zero gets zero alpha. The additive material multiplies RGB by alpha, so the clear
background contributes no light. Atlases have no mipmaps, bilinear filtering and
wrap addressing. Source UVs are repeated before applying per-cell padding.

The existing engine `Texturing/FlipBook` material function supplies animation and
sampling. Its UV math relies on wrapping when the frame's horizontal index passes
a row boundary. Clamp addressing initially produced blank phases; GPU readback
caught this. Top-to-bottom atlas rows and wrap addressing are now tested across
every frame. Engine functions and materials are only referenced, never edited.

One project material parent, `Materials/UE5/Unreal_FireFlipbook_ue5`, supports two
instances. Playback rate, phase offset, atlas layout/padding and emissive strength
are parameters. The phase offset also permits deterministic GPU checks through
transient dynamic instances without editing the saved instance values.

Names preserve original stems, package/group case and the `_ue5` suffix:

- `Textures/NALIFX/SHANEFX/Flipbook/TORCHES2_ue5`
- `Materials/NALIFX/SHANEFX/animated/TORCHES2_ue5`
- `Textures/NALIFX/Flipbook/flames1_ue5`
- `Materials/NALIFX/animated/flames1_ue5`

Five explicit component material overrides bind the instances to the existing
raster effect actors. Mesh assets, triangle material IDs, UV buffers and the
canonical source reference remain intact. Overrides are verified across all
world chunks: every other visible slot must still resolve to its source material.
Fire surfaces remain outside Nanite and cast no shadows, retaining the preceding
VSM workload boundary. Existing source-position lights illuminate the torch areas;
this checkpoint does not add flickering light intensity or new particle geometry.

## Run locally

Complete the Lumen lighting checkpoint first. Prepare a new private directory:

```sh
.venv/bin/python -m ue1_converter.fire_prepare \
  data/converted/Unreal/Maps/Unreal/materials-ready/Unreal.materials.json \
  data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json \
  --texture-root "$HOME/Library/Application Support/Unreal/Textures" \
  --output-dir data/converted/Unreal/Maps/Unreal/fire-ready
```

Preparation checks the lighting/material manifests, original texture package and
bound mesh-buffer hashes. It refuses existing output directories. In the editor,
save work and stop PIE, then run:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_fire.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_fire.py', run_name='__main__')
```

Use the actual repository path. Apply requires empty new asset destinations and
unchanged source material bindings. It copies the saved map into a unique private
`.local/fire-recovery/` directory before changes. A stopped import may leave new
assets; inspect the failure and restore/clean only that attempt's resources before
retrying. Verification reloads the map and requires an active rendering editor.
All atlases, recipes, UE assets, captures, GPU samples and reports remain ignored.
Only the existing Python, UE5, Git and GitHub tools were needed.

## Executed checks

- **170 Python tests passed**, including 22 new checks for native records,
  palette/byte preservation, malformed layouts, counts, types, bounds and tails,
  deterministic moving frames, unsupported preview modes, duration bounds,
  atlas order/padding/colors/alpha, exact slot binding, package provenance,
  overwrite refusal, square-frame admission and rejection of fire on Nanite chunks.
- Saved-map readback verifies the preceding 7,135 world + 116 Mover triangles,
  positions, cyclic winding, UVs, source material data, Lumen settings and lights.
  The new verifier checks both imported atlas sizes/settings, material parent,
  engine-function use, animation parameters and all five explicit overrides.
- GPU validation draws every frame of each real material into a temporary render
  target with frozen phase. **All 64 frames are nonblank and distinct for each
  texture**. Targets and dynamic instances are transient; saved playback settings
  are unchanged. Native castle captures were inspected after the addressing fix.
- Source map, T3D, geometry, prepared material buffers/images and original texture
  packages remain unchanged. The project contains no C++ change or new build
  claim, new application install, or modified app bundle.

## Next checkpoint

`Liquids.liquid2` is a WetTexture with three serialized drops and a reference to
`genfluid.Water.Water`. Its 278 triangles remain transparent placeholders. Read
that source image and drop data before implementing a bounded water preview.
Original sky, camera timing/looping, sound, collision and richer modern art remain
separate milestones. The current flames do not establish original animation
fidelity or a finished AAA effects pass.
