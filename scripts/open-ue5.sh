#!/bin/bash
# Open the built C++ project. Additional arguments are passed to Unreal Editor.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
engine_root="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
project_file="$repo_root/ue5/UnrealRemaster/UnrealRemaster.uproject"
editor_binary="$engine_root/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
module_binary="$repo_root/ue5/UnrealRemaster/Binaries/Mac/libUnrealEditor-UnrealRemaster.dylib"

if [[ ! -f "$project_file" || ! -f "$module_binary" ]]; then
    printf 'Build the project first: bash scripts/build-ue5.sh\n' >&2
    exit 1
fi
if [[ ! -x "$editor_binary" ]]; then
    printf 'Unreal Editor not found at %s. Set UE_ROOT to the engine installation.\n' "$editor_binary" >&2
    exit 1
fi
exec "$editor_binary" "$project_file" "$@"
