# Editor connection and project rename

Verified on 2026-10-26 with UE 5.8.4 on native Apple Silicon.

## Result

The UE5 project, runtime module, and Game/Editor targets are now named
**UnrealGoldRemake**. Open `ue5/UnrealGoldRemake/UnrealGoldRemake.uproject`
or run `bash scripts/open-ue5.sh` from the repository root. Build and validation
scripts, current documentation, and content ignore rules use the new path.
The GitHub repository and local repository directory retain their existing names.

The bundled ModelContextProtocol and AllToolsets plugins are enabled for Editor
targets. The MCP listener binds to `127.0.0.1:8000`; the installed Codex Unreal
plugin supplies the client connection. Local autostart preferences remain in
ignored Saved configuration. See [connection settings](../ue5-editor-connection.md).

## Verification

- Moved old Binaries, Intermediate, and DerivedDataCache outputs into ignored
  `.local/backups/UnrealRemaster-before-project-rename/` before rebuilding.
- `bash scripts/build-ue5.sh` succeeded in 20.18 seconds for
  UnrealGoldRemakeEditor / Mac / Development / arm64, compiling the renamed
  module and linking `libUnrealEditor-UnrealGoldRemake.dylib`.
- The resulting library is Mach-O arm64, and the target receipt names
  UnrealGoldRemakeEditor.
- Reopened the renamed project. The startup log confirms the renamed C++ module,
  engine initialization, localhost listener, and Entry map check with zero errors
  and warnings. The editor remains open.
- Native MCP calls return `projectName: UnrealGoldRemake`, current level
  `/Engine/Maps/Entry`, and Play mode off. The client recovered its session after
  the restart. Toolset and Agent Skill discovery were also verified during setup.
- Changed shell scripts passed `bash -n`; the macOS preflight passed with no
  required failures. `git diff --check` passed.
- The 50 content directory placeholders and ignored local editor preferences
  survived the move. Private map-export hashes and ignore rules were rechecked.

Private verification logs are under `.local/logs/`, including `ue5-build.log`
and `unrealgoldremake-editor-mcp.log`.

Original resources retain names such as `Unreal.t3d` and `Vortex2.t3d`. Future
UE5 content still receives `_ue5`, including `Unreal_ue5.umap`. No converted map,
gameplay, imported asset, or generated resource is included in this change.
