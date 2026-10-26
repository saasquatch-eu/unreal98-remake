# UR-002: minimal native C++ project

## Scope

The project is now named **UnrealGoldRemake**. Commands below use the current
name; the verification record retains the original UnrealRemaster names and
paths used when UR-002 was executed.

Create a UE5 C++ project that builds and opens on the primary Mac. The project
contains one runtime module and Game/Editor target definitions. The module only
logs its startup; no gameplay, conversion, importer, or original content is added.
The engine's empty Entry map is referenced for startup rather than copied.

UE 5.8.4 is pinned in `engine-version.json`. Targets use the installed engine's
V7 build settings and UE 5.8 include order. Android File Server is disabled because
this foundation targets macOS and does not need its generated connection settings.

## Repeatable commands

Run from the repository root:

```sh
bash scripts/build-ue5.sh
bash scripts/open-ue5.sh
```

The build script checks prerequisites and engine version before invoking:

```sh
bash "$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" \
  UnrealGoldRemakeEditor Mac Development \
  "-Project=$PWD/ue5/UnrealGoldRemake/UnrealGoldRemake.uproject" \
  -architecture=arm64 -WaitMutex -NoHotReloadFromIDE
```

`UE_ROOT` defaults to `/Users/Shared/Epic Games/UE_5.8`. The wrapper keeps a log at
`.local/logs/ue5-build.log` and propagates build failures through its logging pipe.
The launch wrapper checks that the project and compiled module exist, then opens
them in the selected engine. No system software is installed by either wrapper.

## Verification on 2026-10-26

- macOS 27.0.1, Xcode 27.1, macOS SDK 27.0, Apple M4 Max, native arm64.
- The first build compiled `UnrealRemaster.cpp`, linked its module, and returned
  `Result: Succeeded` in 61.06 seconds. The descriptor update disabling Android
  File Server was rebuilt successfully in 2.62 seconds.
- Build receipt: target `UnrealRemasterEditor`, platform `Mac`, configuration
  `Development`, architecture `arm64`.
- `file` and `lipo -verify_arch arm64` confirmed the native output at
  `ue5/UnrealRemaster/Binaries/Mac/libUnrealEditor-UnrealRemaster.dylib`.
- An actual GUI editor launch logged `UnrealRemaster primary C++ module loaded.`,
  initialized Metal with the M4 Max adapter, and completed engine initialization.
- `/Engine/Maps/Entry` loaded. Its map check reported zero errors and warnings.
- Editor logs are local/ignored under `.local/logs/`. No generated engine content,
  compiled modules, caches, or original Unreal packages are part of the commit.

The first launch's engine self-test messages match
[UE-305638](https://issues.unrealengine.com/issue/UE-305638): structured logging tests
compare fixed decimal strings under a comma-decimal locale. The project's module
loaded and the editor completed initialization despite those messages. The user
then requested English language and locale; per-user preferences were updated
with a backup, without changing macOS or game localization.

The rebuilt project was then opened again without a command-line culture override.
The saved English preferences took effect: map-check output is English, the C++
module loaded again, and initialization completed. That follow-up log contains no
`Error:` or fatal-error entries; the locale-related self-test errors are absent.
The final startup log is `.local/logs/ue5-editor-english.log`.

## Limits and next issue

This verifies the native Editor build and project startup. The Game target is
defined but a standalone/cooked game has not been built. No gameplay, visual
fidelity, save/load, original map export, or conversion has been tested. No live
editor MCP connection is configured yet; startup was verified through native
engine commands, binary inspection, and editor logs.

Next assigned work can be UR-003: inspect a real user-supplied local map export
before implementing extraction or parser behavior.
