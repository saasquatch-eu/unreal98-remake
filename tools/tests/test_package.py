"""Check installation independently of the repository's working directory."""

import os
import subprocess
import sys


def test_installed_package_imports_outside_repository(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import ue1_converter"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
