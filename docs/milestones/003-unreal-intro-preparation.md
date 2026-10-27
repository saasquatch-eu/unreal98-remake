# Castle intro: export and folder preparation

## Current target

Reconstruct the original castle flyby as the first visual milestone. The original
map is **Unreal.unr**, confirmed by the installed game's `LocalMap=Unreal.unr`
setting. Use `Unreal` for source resources and `Unreal_ue5` for new UE5 assets.
Vortex Rikers (`Vortex2`) remains the later gameplay milestone.

## Executed export investigation

On 2026-10-26, the existing `/Applications/Unreal.app/Contents/MacOS/UCC` exported
a private copy of each map using its advertised `batchexport` command. The app's
version identifies as 227k. No other exporter or additional software was used.

```text
UCC batchexport <private-map-copy.unr> level t3d <private-output-directory>
    -nohomedir INI=<scratch.ini> USERINI=<scratch-user.ini> LOG=<scratch.log>
```

UCC returned exit 0, reported 0 warnings, and produced a nonempty T3D file for
each map. Begin/end blocks were balanced and each export contained one map plus
actors and brush polygons. Original map and user-settings hashes were unchanged
over each experiment. This was a structural check, not a full T3D parser or
geometry-fidelity test.

| Observation | Unreal (castle intro) | Vortex2 (later gameplay target) |
| --- | --- | --- |
| T3D bytes | 918,281 | 4,780,043 |
| Text lines | 19,551 | 101,890 |
| Actors | 359 | 1,559 |
| Brush blocks | 184 | 1,001 |
| Source brush polygons | 1,501 | 7,796 |
| CSG_Subtract properties | 61 | 201 |
| CSG_Add properties | 122 | 764 |
| InterpolationPoint actors | 31 | 0 |
| Mover actors | 2 | 35 |

Counts refer to exported source blocks/properties, not final evaluated polygons
or UE5 triangles. The intro also references `Flyby.Flyby` music. Its smaller
source representation supports beginning with it, but geometry and cinematic
behavior still require validation.

## Prepared output locations

- Raw intro export: `data/local/Unreal/Maps/Unreal/Unreal.t3d`.
- Retained Vortex export: `data/local/Unreal/Maps/Vortex2/Vortex2.t3d`.
- Conversion workspace: `data/converted/Unreal/`, currently empty.
- UE5 content categories: `ue5/UnrealGoldRemake/Content/Unreal/`, placeholders only.
- Naming/provenance rules: `../resource-naming.md`.

The original generic UCC filename was `MyLevel.t3d`. Renaming the stored exports
preserves their bytes and internal names. Local sidecars retain source identity,
exporter filename, command, log, structural inventory, and checksums. Original
game-derived content is ignored by Git, including future imported assets under
the prepared UE5 content root.

Folder checks confirmed 50 trackable placeholders, including original
package/group subfolders explicitly referenced by the intro. Both renamed T3D
files match their recorded SHA-256 hashes. Raw and converted outputs, and planned
UE5 `.umap`/`.uasset` paths, are ignored by Git. No placeholder binary assets were
fabricated. This is not a complete dependency inventory: additional references
may come from class defaults or other packages during later investigation.

## Subsequent work

The first source-inspection checkpoint is now complete; see
`005-unreal-intro-inspection.md`. The observations above record the original
folder-preparation stage. The inspection parser and report do not perform
CSG conversion or create UE5 assets.

## Remaining work from the preparation stage

1. Source parsing is complete: synthetic fixtures cover properties, original
   identifiers, raw transforms, polygon UV data, and source CSG order.
2. Establish evaluated BSP geometry; validate subtraction, scale, orientation,
   surface alignment, and sky zones before assuming brush meshes suffice.
3. Import geometry and the required texture/material/audio resources using the
   original names plus `_ue5` for UE5 assets.
4. Reconstruct the camera path from the 31 interpolation points and original
   runtime behavior, including timing, looping, and field of view.
5. Validate the intro in UE5 before moving to Vortex2 gameplay.

No conversion, camera reconstruction, asset import, or UE5 map creation has been
performed by the folder-preparation change. The existing project still opens
the engine's Entry map. No C++ changes require an engine rebuild in this step.
