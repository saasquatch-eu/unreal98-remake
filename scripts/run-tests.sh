#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Test Python not found. Run scripts/setup-macos.sh first.\n' >&2
    exit 1
fi
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python 3.12+ is required.")'
cd "$repo_root"
exec "$python_bin" -m pytest "$@"
