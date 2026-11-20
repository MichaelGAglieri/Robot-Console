#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Robot Console desktop app (Qt / PySide6) for macOS, Linux and Windows.

    python robot_console.py                 # normal start
    python robot_console.py --no-hardware   # preview only, the USB port is never opened
    python robot_console.py --data FOLDER   # separate data folder (projects, sequence, memory)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if sys.version_info < (3, 10):
    sys.exit('Robot Console richiede Python 3.10 o successivo.')
try:
    import PySide6  # noqa: F401
except ImportError:
    sys.exit('PySide6 non è installato. Esegui: python -m pip install -r requirements.txt')

from qtui.app import main

if __name__ == '__main__':
    sys.exit(main())
