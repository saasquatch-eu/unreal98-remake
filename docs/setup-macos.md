# macOS setup

These commands apply to the repository root. They install only project-local
Python dependencies. System installation and updates require separate approval.

## Python

The shell currently resolves `/usr/bin/python3` (3.9.6), which is too old.
A pre-existing Codex runtime provides Python 3.12.14 and can bootstrap `.venv`
without a system installation:

```sh
cd /Users/arekczub14/Repos/SaaSquatch/unreal98-remake
PYTHON_BIN="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" \
  bash scripts/setup-macos.sh
bash scripts/run-tests.sh
bash scripts/validate-macos.sh
```

This is a local convenience, not a portable dependency on Codex: the runtime
cache can move or be removed. For an independent workstation setup, install a
standalone Python 3.12+ after approval and recreate `.venv` with that interpreter.
Do not move a virtual environment between directories. `PYTHON_BIN` can select
any existing suitable interpreter. Test/validation scripts default to `.venv`.

Setup downloads Python build/test dependencies from the configured pip index and
installs the local package editable. It never upgrades Apple's Python. Version
ranges live in `pyproject.toml`; transitive dependencies are not locked yet.

## Xcode and Unreal Engine

Full Xcode and Metal are now selected and working on the development Mac. For an
alternate installed Xcode or engine location, use process overrides:

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
export UE_ROOT="/Users/Shared/Epic Games/UE_5.8"
xcodebuild -version
xcrun --sdk macosx --show-sdk-version
bash scripts/validate-macos.sh
```

Without an explicit override, the validator reports a Command Line Tools system
selection as a failure for Finder/Launcher starts. It then uses full Xcode for
further diagnostics only. This does not change `xcode-select` globally.
Open Xcode manually if first-launch components or license prompts remain.
No first-launch installation or system selection changes are automated.

### Fixing the Editor's "Xcode not found" dialog

Inspection confirmed that the system still selects Command Line Tools and that
`xcrun metal --version` fails because the optional Metal Toolchain is missing.
The compiler path alone exists as a shim; resolving it does not prove the compiler
is installed. The validator now executes the compiler's version command.

Close the failed Editor launch. After approving the system configuration change
and component download, run these commands in Terminal:

```sh
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
xcodebuild -downloadComponent MetalToolchain
xcode-select -p
xcrun metal --version
```

The first command changes the default developer directory and may ask for your
Mac administrator password. The second downloads and installs the Metal component
for Xcode. Relaunch Unreal Editor once the compiler version command succeeds.
Alternatively, select Xcode 27.1 in Xcode > Settings > Locations > Command Line
Tools and install Metal Toolchain in Settings > Components.

Sources: [Apple: selecting Xcode](https://developer.apple.com/documentation/xcode/configuring-command-line-tools-settings),
[Apple: installing Metal Toolchain](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components).

The baseline in `engine-version.json` is the installed **5.8.4** engine, not a
claim of successful compilation. Epic's [macOS requirements for UE 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/macos-development-requirements-for-unreal-engine?application_version=5.8)
recommend Xcode 26.1.1; the installed engine SDK metadata accepts Xcode 27.1.
The installed OS/Xcode combination still needs an actual project build. Do not
replace Xcode or the engine solely on the basis of this setup preflight.

## Git and later dependencies

The project uses the existing private GitHub repository
`https://github.com/saasquatch-eu/unreal98-remake`. Use feature branches and pull
requests for review. Public distribution and the code license remain separate
decisions; no original Unreal assets are included.

Git LFS, Blender, and the GitHub CLI are optional at this stage and have not been
installed. Configure Git LFS before introducing permitted large binary assets.
No original game installations, exports, or assets are downloaded by setup.

## Build and open

The minimal project created in UR-002 is now named UnrealGoldRemake and lives at
`ue5/UnrealGoldRemake/UnrealGoldRemake.uproject`.
The following commands run from the repository root:

```sh
bash scripts/build-ue5.sh
bash scripts/open-ue5.sh
```

The first command validates the environment and builds UnrealGoldRemakeEditor for
Mac Development arm64. Its log is `.local/logs/ue5-build.log`. The second opens the
built project in the installed editor. The initial map is the engine's empty Entry
map. The project does not yet contain gameplay or converted content.

English interface language and locale were requested for this workstation. The
per-user preference is `[Internationalization]` with `Language=en` and `Locale=en`
in `~/Library/Application Support/Epic/UnrealEngine/5.8/Saved/Config/MacEditor/EditorSettings.ini`.
It takes effect on editor restart and is not committed as a project-wide setting.

See `milestones/002-native-cpp-project.md` for results and scope limits.
