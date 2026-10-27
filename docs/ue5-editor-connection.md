# Local UE5 editor connection

The project enables `ModelContextProtocol` and `AllToolsets` for **Editor targets
only**. Both plugins are bundled with the installed UE 5.8.4 engine; no additional
software or provider account is needed. This connection is for creating and
inspecting UE assets and editor state, not generating content through Meshy or
another external service.

`AllToolsets` enables the engine's Game Features dependency. `Config/DefaultGame.ini`
includes the GameFeatureData primary-asset rule required by that dependency. The
type is marked editor-only, matching this setup's scope and preventing a non-editor
game from trying to load the optional tool dependency. No game-feature assets or
gameplay systems are created by this rule.

## Engine and client settings

The endpoint is `http://127.0.0.1:8000/mcp`. `Config/DefaultEngine.ini` restricts
the HTTP listener for port 8000 to `127.0.0.1`.
Address reuse is enabled for this listener so a normal editor restart can rebind
the local port without waiting for closed TCP connections to expire.

The installed **Unreal Engine Skills for Codex** plugin already supplies that
endpoint in its bundled `mcp.json` and `.mcp.json`. Reuse it; do not add duplicate
entries to the project's or user's Codex configuration.

For this workstation, the ignored file
`ue5/UnrealGoldRemake/Saved/Config/MacEditor/EditorPerProjectUserSettings.ini`
contains:

```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
bAutoStartServer=True
bEnableToolSearch=True
ServerPortNumber=8000
ServerUrlPath=/mcp
```

Save any editor work before restarting. After enabling plugins, build using
`bash scripts/build-ue5.sh`, then open using `bash scripts/open-ue5.sh` or the
project descriptor. Local preference backups and diagnostic logs belong under
ignored `.local/`.

## Verification

A configured URL or a running editor alone does not establish a working
connection. Verify all of the following:

1. The project builds with its enabled plugins.
2. Unreal logs successful MCP startup and listener creation on localhost.
3. An MCP initialization and `tools/list` request succeed.
4. Discover toolsets and their current tool schemas, then execute a read-only
   query that identifies UnrealGoldRemake or its current editor world.
5. Discover any project Agent Skills before using unfamiliar live workflows.

With tool-search mode enabled, the native MCP catalog contains `list_toolsets`,
`describe_toolset`, and `call_tool`. Toolset operations are dispatched through
`call_tool`, using schemas obtained from discovery. Save affected assets before
bulk edits, wait for compilation to complete, and check every returned result.

If the server is verified but the chat still has no Unreal tools, reconnect the
installed Unreal plugin in Codex, or restart Codex so its client reconnects. Keep
the running editor open. Do not install a second server or optional proxy merely
to work around a stale client catalog.

## Troubleshooting

- If another process owns port 8000, identify it before choosing a different port.
  Do not stop unrelated services. A changed port must agree in the engine listener,
  local server preferences, and the one selected client connection.
- The editor console can start the server with `ModelContextProtocol.StartServer`
  and refresh tool registration with `ModelContextProtocol.RefreshTools`.
- Follow the installed Unreal MCP skill's operations reference for client refresh
  and optional proxy recovery; a proxy is not part of this direct configuration.

No original game content is sent to an external asset provider by this setup.

## Verified setup

On 2026-10-26, the native arm64 editor build succeeded with the enabled plugins.
The editor initialized, created its listener on `127.0.0.1:8000`, and completed
the Entry map check with zero errors and warnings. The final startup log contained
no `Error:` entries.

The Unreal MCP tools became available directly in the chat. Native read-only tool
calls returned the configured project name and `/Engine/Maps/Entry`; Play mode was
off and project Agent Skill discovery succeeded. The connection was verified
again after an editor restart and after renaming the project to UnrealGoldRemake.
After the rename, a retained client session initially produced an unknown-session
message; the native client reinitialized successfully. Subsequent native queries
returned `projectName: UnrealGoldRemake`, Entry, and Play mode off. No extra client configuration, proxy, asset
generation service, or external software was installed.

## Console automation focus guard

Prefer direct editor APIs. When a Python console command is necessary, identify
its field in a fresh Slate snapshot, confirm it is empty, then submit the complete
command in one `Type` call with submission enabled. Never clear the field with
separate global Select All/Backspace/Delete calls. Focus can move to the viewport
between calls; a Backspace deleted a derived effect actor during the water pass.
Preflight caught it and the exact checked render actor was restored. If the
identified console contains text, inspect that state rather than sending a
clearing shortcut. Check the execution report/log before issuing dependent work.
