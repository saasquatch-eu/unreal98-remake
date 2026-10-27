# Castle intro: original texture colors and UVs

Completed on 2026-10-27 in the existing UnrealGoldRemake project. The inspection
map now shows original stone, wood, roofs, ground and metal images with their
source UV placement. Exposure is readable. This is a static material baseline,
not the finished original intro or a modern graphics pass.

## Result

| Item | Result |
| --- | --- |
| Original texture paths referenced by visible faces | 28 |
| Decoded / imported ordinary P8 textures | 25 |
| Deferred procedural texture paths | 3 |
| Original-color material instances | 26 |
| Transparent procedural placeholder instances | 3 |
| Shared material parents | 5 |
| Triangles with original texture colors | 6,771 |
| Preserved triangles for pending procedural effects | 406 |
| Mover triangles with omitted source texture assignments | 74 |
| Total preserved triangles | 7,251 |

The existing `/Game/Unreal/Maps/Unreal_ue5` and its three meshes are updated locally.
Texture names, case, package/group directories and hyphens are retained, with
`_ue5` on UE5 resources. Material variants add a mode directory, for example:

- `Textures/NaliCast/Wall/wmcs_ue5`
- `Materials/NaliCast/Wall/opaque/wmcs_ue5`
- `Materials/NaliCast/Mask/masked_two_sided/Grate3-m_ue5`

New generic parents live under `Materials/UE5/Original_<mode>_ue5`. Existing
engine materials were inspected first: BasicShapeMaterial has no texture
parameter, while EmissiveTexturedMaterial does not cover lit / masked surfaces.
Small shared parents expose OriginalColor and, for lit surfaces, Roughness.
Instances reuse those parents. No external asset generator or new application
was used. All game-derived images, mesh buffers, UE5 assets and captures stay
private and ignored; the PR contains tooling, synthetic fixtures and notes.

## Texture and UV contract

`texture61.py` reads ordinary Texture objects and their local Palette from v61,
licensee-zero packages. The existing table reader remains strict by default;
texture preparation explicitly accepts the `PKG_AllowDownload` flag (bit 0).
That is a serialized package flag, not a network operation. Other flags and
versions remain rejected. Source bytes are never patched or rewritten.

The decoder checks property boundaries, class-aware object paths, local palette
references, 256 palette colors, P8 format, power-of-two sizes, mip dimensions,
byte counts and exact consumption of native data. Small static property-array
indices are read; extended array indices and state frames remain unsupported.
A texture and palette can share the same object path, so names alone are not
used to choose the texture. Export, palette, every mip and source-package hashes
are recorded. Top mip pixels are exported as TGA; original mip metadata stays in
the manifest, while UE5 generates its own render mip chain.

Palette color channels are serialized RGBA. The legacy fourth channel is not
used as surface opacity: masked materials use palette index zero as transparent.
TGA output records top-left row order and BGRA bytes explicitly. UE5 textures
use repeat addressing and sRGB sampling as an inspection assumption; exact
original display gamma has not been matched. Texture compression and a uniform
roughness do not reproduce original shading or provide modern PBR detail.

Each face's stored texel coordinates become `(u / width, v / height)`. There is
no V flip, clamp, or reapplication of brush transforms. Triangle-corner UVs stay
paired with their vertices when the previous UE5 winding is retained. Source
positions and normals are unchanged. Full-precision UV0 is enabled to preserve
repeated and negative coordinates. UVs for procedural surfaces use their
serialized dimensions too, even while their visual effect is pending.

Masked and two-sided variants are represented. Legacy translucent blending uses
an additive approximation in this baseline; original lighting, detail textures,
animated surface flags, exact blending and original atmosphere remain pending.
Source flags / names remain in the preceding geometry bundle.

## Exposure and procedural effects

The previous histogram inspection exposure washed out the scene. A shared editor
helper now uses manual exposure with physical-camera exposure disabled and a
-13 EV compensation for the existing 100,000 lux inspection sun. Min/max
histogram overrides are disabled. Saved-map reload confirms the manual mode and
compensation persist. Sun and sky were not artistically rebuilt in this pass.

Three references use native procedural classes rather than ordinary images:

- `Liquids.liquid2`: WetTexture, 256 x 256.
- `NALIFX.SHANEFX.TORCHES2`: FireTexture, 128 x 128.
- `NALIFX.flames1`: FireTexture, 128 x 128.

They have explicit transparent preview instances with PreviewOpacity = 0. Their
geometry, dimensions, UVs and references remain intact. This avoids opaque white
flame billboards covering the entrance while those effects are unfinished.
They are not rendered effects yet. Missing Mover texture assignments retain the
existing neutral material rather than receiving an invented original texture.

## Run locally

Prepare a new output directory using the existing repository `.venv`:

```sh
.venv/bin/python -m ue1_converter.material_prepare \
  data/converted/Unreal/Maps/Unreal/geometry-final/Unreal.geometry.json \
  data/converted/Unreal/Maps/Unreal/ue5-import-ready/Unreal.import.json \
  --texture-root "$HOME/Library/Application Support/Unreal/Textures" \
  --output-dir data/converted/Unreal/Maps/Unreal/materials-ready
```

The tool refuses an existing output directory. Open the inspection map, save
work, stop PIE and run in Unreal's existing Python console:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_materials.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_materials.py', run_name='__main__')
```

Use the actual repository path. New texture/material destinations must be empty.
Existing inspection geometry must match the preceding checkpoint before being
updated. A private map / mesh backup is made under `.local/materials-recovery/`.
A failure can leave newly created resources; inspect the error and recovery
backup rather than blindly retrying. The verifier switches maps, so save first.

UE5.8's texture-parameter setter returns false even after assignment in the
installed engine implementation. The tool verifies the parameter's actual
readback instead. It does not treat the false return as success without evidence.

## Executed checks

- `bash scripts/run-tests.sh`: **131 passed** (25 new tests, all 106 prior tests).
- Synthetic packages check palette channels / mask semantics, asymmetric image
  row order, multiple mips, same-named palettes, package flag opt-in, invalid
  dimensions, formats, references, native tails and truncated data.
- Synthetic material preparation checks normalized negative/repeated UVs,
  unchanged positions / normals / winding, material IDs, procedural deferral,
  source checksums, safe paths and overwrite refusal.
- Actual editor import and saved-map reload passed. Readback matched every
  triangle's positions, cyclic winding, UV0 and material ID at StaticMesh float
  precision; texture dimensions, saved instance parameters, slots, absence of
  actor overrides, exposure, NoCollision and actor placements were checked.
- Map reload reported zero map-check errors or warnings. Source package / raw
  export / geometry / texture-package hashes remain unchanged. Generated output
  is ignored. The editor stayed running through this pass; C++ was unchanged,
  and no new C++ build pass is claimed.
- Decoded images were visually inspected in a contact sheet using the already
  available Python image library. Native UE5 captures were inspected, including
  the recorded first source-camera pose. A source ray check identified the
  entrance placeholder panels as FireTexture surfaces. No matching original-game
  frame comparison, original lighting fidelity or performance target is claimed.

References: OldUnreal's pinned [texture interface](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UTexture.h)
and [color serialization definitions](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/UnColor.h).
The bounded v61 native layout is checked against complete table consumption and
authored fixtures; this is not a universal texture-package decoder. Engine source
was consulted as a reference and is not copied into the repository.

## Next checkpoint

Reconstruct procedural water / fire and original sky behavior, then verify camera
path timing and looping against the running original. Keep collision and the
unresolved physical scale separate from this inspection scene.

After the faithful baseline works, the agreed visual direction is to polish one
castle shot with richer geometry, materials, lighting and effects, agree on its
look with the user, and measure Mac performance before expanding. AAA quality is
a target for that later art pass, not a claim about these original low-resolution
textures or an automatic result of importing into UE5.
