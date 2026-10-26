# Unreal Engine workspace

`UnrealRemaster/UnrealRemaster.uproject` is the minimal C++ project for UE **5.8.4**
(see `../engine-version.json`). Its editor target builds for native Mac arm64.

From the repository root, run `bash scripts/build-ue5.sh` and then
`bash scripts/open-ue5.sh`. Subsequent launches can use the `.uproject` directly.
The empty engine Entry map is the startup map. The runtime module logs its load;
it does not implement gameplay. There are no converted original game assets.

The unused Android File Server plugin is disabled for this Mac foundation. Native
build outputs, editor state, and caches remain ignored. The engine installation
stays outside this repository; the Entry map is referenced rather than copied.

See `../docs/milestones/002-native-cpp-project.md` for verification evidence.

## First content target: Unreal castle intro

`Content/Unreal/` has prepared folders for Maps, Meshes, Textures, Materials,
Sounds, Music, Cinematics, and Blueprints. They contain placeholders only.
The planned intro level is `/Game/Unreal/Maps/Unreal_ue5`, based on the original
`Unreal.unr`. The planned camera sequence is
`/Game/Unreal/Cinematics/Unreal_ue5`. Neither asset has been created yet.

Use source package/group names below each resource category, preserve case, and
append `_ue5` to each new UE5 asset name. See `../docs/resource-naming.md`.
Original-game-derived content under this root is ignored by Git; only directory
placeholders are tracked. The startup map remains Entry until a real imported
level is created and validated.
