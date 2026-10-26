# Environment inspection

Validated on **2026-10-26**. UR-002's native editor target compiled successfully
and the editor loaded the project's C++ module and empty startup map.

| Item | Observed |
| --- | --- |
| Project directory | `/Users/arekczub14/Repos/SaaSquatch/unreal98-remake` |
| macOS | 27.0.1, build 26A434 |
| Process and project library architecture | `arm64` |
| CPU / memory | Apple M4 Max / 64 GiB, verified with `sysctl` |
| Git | 2.54.0 (Apple Git-157) |
| Active developer directory | `/Applications/Xcode.app/Contents/Developer` |
| Xcode / macOS SDK | 27.1 (27A9275) / 27.0 |
| Metal compiler | 32023.921; its version command executes successfully |
| UE installation | `/Users/Shared/Epic Games/UE_5.8` |
| UE version | 5.8.4, changelist 58902052 |
| Default Python | `/usr/bin/python3`, 3.9.6; too old for project tooling |
| Local Python | `.venv`, Python 3.12.14, native arm64, from the existing Codex runtime |
| Test dependency | pytest 9.1.1, installed in `.venv` only |
| GitHub repository | `saasquatch-eu/unreal98-remake`, private, default branch `main` |
| Optional tools | Git LFS, GitHub CLI, and Blender were not installed during setup |

The initial Xcode/Metal launch blockers were resolved by the user and rechecked:
full Xcode is now selected and the Metal compiler runs. The preflight executes
compiler version commands, rather than merely checking for shim paths.

## Executed checks

| Check | Result |
| --- | --- |
| macOS preflight | Exit 0, no required failures |
| Native editor build | UnrealGoldRemakeEditor / Mac / Development / arm64; succeeded |
| Built library architecture | `lipo` verified arm64; `file` reports a native arm64 dylib |
| Project module loading | Startup log confirms the primary C++ module loaded |
| Editor and Metal startup | Engine initialization, M4 Max adapter, and Metal viewport creation confirmed in log |
| Startup map | Engine Entry map loaded; map check reports 0 errors and 0 warnings |
| Python installation smoke test | 1 passed during setup |
| Python dependency check | No broken requirements during setup |
| Changed shell scripts | `bash -n` passed |
| Direct editor connection | Native MCP queries identify UnrealGoldRemake, Entry, and Play mode off |

The user requested English editor language and locale. These preferences are
stored in the user's UE 5.8 `EditorSettings.ini`, with a local backup under
`.local/backups/`. They are not game localization settings or macOS preferences.
Already-open editor windows need restarting to pick up that preference.

Unreal's built-in structured-log self-tests initially emitted locale-sensitive
errors under Polish, matching [Epic issue UE-305638](https://issues.unrealengine.com/issue/UE-305638).
After switching the user's editor language and locale to English, a fresh launch
completed with English map-check output and no `Error:` entries. The built-in
self-test messages were absent. No engine source was edited.

The virtual environment depends on the existing Codex runtime cache. A standalone
Python installation can replace it later with approval. Only the editor target has
been compiled; standalone builds, packaging, gameplay, and original content
conversion remain outside this milestone. Detailed commands and evidence are in
`milestones/002-native-cpp-project.md`. The renamed editor target was rebuilt
successfully in 20.18 seconds after moving the old generated outputs to a local
backup. Current connection and rename evidence is in
`milestones/004-editor-connection-project-rename.md`.
