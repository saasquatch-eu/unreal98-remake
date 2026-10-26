#!/bin/bash
# Read-only preflight. Exit 1 for missing required dependencies, 0 otherwise.
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0
fail() { printf 'FAIL: %s\n' "$*"; failures=$((failures + 1)); }
warn() { printf 'WARN: %s\n' "$*"; }
pass() { printf 'PASS: %s\n' "$*"; }

if [[ "$(uname -s)" != Darwin ]]; then
    fail 'This preflight requires macOS.'
    exit 1
fi
pass "macOS $(sw_vers -productVersion); architecture $(uname -m)"
if [[ "$(uname -m)" != arm64 ]]; then
    fail 'Run a native arm64 shell on the primary Apple Silicon development machine.'
fi

selected_developer_dir="$(xcode-select -p 2>/dev/null || true)"
if [[ -z "${DEVELOPER_DIR:-}" ]]; then
    if [[ "$selected_developer_dir" == */Xcode*.app/Contents/Developer ]]; then
        export DEVELOPER_DIR="$selected_developer_dir"
    elif [[ -d /Applications/Xcode.app/Contents/Developer ]]; then
        export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
        fail "System selection is $selected_developer_dir; Finder/Launcher starts need full Xcode selected. Using $DEVELOPER_DIR for diagnostics only."
    fi
fi
if xcode_info="$(xcodebuild -version 2>/dev/null)"; then
    pass "$xcode_info"
    if ! xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1; then
        fail 'Xcode first-launch setup is incomplete; open Xcode and complete its prompts manually.'
    fi
    if sdk_version="$(xcrun --sdk macosx --show-sdk-version 2>/dev/null)"; then
        pass "macOS SDK $sdk_version"
    else
        fail 'macOS SDK is unavailable.'
    fi
    if xcrun clang --version >/dev/null 2>&1; then
        pass 'Clang responds to its version command (not a compilation test).'
    else
        fail 'Clang cannot run; inspect Xcode components.'
    fi
    if metal_info="$(xcrun metal --version 2>&1)"; then
        pass 'Metal compiler responds to its version command (not a shader compilation test).'
    else
        fail "Metal compiler cannot run: $metal_info"
    fi
else
    fail 'Full Xcode is unavailable. Set DEVELOPER_DIR to its Contents/Developer directory.'
fi

if command -v git >/dev/null 2>&1; then
    pass "$(git --version)"
else
    fail 'Git is unavailable.'
fi
if git lfs version >/dev/null 2>&1; then
    pass "$(git lfs version)"
else
    warn 'Git LFS is not installed; defer until permitted binary assets are introduced.'
fi

if [[ -n "${PYTHON_BIN:-}" ]]; then
    python_bin="$PYTHON_BIN"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
    python_bin="$repo_root/.venv/bin/python"
else
    python_bin=python3
fi
if command -v "$python_bin" >/dev/null 2>&1; then
    if "$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
        pass "$("$python_bin" --version) at $python_bin"
        if "$python_bin" -m pytest --version; then
            pass 'pytest is available.'
        else
            fail 'pytest is missing; run scripts/setup-macos.sh with Python 3.12+.'
        fi
        if "$python_bin" -I -c 'import ue1_converter'; then
            pass 'The scaffold package is installed.'
        else
            fail 'The scaffold package is missing; run scripts/setup-macos.sh.'
        fi
    else
        fail "Python 3.12+ is required; found $("$python_bin" --version 2>&1)."
    fi
else
    fail "Python not found: $python_bin"
fi

engine_root="${UE_ROOT:-/Users/Shared/Epic Games/UE_5.8}"
build_version="$engine_root/Engine/Build/Build.version"
editor_binary="$engine_root/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
if [[ -r "$build_version" ]] && command -v "$python_bin" >/dev/null 2>&1; then
    if "$python_bin" - "$repo_root/engine-version.json" "$build_version" <<'PY'
import json
import sys

with open(sys.argv[1]) as source:
    expected = json.load(source)
with open(sys.argv[2]) as source:
    installed = json.load(source)
actual = tuple(installed[key] for key in ("MajorVersion", "MinorVersion", "PatchVersion"))
baseline = tuple(expected[key] for key in ("major", "minor", "patch"))
print("UE installed: %s; baseline: %s" % (".".join(map(str, actual)), ".".join(map(str, baseline))))
sys.exit(0 if actual == baseline else 1)
PY
    then
        pass "Engine version matches at $engine_root"
    else
        fail 'Engine version does not match the baseline, or metadata could not be read.'
    fi
else
    fail "Cannot inspect engine metadata at $build_version; set UE_ROOT if needed."
fi
if [[ -x "$editor_binary" ]] && /usr/bin/lipo -verify_arch arm64 "$editor_binary" >/dev/null 2>&1; then
    pass 'Installed Unreal Editor has an arm64 executable.'
else
    fail 'Native arm64 Unreal Editor is missing.'
fi
if [[ -f "$engine_root/Engine/Build/BatchFiles/Mac/Build.sh" ]]; then
    pass 'Unreal Build Tool entry script exists.'
else
    fail 'Unreal build entry script is missing.'
fi
warn 'No UE project exists yet. C++ compilation, editor launch, and rendering remain unverified.'
df -h "$repo_root"
printf '\nRequired preflight failures: %s\n' "$failures"
[[ "$failures" -eq 0 ]]
