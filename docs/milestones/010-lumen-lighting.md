# Castle intro: Lumen lighting checkpoint

Completed locally on 2026-10-27 in UnrealGoldRemake, UE 5.8.4, on an Apple M4 Max
using Metal SM6. The castle now uses software Lumen global illumination and
reflections, Virtual Shadow Maps, Nanite for opaque/masked world surfaces, TSR,
a warm directional light, source-position point lights, volumetric clouds and
subtle volumetric fog. This is a modern lighting foundation using the original
geometry and images; the original sky and animated effects remain unfinished.

## Geometry and shadow workload

The canonical world mesh remains as a hidden source reference. Its replacement
render representation groups complete triangles by centroid into 3,200-unit
cells, separating opaque/masked surfaces from transparent effects. There is no
retessellation, vertex movement, UV generation, winding reversal or material
substitution. Each chunk has only its used material slots; unused translucent
slots must not prevent Nanite support.

- 44 Nanite world chunks and 16 raster effect chunks preserve 7,135 world triangles.
- The two original Mover meshes preserve another 116 triangles, for 7,251 total.
- Raster effect chunks cast no shadows and do not participate in distance fields.
- Opaque/masked chunks use two-sided distance-field generation, resolution scale
  2 and a maximum of 64 Lumen cards. These settings improve the representation
  of the source's large, often thin surfaces without changing their geometry.
- Nanite retains 100% of input triangles with zero trim error. Fallback target is
  explicitly **Percent Triangles**, with 100% retained and zero relative error.
  Auto target reduced seven large fallback meshes despite the percentage value;
  explicit targeting restores all counts. Source Model and fallback triangle
  counts are both checked, while saved Source Model positions, cyclic winding,
  UV0 and material assignments must match the canonical world exactly.
- Source assets keep their original package/group names and `_ue5` suffix.
  Generated chunks use `Meshes/Lumen/Unreal_ChunkNNN_ue5` and
  `Unreal_EffectsNNN_ue5`. Original actor labels are retained in recipe metadata.

The initial broad non-Nanite shadow workload produced the reported VSM marking
queue overflow. Separating effects, enabling Nanite on eligible surfaces and
limiting point-light shadows addresses that workload. The checked castle view
no longer displayed the warning with
`r.Shadow.Virtual.AllowScreenOverflowMessages=1`; messages were not suppressed.
This is a checked view, not a guarantee for every future camera or level.

## Lighting choices and fidelity limits

The 27 steady `Light` actors in native BSP zone 1 use their original coordinates.
Twelve lights outside that zone are inventoried but excluded. Source actor
indices distinguish repeated names. Missing properties and the defaults used
are recorded explicitly; the original v61 class defaults have not been decoded.
Default assumptions are checked against the pinned
[OldUnreal Light reference](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Classes/Light.uc).

HSV colors and physical inverse-square lumen intensities are an explicit artistic
calibration of source bytes, not a conversion of native UE1 lightmaps. Radius uses
`LightRadius * 25 + 1` cm at the provisional inspection scale. Seven explicitly
marked source corona lights receive shadows; the remaining twenty provide fill.
The original brightness effects, coronas and distance lightning are not animated.

The key light uses 1,000 lux, pitch -12 degrees, yaw 125 degrees and a 2-degree
source angle. Manual exposure compensation is -6 EV, replacing the preceding
-13 EV inspection setup. Lumen lighting/final-gather/reflection quality overrides
are 2. Motion blur is disabled for this static inspection scene. Sky capture is
real time. Clouds use a project-local duplicate of the engine instance, coverage
-0.2, density 0.008 and a 3–8 km layer. Fog density is 0.000015. Engine materials
and application bundles are never edited.

The tested renderer uses software ray tracing and generated mesh distance fields.
Epic's current [Mac rendering requirements](https://dev.epicgames.com/documentation/unreal-engine/macos-development-requirements-for-unreal-engine?lang=en-US)
list software Lumen on M1+, Nanite/VSM as beta on M2+, and hardware Lumen/MegaLights
as experimental on M2+. Hardware ray tracing remains disabled in this checkpoint;
no hardware-ray-tracing or MegaLights validation is claimed. See also
[Lumen representation guidance](https://dev.epicgames.com/documentation/unreal-engine/lumen-technical-details-in-unreal-engine)
and [Virtual Shadow Maps](https://dev.epicgames.com/documentation/unreal-engine/virtual-shadow-maps-in-unreal-engine).
Thin or complex source surfaces can still have imperfect indirect lighting.

## Reproduce locally

First complete the material checkpoint, save work and stop PIE. The tracked
renderer configuration requires an editor restart. Prepare a new private folder:

```sh
.venv/bin/python -m ue1_converter.lighting_prepare \
  data/converted/Unreal/Maps/Unreal/materials-ready/Unreal.materials.json \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  "$HOME/Library/Application Support/Unreal/Maps/Unreal.unr" \
  --output-dir data/converted/Unreal/Maps/Unreal/lighting-ready
```

Preparation refuses an existing destination and checks source map/export,
geometry and material-buffer provenance. In the existing editor Python console:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_lumen_lighting.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_lumen_lighting.py', run_name='__main__')
```

Replace the absolute repository path. Apply requires the preceding inspection
baseline and empty new asset destinations. It makes a uniquely named backup of
the saved Maps/Meshes and current renderer config under `.local/lighting-recovery/`
before bulk edits. A failed pass can leave partial assets; inspect its report and
restore the recovery copy rather than blindly rerunning. Verification switches
maps, so save first. All outputs, reports, backups and generated UE assets remain
private and ignored. No new application or external asset service is required.

## Executed validation

- Python suite: **148 passed**, including 17 tests for exact partition attributes,
  determinism, negative cells, invalid dimensions/material counts, source light
  placement, default tracking, zone/type exclusions, duplicate actor names,
  invalid bytes, transparent separation and shadow selection.
- Saved-map reload verifies all 7,251 canonical triangles and their UV/material
  assignments, plus the exact 7,135-triangle visible world union. Fallback counts,
  full-precision UVs, Nanite settings, identity transforms, NoCollision, light
  positions/intensities/radii/shadows, renderer settings, manual exposure,
  project-local cloud parameters, fog and real-time sky capture are checked.
- Runtime Lumen stats recorded 46 mesh distance-field objects and 270 cards.
  Native viewport captures were inspected. Map checks reported zero errors and
  warnings. Original map/export, geometry, material buffers and source texture
  package hashes remain unchanged.
- An earlier editing session crashed with a Metal command-buffer out-of-memory
  error. The project reopened and saved-map verification passed. Recovery preview
  used a session-only 30 FPS cap and 66% screen percentage. These are not global
  project quality settings or measured performance results. Long-session stability
  and a target frame rate remain unverified.
- The installed realtime-toggle API produced a nonfatal ensure when asked to
  remove an override that did not exist. The unnecessary call was removed from
  the lighting script. C++ and engine binaries were unchanged; no new C++ build
  is claimed.

## Next checkpoint

Rebuild procedural fire and water, the original sky behavior and the timed camera
loop. The current lights illuminate positions where flame visuals are still
transparent placeholders. Collision, gameplay, final physical scale, richer PBR
materials and modern art detail remain separate work. This checkpoint does not
establish original atmosphere fidelity, finished flyby playback or AAA quality.
