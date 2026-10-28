# Continue the UnrealGoldRemake project

This is the shared handoff for people and coding models. Read this page first,
then `AGENTS.md` for working rules and the linked milestone for the area you
will change. Milestone reports record what was proved **at that checkpoint**;
older reports are historical and may say that later work was still pending.
Check Git and the live editor before treating any status below as current.

## Where the project lives

- Git repository: `https://github.com/saasquatch-eu/unreal98-remake`.
- UE project: `ue5/UnrealGoldRemake/UnrealGoldRemake.uproject` (UE 5.8.4 on the
  development Mac). The editor starts in Entry; open the private castle map
  `/Game/Unreal/Maps/Unreal_ue5` separately.
- First content target: original `Unreal.unr` castle intro. `Vortex2.unr` is a
  later gameplay target.
- Tracked implementation: `tools/src/ue1_converter/` (readers/preparation),
  `tools/editor/` (editor application/verification), `tools/tests/`, `scripts/`,
  `ue5/` (project configuration/C++ foundation), and `docs/milestones/`.
- Private inputs: the owner's installed Unreal Gold under
  `~/Library/Application Support/Unreal/`; original exports under
  `data/local/Unreal/`. Prepared game-derived data is under
  `data/converted/Unreal/`; generated UE assets are under
  `ue5/UnrealGoldRemake/Content/Unreal/`. These are Git-ignored and **are not
  available from a fresh clone**. See `docs/asset-pipeline.md` and
  `docs/resource-naming.md`.

## Current checkpoint (2026-10-28, merged PR #18)

The private castle preview contains the evaluated original world, original
texture assignments, software Lumen lighting, Nanite render chunks, VSM,
animated fire and water previews, gloomy atmosphere, source-image sky, moons,
source-position lightning, a looping source-path camera, Flyby music and ten
ambient emitters. The moat is visible from above; the entrance floor renders.
The sequence starts in **Play** and loops independently from the music.

The latest full report is `docs/milestones/017-intro-camera-audio.md`. Earlier
stage details are in milestones 008–016. The latest completed checks recorded
there were 268 Python tests, saved-scene readback, Play camera/audio checks and
source/derived hash checks. Their private result logs and screenshots live
under ignored `.local/`; they may not exist in another checkout. The counts to
preserve are **7,135 world + 116 Mover + 82 sky + 672 moon triangles**.
The current sequence is a reconstruction, not a captured frame-by-frame match
to Unreal Gold. No collision or complete original intro runtime is claimed.

A separate private **Nali visual model prototype** was generated after PR #17.
It has four visible arms but is unrigged, very dense and not imported into UE5.
See `docs/milestones/018-nali-model-prototype.md` before character work.
The follow-on source-motion checkpoint in `docs/milestones/019-nali-source-walk.md`
identifies `UnrealShare.Nali1` as the castle Nali mesh and prepares its 20-frame
`Walk` reference privately. It does not supply a four-arm rig or UE5 animation.

## What remains

- Compare captured original intro frames and audio against the UE5 playback;
  refine camera motion, initial timing, eye height, framing and sky/mood.
- Rework lightning so flashes affect the wider scene convincingly while
  keeping the dark baseline. The current 18 source-position lights and 11 sky
  pulses are an approximation; no original bolt or thunder was found in the
  inspected lightning class.
- Restore Nali, birds, animated decorations/flags, triggered Movers and their
  sounds, original title/menu/HUD, collision and gameplay behavior. These are
  **not** present in the current intro preview.
- The castle source contains `Nali0` with `Orders=Patroling` (source spelling),
  `OrderTag=P1`, and four `PatrolPoint` records around the walls. Verify full
  links and behavior from source before implementing a route. The Meshy Nali
  prototype remains private and unrigged; its four arms need a custom rig and
  animation plan. Use `Nali1` source `Walk` poses, not playable `Nali2` poses,
  as the initial motion reference.

Choose one bounded next milestone and record exact acceptance criteria before
editing. Do not infer that a discussion of an idea authorized paid asset
generation or a new external service.

## How to start a session

1. Read `AGENTS.md`, this page, the relevant latest milestone and `git status`.
   Fetch `main` and inspect open work before branching. Other models may be
   editing the same checkout; use an isolated worktree/branch and never discard
   their uncommitted files. The owner reviews and merges pull requests.
2. Confirm which original installations and private generated files exist.
   A fresh clone has code and docs only. Do not report a successful UE scene
   check when only the tracked project files are present.
3. For Python changes run `bash scripts/run-tests.sh`. For live UE changes,
   read `docs/ue5-editor-connection.md`, verify the connected project and
   loaded map, save affected work, use the applicable `tools/editor/verify_*`
   script, and inspect actual Play behavior when runtime behavior matters.
4. Keep source hashes, actor order, source flags, coordinates, material/UV
   assignments and strict geometry checks. Record every presentation change
   separately from original-source evidence. New UE5 asset names end `_ue5`.
5. Update this page and the new milestone report with what changed, exact
   verification performed, remaining limits and recovery steps. Keep original
   game data, imports, recordings, captures and secrets out of Git.

## Editor and tool boundaries

Use the existing UE installation, Python environment and localhost editor
connection described in `docs/ue5-editor-connection.md`. The owner handles app
installation, updates and removal; never modify `/Applications` bundles or
request macOS app-management permission. Inform the owner before using a new
program or external generation provider. Meshy is optional character-production
help, not a dependency of the current scene. If an editor MCP tool is absent in
the current chat, report that state and use the documented connection recovery;
do not claim a live editor verification from repository inspection alone.

The saved map and original audio are private. `tools/editor/apply_*` scripts are
stage-specific and many refuse existing destinations. Read their matching
milestone before running them, back up affected assets, and inspect partial
state after a failure. For console automation, identify an empty field from a
fresh Slate snapshot and submit a complete command in one Type call; check its
result log before dependent actions. See the focus incident in
`docs/ue5-editor-connection.md`.
