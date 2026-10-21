#!/usr/bin/env bash
set -euo pipefail

env_dir=$(mktemp -d)
trap 'rm -rf "$env_dir"' EXIT
python3 -m venv --system-site-packages "$env_dir"
"$env_dir/bin/python" -c 'from cosmic_ray.mutating import mutate_and_test'
