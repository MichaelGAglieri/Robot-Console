#!/bin/zsh
# SPDX-License-Identifier: GPL-3.0-only
set -e
cd "$(dirname "$0")/.."
python3 scripts/install_local.py --apply
