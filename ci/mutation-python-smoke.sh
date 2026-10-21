#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import sys

from angr import claripy
from cosmic_ray.mutating import mutate_and_test
from coverage import Coverage
import pytest

print(f"Unified Python: {sys.executable}")
PY
cosmic-ray --version
ruff --version
