# Project guidance

## Scope and intent

- The current assignment is **UR-002**: create and validate the minimal native
  UE5 C++ project. Conversion, importer, and gameplay work need a separate request.
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
- Ask before installing/updating system software or changing system configuration.
  Project-local dependencies belong in `.venv`.
- Keep engine binaries, caches, build outputs, private exports, and secrets out of
  Git. The engine baseline is recorded in `engine-version.json`.

## Checks and reporting

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
