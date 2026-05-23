#!/usr/bin/env bash
set -euo pipefail

cd /mnt/c/mavi_project

if [ ! -d .buildozer-venv ]; then
  python3 -m venv .buildozer-venv
fi

source .buildozer-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install buildozer cython
buildozer android debug
