# Asset pipeline boundaries

Work from the user's local installation; keep originals outside the repository.
The original resources are under `~/Library/Application Support/Unreal/`, and
the native tools/script packages are in `/Applications/Unreal.app`.

The bundled 227k UCC has successfully exported both `Unreal.unr` (castle intro)
and `Vortex2.unr` (Vortex Rikers) with its `batchexport ... level t3d` command.
Experiments used scratch settings, `-nohomedir`, private map copies, and explicit
log/output paths. Original-map and settings hashes were checked unchanged.

The castle intro is the first content target. Preserve each map's original name:

1. Raw exports: `data/local/Unreal/Maps/<Map>/<Map>.t3d`.
2. Private intermediate output: `data/converted/Unreal/Maps/<Map>/`, with shared
   resources grouped by original package and group under the other categories.
3. Future UE5 assets: `ue5/UnrealGoldRemake/Content/Unreal/`, with the `_ue5` suffix
   on asset names. These imported assets remain ignored pending rights review.

See `resource-naming.md` for concrete source-name mappings. The folders exist;
a private inspection report is now generated under `data/converted/Unreal/Maps/Unreal/`.
The geometry bundle and diagnostic OBJ are now generated locally; imported UE5
assets have not been created.

The current geometry path reads the original compiled BSP through Level.Model,
preserving its evaluated cuts. It does not rebuild the original CSG sequence.
Sky masks, sky-zone geometry, invisible/portal flags, texture paths, and zone
metadata remain classified in the private geometry JSON. The visible world
and separate Mover rest geometry are exported to `Unreal_ue5.obj`.

UE5 import must still establish scale, orientation, normalized UVs, materials,
collision, and sky behavior. Individual brush meshes must not be assumed to
reconstruct the playable space.

The T3D exports contain brush descriptions and actors, not proven evaluated room
meshes. The source parser preserves ordered actors, raw properties, shared brush
references, polygon vertices, and texture basis/pan data. Its inspection command
has synthetic tests and a documented report contract. New CSG rebuilding, UE5 coordinate scaling, UV application, collision, and camera
reconstruction remain unverified.
See `milestones/005-unreal-intro-inspection.md` for observed source ambiguities
that were identified before geometry conversion. The subsequent coordinate
audit (`milestones/006-brush-validation.md`) binds four malformed pivot
components to original binary values without rewriting the export. It audits
186 brush transforms. The original compiled-BSP extraction is documented in
`milestones/007-evaluated-geometry.md`; UE5 solidity/sky behavior and runtime
comparison remain outstanding.
