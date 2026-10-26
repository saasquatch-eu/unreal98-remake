# Environment inspection

Inspected on **2026-10-26**. Python setup is ready. Unreal Editor setup remains
blocked by the active developer directory and missing Metal Toolchain, confirmed
after the user reported a failed launch. The initial preflight was insufficient:
it checked compiler paths without executing Metal and used a temporary Xcode
override. The corrected preflight reports these blockers.

| Item | Observed |
| --- | --- |
| Project directory | `/Users/arekczub14/Repos/SaaSquatch/unreal98-remake` |
| macOS | 27.0.1, build 26A434 |
| Process architecture | `arm64` |
| CPU/RAM | Apple M4 Max / 68,719,476,736 bytes (64 GiB), verified with `sysctl` |
| Free space | Approximately 154 GiB on the system volume at inspection |
| Git | 2.54.0 (Apple Git-157) |
| Active developer directory | `/Library/Developer/CommandLineTools` |
| Full Xcode | 27.1, build 27A9275, `/Applications/Xcode.app` |
| macOS SDK | 27.0, resolved with a process-local `DEVELOPER_DIR` |
| Xcode first-launch status | `xcodebuild -checkFirstLaunchStatus` returned 0 |
| Clang/Metal | Paths resolve, but executing Metal reports a missing Metal Toolchain |
| UE install | `/Users/Shared/Epic Games/UE_5.8` |
| UE version | 5.8.4, changelist 58902052 |
| UE Editor architecture | Universal binary containing arm64 and x86_64 |
| Engine Xcode range | Local `Engine/Config/Apple/Apple_SDK.json`: 15.2.0–27.9.0 |
| Default Python | `/usr/bin/python3`, 3.9.6; insufficient for project tooling |
| Available alternate Python | Existing Codex runtime, 3.12.14 |
| Local Python environment | `.venv`, Python 3.12.14, native arm64 |
| Test dependency | pytest 9.1.1, installed only in `.venv` |
| Local repository | `setup/bootstrap`; files uncommitted; no remote configured |
| Git LFS / GitHub CLI / Blender | Not found in inspected standard locations/PATH |

The local engine range is a build-tool version check, not evidence that this OS,
SDK, and Xcode combination compiles or runs a project. The published requirements
and local engine metadata differ; retain the installed baseline until a real
build establishes compatibility.

No system software was installed/updated and no global configuration was changed.
Xcode emitted cache/event-stream warnings under the sandbox but returned its
version and SDK successfully. The user attempted editor launch and received the
"Xcode not found" dialog. Successful launch, UE compilation, rendering, and game
behavior remain unverified. The assignment is still limited to setup.

## Executed setup checks

| Check | Result |
| --- | --- |
| `bash scripts/run-tests.sh` | 1 passed; installed package imports from outside the repository |
| `bash scripts/validate-macos.sh` | Original path-only check returned 0; corrected check reports the developer-directory and Metal blockers |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `bash -n` on all three shell scripts | Passed |
| Python syntax, `pyproject.toml`, and `engine-version.json` parsing | Passed |
| Setup with system Python 3.9 before `.venv` creation | Correctly returned exit 1 without creating `.venv` |
| Preflight with a nonexistent `UE_ROOT` | Correctly returned exit 1 |
| Git ignore checks | Local environment, private exports, and nested UE build outputs ignored; future source and synthetic fixtures permitted |

Required setup fixes: select full Xcode for GUI launches and install its Metal
Toolchain. See `setup-macos.md` for administrator-approved manual commands. No
system configuration or component installation has been performed by the agent.

Other notes: Git LFS is absent and the virtual environment depends on the
pre-existing Codex runtime cache. A standalone Python installation can replace
that dependency after separate approval.

Next issue, only when the user requests development: **UR-002**, create and compile
the minimal UE C++ project. No engine build was attempted during setup.
