# Project guidance

## Scope and intent

- UR-002's native C++ foundation is complete. The current assignment is to prepare
  the castle intro as the first content target: the original map is `Unreal.unr`.
  Keep Vortex Rikers (`Vortex2.unr`) for the later gameplay milestone.
- Preserve source actor order and raw values, including repeated names and
  malformed export tokens. Actor names alone are not unique identifiers.
- Preserve original resource stems, case, package names, and groups. New UE5 asset
  names receive the lowercase `_ue5` suffix before their extension, such as
  `Unreal_ue5.umap`. Follow `docs/resource-naming.md` for paths and exceptions.
- The source-inspection checkpoint now includes a T3D parser, synthetic tests,
  and a private intro report. It does not evaluate CSG, apply class defaults,
  import assets, or implement gameplay. Empty content directories are not
  working UE5 assets. Follow docs/milestones/005-unreal-intro-inspection.md
  for the initial geometry and camera questions. The next source-coordinate
  checkpoint is documented in docs/milestones/006-brush-validation.md: binary
  evidence resolves four pivot components, and zero-shear transforms plus an
  axis-aligned synthetic CSG reference are tested. The subsequent extraction
  (docs/milestones/007-evaluated-geometry.md) reads the original compiled BSP
  through the Level.Model reference. It does not rebuild the brush sequence.
- Compiled world points are already in source world coordinates; do not apply
  brush transforms to them again. Preserve raw surface/node flags, texture
  paths, source boundaries, sky roles, and separate Movers. An OBJ or offline
  preview does not establish UE5 import, normalized UVs, collision, or playback.
- The private UE5 import checkpoint is documented in
  docs/milestones/008-ue5-intro-import.md. Direct Geometry Script buffers preserve
  identity axes and reverse source triangle winding for UE5. Mandatory diagnostic
  UV0 prevents StaticMesh lightmap assertions; it is not original texture UVs.
  Preserve exact triangle counts and validate saved triangle positions/winding,
  actor transforms and the NoCollision profile after reload. Never silently
  overwrite existing assets or loosen count checks. The following material checkpoint
  (docs/milestones/009-original-materials.md) adds 25 original P8 images, normalized
  UV0 and material IDs with full saved readback. Manual -13 EV inspection exposure
  fixes the washout. Procedural fire/water are explicitly transparent placeholders,
  with geometry and UVs preserved. Missing source assignments remain neutral.
  Original sky, effects, collision and flyby playback are still unresolved.
  The modern lighting checkpoint (docs/milestones/010-lumen-lighting.md) replaces
  inspection lighting with software Lumen, Nanite/VSM, clouds/fog and source-position
  lights. Preserve the hidden canonical world reference and exact 7,135-triangle
  union across 44 Nanite and 16 raster chunks, plus 116 Mover triangles. Keep
  transparent effects separate and non-shadowing. Nanite fallback target must be
  Percent Triangles at 100%, with exact Source Model and fallback count checks.
  Manual exposure is now -6 EV; use the lighting verifier for the updated stage.
  Point-light intensity/color calibration is artistic, not a UE1 lightmap match.
  Hardware ray tracing and MegaLights are not enabled or validated.
- Use numeric evidence only when both source and original-package hashes match
  recorded export provenance. Never globally relax the numeric parser or
  rewrite source exports. The binary reader is deliberately limited to v61,
  licensee zero, flags zero, and selected objects without state frames/arrays.
  Texture tooling alone opts into the AllowDownload package flag and small
  static property-array indices. Keep the map reader strict by default.
- Preserve Unreal (1998) gameplay and geometry; modernize visuals incrementally.
- Work in small issues with explicit acceptance criteria. Inspect existing files
  before editing. Do not generate an entire game or introduce speculative systems.
- Use branches and reviewable changes. Do not publish, push, or create remote
  repositories unless the user requests it.

## Environment

- macOS and native Apple Silicon are the primary development environment.
- Python tooling requires Python 3.12+ in a repository-local `.venv`.
- Use `PYTHON_BIN`, `DEVELOPER_DIR`, and `UE_ROOT` overrides rather than hardcoding
  a developer's paths in implementation files.
- The user handles application installation, updates, and removal manually.
  Do not request macOS app-management permission or modify application bundles.
  The UCC compiler probe was stopped after that permission prompt; this
  validation workflow uses read-only package analysis and Python tests.
  Project-local dependencies belong in `.venv`. Inform the user immediately
  if another tool becomes necessary.
- The user wants to know which tools are used. Work with the existing Python,
  bundled Unreal UCC, Git/GitHub, and UE5 tooling; inform the user before using an
  additional program. No extra software is needed for folder preparation.
- Keep engine binaries, caches, build outputs, private exports, and secrets out of
  Git. The engine baseline is recorded in `engine-version.json`.

## Checks and reporting

- The UE5 editor connection uses the installed Unreal MCP skill and the bundled
  `ModelContextProtocol` and `AllToolsets` plugins, enabled for Editor targets.
  Follow `docs/ue5-editor-connection.md`; reuse the installed Codex plugin's
  localhost connection rather than adding a duplicate client configuration.
- Before live edits, verify the connected project is UnrealGoldRemake and save
  affected work. Discover current tool schemas, serialize dependent mutations,
  and verify returned results. Connection setup itself does not authorize asset
  conversion or gameplay work.

- Run `bash scripts/run-tests.sh` for Python changes, and `bash -n` on changed
  shell scripts. Run the environment validator when changing setup tooling.
- Future C++ changes require an actual engine build when available. Report exact
  failures or unavailable checks; never claim compilation or tests without running
  them. Editor launch and gameplay feel require separate verification.
- Smoke tests establish packaging only; they do not establish conversion fidelity.
- Add meaningful tests with actual future behavior rather than placeholder
  conversion implementations or tests that merely repeat constants.

## Content and rights

- Do not download or commit original Unreal assets or Epic-owned source.
- Use synthetic fixtures; place private installations/exports under ignored
  `reference/local/` or `data/local/` paths.
- Record provenance before adding third-party assets. A free release and a public
  code license remain future decisions with rights verification outstanding.
- Do not copy Unreal Engine source or redistribute engine binaries in this repo.
