#!/bin/bash
# Install development dependencies in .venv only; never install system software.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-python3}"

if ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python not found: %s. Set PYTHON_BIN to an existing Python 3.12+ executable.\n' "$python_bin" >&2
    exit 1
fi
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Python 3.12+ is required; set PYTHON_BIN. No system changes were made.")'

if [[ ! -e "$repo_root/.venv" ]]; then
    "$python_bin" -m venv "$repo_root/.venv"
fi
venv_python="$repo_root/.venv/bin/python"
if [[ ! -x "$venv_python" ]]; then
    printf '.venv exists but has no executable Python. Inspect it before recreating it.\n' >&2
    exit 1
fi
"$venv_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Existing .venv needs Python 3.12+; recreate it deliberately.")'
"$venv_python" -m pip install --disable-pip-version-check --no-cache-dir -e "$repo_root[dev]"
printf '\nLocal Python setup complete. Run: bash scripts/run-tests.sh\n'
