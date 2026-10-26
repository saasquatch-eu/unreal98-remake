#!/bin/bash
# Build the native Mac editor target with the baseline engine installation.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
engine_root="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
project_file="$repo_root/ue5/UnrealRemaster/UnrealRemaster.uproject"

bash "$repo_root/scripts/validate-macos.sh"
if [[ ! -f "$project_file" ]]; then
    printf 'Project descriptor is missing: %s\n' "$project_file" >&2
    exit 1
fi

mkdir -p "$repo_root/.local/logs"
/bin/bash "$engine_root/Engine/Build/BatchFiles/Mac/Build.sh" \
    UnrealRemasterEditor Mac Development \
    "-Project=$project_file" -architecture=arm64 -WaitMutex -NoHotReloadFromIDE \
    "$@" 2>&1 | tee "$repo_root/.local/logs/ue5-build.log"
