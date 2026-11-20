# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Robot Console cross-platform desktop interface (PySide6 / Qt 6).

The window talks to the same controller process as the macOS Swift app
(native/native_bridge.py): one JSON request per line, one JSON state reply per line.
"""
__version__ = '2.1.0'
