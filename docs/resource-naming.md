# Resource names and locations

Preserve source names and case. The castle intro's map filename is `Unreal.unr`;
Vortex Rikers is `Vortex2.unr`. Use those identifiers for working files and assets.

## Naming rule

- Original installations are not renamed or edited.
- Raw/intermediate copies retain the original resource stem and package/group
  hierarchy. An export of `Unreal.unr` is stored as `Unreal.t3d`.
- New UE5 assets receive the lowercase suffix **`_ue5`**, immediately before their
  extension. Keep the original stem; do not add replacement display names or
  type prefixes such as `SM_`, `T_`, or `M_`.
- Preserve original actor instance identifiers in metadata. An asset filename
  suffix does not authorize rewriting actor names or links in the raw export.
- If UE5 rejects a source name, record the exact source-to-target mapping before
  applying the minimum necessary substitution. Never silently lowercase, flatten
  package groups, or rename colliding resources.
- For generated resources with no direct source object, use the original map stem
  and a descriptive part name when necessary, then `_ue5`. Record the provenance.
- This rule concerns content assets. It does not rename the existing C++ project,
  module, configuration files, documentation, or original game binaries.

## Canonical working directories

All paths below are relative to the repository root.

```text
data/local/Unreal/                    # private, ignored
  Maps/Unreal/Unreal.t3d              # exported and structurally checked
  Maps/Vortex2/Vortex2.t3d            # retained for the later gameplay milestone
  Textures/
  Sounds/
  Music/
  System/

data/converted/Unreal/                # private, ignored; reports and geometry bundles
  Maps/Unreal/
  Maps/Vortex2/
  Meshes/
  Textures/
  Sounds/
  Music/

ue5/UnrealGoldRemake/Content/Unreal/     # generated assets remain private and ignored
  Maps/
  Meshes/
  Textures/
  Materials/
  Sounds/
  Music/
  Cinematics/
  Blueprints/
```

UCC names the exported level object `MyLevel.t3d` for each map. The stored file is
renamed to the source map stem to avoid ambiguity; its bytes and internal object
names stay unchanged. Each map folder also holds `<Map>.export-summary.json`,
`<Map>.export-command.json`, `<Map>.source-baseline.json`, and `<Map>.ucc-export.log`.
The command/log preserve the actual experiment paths and original exporter name.

## Planned UE5 assets

These examples define naming. The castle inspection map, meshes and original
texture baseline now exist locally; other resource types remain future work.

| Source | Planned UE5 path below Content/Unreal |
| --- | --- |
| Map `Unreal.unr` | `Maps/Unreal_ue5.umap` |
| Map `Vortex2.unr` | `Maps/Vortex2_ue5.umap` |
| Texture `GenEarth.Rock.Rock1b` | `Textures/GenEarth/Rock/Rock1b_ue5.uasset` |
| Material derived from that texture | `Materials/GenEarth/Rock/Rock1b_ue5.uasset` |
| Sound `AmbOutside.Looping.wind01` | `Sounds/AmbOutside/Looping/wind01_ue5.uasset` |
| Music `Flyby.Flyby` | `Music/Flyby/Flyby_ue5.uasset` |
| Camera sequence reconstructed from `Unreal.unr` | `Cinematics/Unreal_ue5.uasset` |

Texture, sound, and music identifiers above were observed in the actual intro
export. Package/group directories prevent same-named objects in different source
packages from colliding. Inside UE5, Content maps to `/Game`, so the planned intro
level's package is `/Game/Unreal/Maps/Unreal_ue5`.

Game-derived raw, converted, and imported content remains private. Git ignores
the working-data roots and Content/Unreal asset files; only its `.gitkeep`
directory placeholders are versioned. No synthetic fixtures or independently
authored source code are hidden by that content-specific rule.

Material variants preserve package/group directories and add a mode folder before
the original stem, for example `Materials/NaliCast/Wall/opaque/wmcs_ue5.uasset`.
Generic shared parents use `Materials/UE5/Original_<mode>_ue5.uasset`. Procedural
placeholders use the `deferred` mode and retain their original source names.

Lumen render chunks are derived map resources under `Meshes/Lumen/`, named
`Unreal_ChunkNNN_ue5` for opaque/masked surfaces and `Unreal_EffectsNNN_ue5` for
transparent surfaces. The private recipe records source triangle indices and
original material references. The localized cloud instance is
`Materials/UE5/Unreal_Clouds_ue5`; the canonical world/Mover meshes keep their names.

Animated flame atlases retain original stems under `Textures/<package>/<group>/Flipbook/`;
instances use `Materials/<package>/<group>/animated/`. For example,
`Textures/NALIFX/SHANEFX/Flipbook/TORCHES2_ue5` and
`Materials/NALIFX/SHANEFX/animated/TORCHES2_ue5`. The shared independently authored
parent is `Materials/UE5/Unreal_FireFlipbook_ue5`. Deferred source materials remain
as provenance references; explicit raster actor overrides select the previews.

The source image for `Liquids.liquid2` retains its referenced package/group as
`Textures/genfluid/Water/Water_ue5`. Its derived atlas is
`Textures/Liquids/Flipbook/liquid2_ue5` and its preview instance is
`Materials/Liquids/animated/liquid2_ue5`. The separate authored lit parent is
`Materials/UE5/Unreal_WaterFlipbook_ue5`; the original deferred source slot stays
unchanged in the mesh, with an explicit raster actor override selecting the preview.
