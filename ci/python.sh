#!/usr/bin/env bash
set -euo pipefail
ci_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ -n "${IFRL_NIX_SHELL:-}" && "${IFRL_IN_SHELL:-}" != 1 ]]; then
  export IFRL_IN_SHELL=1
  exec nix develop "$IFRL_NIX_SHELL" --no-write-lock-file --command bash "$0" "$@"
fi
ci_venv="${RUNNER_TEMP:-/tmp}/ifrl-python"
if [[ ! -x "$ci_venv/bin/python" ]]; then
  python3 -m venv --system-site-packages "$ci_venv"
  "$ci_venv/bin/python" -m pip install -r "$ci_root/requirements.txt"
  if [[ -f .ci/python-requirements.txt ]]; then
    "$ci_venv/bin/python" -m pip install -r .ci/python-requirements.txt
  fi
fi
export PATH="$ci_venv/bin:$PATH"
exec "$ci_venv/bin/python" "$ci_root/python.py" "$@"
