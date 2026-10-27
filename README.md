# UnrealGoldRemake

A planned Unreal Engine 5 visual remaster that preserves the original gameplay,
level geometry, atmosphere, and pacing. This is an independent personal project.

**Status: castle geometry imported into a private UE5 inspection map.**
UnrealGoldRemake has its native Mac arm64 foundation. The local tooling extracts
original evaluated BSP, preserves provenance and prepares UE5 mesh buffers.
The first import contains all 7,251 triangles across the world and two separate
Movers. Saved-map checks cover geometry, placement and disabled collision.
The lit preview is still overexposed; original materials, sky behavior, collision
and flyby playback remain future work. See the
[UE5 import report](docs/milestones/008-ue5-intro-import.md) and
[evaluated geometry report](docs/milestones/007-evaluated-geometry.md).

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
`Maps/Unreal_ue5.umap` and `Cinematics/Unreal_ue5.uasset`. The private inspection map and three mesh assets now exist locally; Cinematics
assets remain future work. The editor still starts with Entry.

See [resource naming](docs/resource-naming.md) and the
[intro preparation report](docs/milestones/003-unreal-intro-preparation.md).
The evaluated extraction is under ignored `data/converted/Unreal/Maps/Unreal/geometry-final/`,
including `Unreal.geometry.json`, `Unreal_ue5.obj`, and diagnostic PNGs. These
are local game-derived outputs; only the tooling and synthetic tests are in Git.
The private UE5 recipe and buffers are under `ue5-import-ready/` beside that
bundle. See the import report for commands, recovery notes and current limits.
Next are exposure and original UV/material reconstruction, followed by collision,
sky behavior, and camera playback verification.
