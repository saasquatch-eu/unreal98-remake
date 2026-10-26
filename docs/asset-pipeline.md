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
2. Future intermediate output: `data/converted/Unreal/Maps/<Map>/`, with shared
   resources grouped by original package and group under the other categories.
3. Future UE5 assets: `ue5/UnrealGoldRemake/Content/Unreal/`, with the `_ue5` suffix
   on asset names. These imported assets remain ignored pending rights review.

See `resource-naming.md` for concrete source-name mappings. The folders exist;
conversion output and imported UE5 assets have not been generated.

BSP conversion must eventually use evaluated geometry and handle subtractive
volumes, UV alignment, coordinates, scaling, collision, materials, and transforms.
Individual brush meshes must not be assumed to reconstruct the playable space.

The T3D exports contain brush descriptions and actors, not proven evaluated room
meshes. Structural block checks passed, but CSG evaluation, coordinate scaling,
UVs, collision, and camera reconstruction remain unverified. Schemas, synthetic
fixtures, and reusable pipeline commands will be introduced with the relevant
parser/conversion work; the current experiments do not implement a converter.
