# UnrealGoldRemake

**Continuing with another coding model?** Read the
[shared handoff](docs/CONTINUE.md) and [project rules](AGENTS.md) first.

A planned Unreal Engine 5 visual remaster that preserves the original gameplay,
level geometry, atmosphere, and pacing. This is an independent personal project.

**Status: castle geometry, original textures, Lumen lighting, and animated flame/water previews are in UE5.**
The private inspection map preserves all 7,251 source triangles and their UV/material
assignments. It now uses software Lumen, Nanite world chunks, Virtual Shadow Maps,
clouds, subtle fog and source-position lights. The reported shadow overflow is absent
in the checked castle view. Both original flame references now have animated
source-palette previews on their 128 triangles. Lit water now uses its original
image with animated distortion on 278 triangles. A darker overcast pass replaces
the golden sunset wash while preserving source light colors. The original star
textures and a scrolling cloud-sheet preview now form the sky background. All
three source moons are present, with two rotating at their exported yaw rates.
A looping source-position lightning preview now adds brief castle and cloud
flashes while preserving the gloomy baseline. A source-path camera and original
Flyby music/ambient recordings now play in a loop. The moat remains visible from above and the entrance floor renders solid.
Exact sky matching, collision, original HUD and animated props remain unfinished.
See the
[intro camera/audio report](docs/milestones/017-intro-camera-audio.md),
[lightning report](docs/milestones/016-source-lightning.md),
[moons report](docs/milestones/015-source-moons.md),
[sky background report](docs/milestones/014-original-sky-background.md),
[gloom lighting report](docs/milestones/013-gloom-lighting.md),
[water preview report](docs/milestones/012-source-water-preview.md),
[flame preview report](docs/milestones/011-source-flame-preview.md),
[Lumen lighting report](docs/milestones/010-lumen-lighting.md),
[original materials report](docs/milestones/009-original-materials.md) and
[UE5 import report](docs/milestones/008-ue5-intro-import.md).

## Setup

Use macOS on Apple Silicon, full Xcode, Python 3.12+, and Git. The installed engine
baseline is UE **5.8.4**, verified with Xcode 27.1 on this development Mac.

```sh
cd /Users/arekczub14/Repos/SaaSquatch/unreal98-remake
# Select an existing Python 3.12+ executable; never use Apple's Python 3.9.
PYTHON_BIN=/path/to/python3.12 bash scripts/setup-macos.sh
bash scripts/run-tests.sh
bash scripts/validate-macos.sh
```

Setup creates `.venv` and installs this package and pytest there. It does not
install system software, select Xcode globally, or download game assets.
See [the setup guide](docs/setup-macos.md) for exact local paths, overrides, and
manual actions, and [the environment report](docs/environment.md) for verified
results and outstanding work.

## Layout

| Path | Purpose |
| --- | --- |
| `docs/` | Setup, architecture boundaries, fidelity, and milestone notes |
| `tools/src/ue1_converter/` | Source inspection, binary evidence, compiled BSP extraction, and validation |
| `tools/tests/` | Synthetic parsing/inspection and CLI safety tests, installation smoke test |
| `tools/editor/` | Create-only UE5 importer and saved-map readback checks |
| `tools/{extract,convert,validate}/` | Reserved tooling directories |
| `schemas/` | Future intermediate representation contracts |
| `data/{fixtures,manifests}/` | Future synthetic fixtures and manifests |
| `data/local/Unreal/` | Private exports with original map/resource names; ignored |
| `data/converted/Unreal/` | Private reports, geometry bundles, and previews; ignored |
| `reference/` | Reference handling policy; local files remain ignored |
| `ue5/UnrealGoldRemake/` | Minimal C++ project, source targets, and configuration |
| `scripts/` | Local setup, validation, and test commands |

Original Unreal maps, textures, models, sounds, and source must remain local and
untracked. See [content and licensing boundaries](docs/legal-and-licensing.md).

## Build and open the project

```sh
bash scripts/build-ue5.sh
bash scripts/open-ue5.sh
```

You can also open `ue5/UnrealGoldRemake/UnrealGoldRemake.uproject` after the first
build. It opens the engine's empty Entry map. The generated private castle map can be
opened separately; it is not included in a fresh clone.
The build script validates prerequisites, selects the pinned engine, and saves
its log under ignored `.local/logs/`. `UE_ROOT` can override the engine location.

The project's editor connection uses UE5's bundled Unreal MCP plugins. See
[editor connection setup](docs/ue5-editor-connection.md) for local startup and
verification. Its port is restricted to localhost; per-user auto-start settings
remain under ignored `Saved/`.

See [UR-002 results](docs/milestones/002-native-cpp-project.md) for executed checks
and their limits. Development is tracked in the existing
[GitHub repository](https://github.com/saasquatch-eu/unreal98-remake).

The first content target is the **castle intro**, whose original filename is
`Unreal.unr`. Its raw export is `data/local/Unreal/Maps/Unreal/Unreal.t3d`. The
Vortex Rikers export is retained under `data/local/Unreal/Maps/Vortex2/Vortex2.t3d`.
Both are private and untracked. Inspect the castle export with:

```sh
.venv/bin/python -m ue1_converter inspect-t3d \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  --output data/converted/Unreal/Maps/Unreal/Unreal.inspection.json
```

Use `--force` to replace an existing inspection report. The command preserves
the source export and reports warnings without repairing values. Detailed
output contains game-derived data and must remain in the ignored local folders.

The prepared UE5 folders are under `ue5/UnrealGoldRemake/Content/Unreal/`. Future
intro assets use original source names plus `_ue5`, including
`Maps/Unreal_ue5.umap` and `Cinematics/Unreal_ue5.uasset`. The private inspection map, three canonical meshes and
60 lighting render chunks exist locally. Cinematics now contains a lightning
preview sequence and the camera flyby.
The editor still starts with Entry.

See [resource naming](docs/resource-naming.md) and the
[intro preparation report](docs/milestones/003-unreal-intro-preparation.md).
The evaluated extraction is under ignored `data/converted/Unreal/Maps/Unreal/geometry-final/`,
including `Unreal.geometry.json`, `Unreal_ue5.obj`, and diagnostic PNGs. These
are local game-derived outputs; only the tooling and synthetic tests are in Git.
The private UE5 recipe and buffers are under `ue5-import-ready/` beside that
bundle. See the import report for commands, recovery notes and current limits.
Original-color images and full UV/material buffers are under `materials-ready/`.
The Lumen recipe and lossless render chunks are under `lighting-ready/`.
The flame recipe/atlases are under `fire-ready/`; the water recipe, source image
and atlas are under `water-ready/`. The selected original sky textures and
compiled miniature buffers are under `sky-ready/`; moon buffers and skins are
under `moons-ready/`. The lightning recipe is under `lightning-ready/`.
The camera/audio recipe and private original recordings are under `intro-ready/`.
Next are original-game comparison, remaining animated actors and the title/menu.
Modern lighting is a foundation for the later material and geometry art pass.
