# UnrealGoldRemake

A planned Unreal Engine 5 visual remaster that preserves the original gameplay,
level geometry, atmosphere, and pacing. This is an independent personal project.

**Status: UR-002 native C++ foundation verified.** The minimal UE project builds
for Mac arm64 and opens in Unreal Editor. Conversion, importer, and gameplay work
have not started. The castle intro (`Unreal.unr`) is the first content target;
its native UCC export and private working folders are ready. The Python package
remains an empty, installable scaffold. The project is now named
**UnrealGoldRemake**, with a verified direct editor connection. See the
[connection and rename report](docs/milestones/004-editor-connection-project-rename.md).

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
| `tools/src/ue1_converter/` | Empty Python package for future conversion work |
| `tools/tests/` | Package installation smoke test |
| `tools/{extract,convert,validate}/` | Reserved tooling directories |
| `schemas/` | Future intermediate representation contracts |
| `data/{fixtures,manifests}/` | Future synthetic fixtures and manifests |
| `data/local/Unreal/` | Private exports with original map/resource names; ignored |
| `data/converted/Unreal/` | Private intermediate-content folders; ignored, empty |
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
build. It opens the engine's empty Entry map; no remaster level is expected yet.
The build script validates prerequisites, selects the pinned engine, and saves
its log under ignored `.local/logs/`. `UE_ROOT` can override the engine location.

The project's editor connection uses UE5's bundled Unreal MCP plugins. See
[editor connection setup](docs/ue5-editor-connection.md) for local startup and
verification. Its port is restricted to localhost; per-user auto-start settings
remain under ignored `Saved/`.

See [UR-002 results](docs/milestones/002-native-cpp-project.md) for executed checks
and their limits. Development is tracked in the existing private
[GitHub repository](https://github.com/saasquatch-eu/unreal98-remake).

The first content target is the **castle intro**, whose original filename is
`Unreal.unr`. Its raw export is `data/local/Unreal/Maps/Unreal/Unreal.t3d`. The
Vortex Rikers export is retained under `data/local/Unreal/Maps/Vortex2/Vortex2.t3d`.
Both are private and untracked.

The prepared UE5 folders are under `ue5/UnrealGoldRemake/Content/Unreal/`. Future
intro assets use original source names plus `_ue5`, including
`Maps/Unreal_ue5.umap` and `Cinematics/Unreal_ue5.uasset`. These assets do not exist
yet; the editor still opens Entry.

See [resource naming](docs/resource-naming.md) and the
[intro preparation report](docs/milestones/003-unreal-intro-preparation.md).
Next comes parsing the real intro export and validating evaluated BSP geometry,
before importing assets or recreating its flyby camera.
