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

if len(sys.argv) > 1 and sys.argv[1] == '--controller':
    # Packaged app: the same executable also runs the controller process
    # (the window starts it with --controller; stdin EOF = STOP and exit).
    sys.argv = [sys.argv[0]]
    import io
    # A windowed executable (Windows) may start without Python text streams even
    # though the parent passed pipes: rebuild them from the inherited descriptors.
    for name, fd, mode in (('stdin', 0, 'r'), ('stdout', 1, 'w'), ('stderr', 2, 'w')):
        if getattr(sys, name) is None:
            try:
                setattr(sys, name, io.TextIOWrapper(io.FileIO(fd, mode, closefd=False), encoding='utf-8', line_buffering=mode == 'w'))
            except OSError:
                pass
    sys.path.insert(0, str(ROOT / 'native'))
    import native_bridge  # noqa: F401  (runs the controller loop)
    sys.exit(0)

if sys.version_info < (3, 10):
    sys.exit('Robot Console richiede Python 3.10 o successivo.')
try:
    import PySide6  # noqa: F401
except ImportError:
    sys.exit('PySide6 non è installato. Esegui: python -m pip install -r requirements.txt')

from qtui.app import main

if __name__ == '__main__':
    sys.exit(main())
