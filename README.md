# Unreal (1998) Remake

A planned Unreal Engine 5 visual remaster that preserves the original gameplay,
level geometry, atmosphere, and pacing. This is an independent personal project.

**Status: setup only.** No conversion, importer, gameplay, or UE C++ project has
been implemented. The Python package is an empty, installable scaffold.

## Setup

Use macOS on Apple Silicon, full Xcode, Python 3.12+, and Git. The installed engine
baseline is UE **5.8.4**; compilation compatibility has not yet been established.

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
| `reference/` | Reference handling policy; local files remain ignored |
| `ue5/` | Reserved engine workspace; no `.uproject` yet |
| `scripts/` | Local setup, validation, and test commands |

Original Unreal maps, textures, models, sounds, and source must remain local and
untracked. See [content and licensing boundaries](docs/legal-and-licensing.md).

Next work, only when requested: UR-002, create and compile a minimal native UE C++
project. Conversion and gameplay work follow separate issues.
