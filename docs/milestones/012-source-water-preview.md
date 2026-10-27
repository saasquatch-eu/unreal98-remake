# Castle intro: animated source-image water preview

Completed locally on 2026-10-27 in UnrealGoldRemake / UE 5.8.4 on the existing
M4 Max. `Liquids.liquid2` now has a lit, translucent animated preview on its
278 original triangles. Both flame previews and the Lumen lighting pass remain
in place. Original sky behavior, flyby playback and gameplay remain unfinished.

## Source and fidelity boundary

The v61 WetTexture stores a single empty 256 × 256 mip, a reference to
`genfluid.Water.Water`, the external `genfluid.Palette149` palette, WaveAmp = 128
and three eight-byte HorizontalOsc drop records. The referenced image is an
ordinary P8 Texture, also 256 × 256. Its palette matches the WetTexture's reference.
The source dependency is now inventoried with its package/export/palette/mip
hashes; source files are read without modification.

`water61.py` validates the class, dimensions, mip header, complete native tail,
references, drop count, contiguous property indices, ADrop structure sizes, type
and coordinate bounds. The property reader still rejects large static array
indices; this decoder deliberately admits at most 128 records, although the
reference class defines a larger maximum. Only HorizontalOsc has a preview;
other valid native types are recorded but rejected by the renderer.

Raw properties and all drop bytes remain in the private recipe. The independent
preview uses raw X/Y positions and depths as anchors/weights for periodic
horizontal oscillators, scaled by WaveAmp. Native simulation-grid scaling and
byte_a..d semantics have not been inferred. Each output pixel samples the same
row of the original image with wraparound; no new image colors are painted.
Wave speeds, displacement, four-second duration and 16 FPS are authored choices,
not measured native behavior. Zero amplitude/displacement preserves the image,
and phase 1 matches phase 0 exactly. This is not a native WetTexture solver or an
original-game frame match.

The archived [1998 animating-textures manual by Erik de Neve](https://unrealarchive.org/unreal-tournament/documents/reference/unrealed/unreal-animating-real-time-textures-manual/index.html)
describes WetTexture as horizontal source-image distortion. The pinned
[WetTexture](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Fire/Classes/WetTexture.uc)
and [WaterTexture](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Fire/Classes/WaterTexture.uc)
definitions establish the references and record fields. The reader is checked
against actual byte consumption and synthetic packages. Reference code is not
copied into the repository.

## UE5 representation

The original image is imported as
`Textures/genfluid/Water/Water_ue5`. A derived 64-frame, 8 × 8 atlas is imported as
`Textures/Liquids/Flipbook/liquid2_ue5`. Each 256 × 256 frame has two-pixel repeat
padding, yielding 2,080 × 2,080 pixels. Unlike the flame's clear padding, water
padding copies opposite frame edges, preserving tile sampling. Water uses
unmasked RGBA colors, wrap addressing, bilinear filtering and no atlas mipmaps.
The existing flame atlas behavior is unchanged.

The water's source flags specify lit, translucent, two-sided surfaces. A separate
`Materials/UE5/Unreal_WaterFlipbook_ue5` parent duplicates the project's authored
animation graph, reuses the engine FlipBook function and supplies default-lit
surface forward shading. Its base color is sampled from the water atlas.
`Materials/Liquids/animated/liquid2_ue5` sets opacity 0.7, roughness 0.2 and color
strength 1. These are preview values. Modern alpha translucency approximates the
legacy blend; screen refraction, displaced geometry and a high-quality water
reflection target have not been established.

Diagnostic emission is zero in the saved scene. GPU checks enable it only on a
transient dynamic instance because canvas render-target tests read emissive
output. Saved scene material values are checked separately, and the actual lit
water appearance was inspected in a native moat capture.

Thirteen explicit component material overrides replace only the original water
slots. Five flame overrides remain intact. Every other world slot must still
resolve to its recorded source material. No mesh buffers, triangle material IDs,
UVs, canonical source references or light settings are changed. Water remains on
the non-shadowing raster path, outside Nanite and distance-field lighting.

## Run locally

Complete the flame checkpoint first. Prepare a new private directory:

```sh
.venv/bin/python -m ue1_converter.water_prepare \
  data/converted/Unreal/Maps/Unreal/materials-ready/Unreal.materials.json \
  data/converted/Unreal/Maps/Unreal/lighting-ready/Unreal.lighting.json \
  data/converted/Unreal/Maps/Unreal/fire-ready/Unreal.fire.json \
  --texture-root "$HOME/Library/Application Support/Unreal/Textures" \
  --output-dir data/converted/Unreal/Maps/Unreal/water-ready
```

Preparation validates the preceding manifest relationship, source water package,
bound mesh-buffer hashes, palette relationship and matching image dimensions.
The new source image dependency is hashed on admission. Existing output folders,
static-image warps and incompatible material/Nanite flags are rejected.

Save work and stop PIE, then run in the existing editor Python console:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_water.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_water.py', run_name='__main__')
```

Use the actual repository path. Apply requires empty destinations, checks the
complete flame baseline and makes a unique map backup under
`.local/water-recovery/`. Partial new assets require inspection/recovery before
retrying. Use the water verifier after this stage: the earlier flame-only
verification intentionally rejects unrecorded overrides. The water verifier
supplies an explicit checked water-binding contract and verifies the combined
scene without weakening geometry checks.

All game-derived outputs and UE assets stay private and ignored. No additional
application, external asset provider, engine-bundle edit or C++ change was needed.

## Executed checks and recovery

- **196 Python tests passed**, including 26 new tests for native water records,
  malformed layouts, exact source references/bytes, periodic horizontal sampling,
  zero-amplitude identity, unsupported motion, wrapped gutters, unmasked palette
  zero, deterministic outputs, exact slot binding, provenance, overwrite refusal
  and rejected material/Nanite/static-image cases.
- Saved-map reload verifies all 7,135 world + 116 Mover triangles, positions,
  cyclic winding, UVs and source material data, the Lumen/light settings, all
  visible water/flame bindings, atlas settings and saved material parameters.
- **All 64 water frames are nonblank and distinct on the GPU.** Both flame
  materials also retain 64 nonblank, distinct GPU frames. GPU checks use temporary
  targets/instances and preserve zero water diagnostic emission in the map.
- A keyboard-automation focus change caused a Backspace to delete one derived
  effect actor before import. Preflight caught the missing actor. Only that actor
  was restored from its checked mesh recipe and flame bindings; a recovery map
  copy was retained. Complete saved-scene verification passed afterward. Console
  automation now submits a complete command in one call after checking the field;
  separate Select All/Backspace actions are prohibited in project guidance.
- Original map/export, geometry, prepared material images/buffers, original texture
  packages and the prior flame atlases remain unchanged. New water preparation is
  reproducible. No C++ compilation or measured performance target is claimed.

## Next checkpoint

Restore the original sky behavior and verify the timed camera loop against the
running original. Collision, water volumes/swimming, audio, final physical scale
and the later modern art/material pass remain separate work. This visual preview
does not establish gameplay behavior or original water-animation fidelity.
