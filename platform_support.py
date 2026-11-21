# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Operating-system differences in one place: data folder, single instance, external tools.

macOS, Linux and Windows. Standard library only. Nothing here opens the serial port,
starts a tool or contacts the network.
"""
import os, shutil, signal, subprocess, sys
from pathlib import Path

WINDOWS = os.name == 'nt'
MACOS = sys.platform == 'darwin'
LINUX = sys.platform.startswith('linux')
APP_FOLDER = 'DOC Regia'  # historical name, kept so every version shares the same data


def system_name():
    return 'windows' if WINDOWS else 'macos' if MACOS else 'linux'


def data_folder():
    """Per-user data folder. DOC_REGIA_DATA overrides it (tests, portable installs)."""
    if os.environ.get('DOC_REGIA_DATA'):
        return Path(os.environ['DOC_REGIA_DATA'])
    if MACOS:
        return Path.home() / 'Library/Application Support' / APP_FOLDER
    if WINDOWS:
        return Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / APP_FOLDER
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'doc-regia'


class InstanceLock:
    """One controller per user: a second copy must never talk to the same robot."""

    def __init__(self, folder):
        self.path = Path(folder) / 'controller.lock'
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, 'a+')
        try:
            if WINDOWS:
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self):
        if self.handle:
            try:
                if WINDOWS:
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            self.handle.close()
            self.handle = None


def _executable(path):
    path = Path(path)
    return path.is_file() and (WINDOWS or os.access(path, os.X_OK))


def find_executable(name, extra=()):
    """First runnable candidate: PATH, then well-known per-system locations."""
    candidates = []
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    candidates += [Path(p) for p in extra]
    return next((str(p) for p in candidates if _executable(p)), '')


def _program_files():
    roots = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA')]
    return [Path(r) for r in roots if r]


def arduino_cli_candidates(bundled_dir):
    exe = 'arduino-cli.exe' if WINDOWS else 'arduino-cli'
    found = [Path(bundled_dir) / 'Tools' / exe]
    if MACOS:
        found += [Path('/opt/homebrew/bin/arduino-cli'), Path('/usr/local/bin/arduino-cli'),
                  Path('/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli'),
                  Path.home() / 'Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli']
    elif WINDOWS:
        for root in _program_files():
            found += [root / 'Arduino CLI/arduino-cli.exe', root / 'Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe',
                      root / 'Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe']
    else:
        found += [Path('/usr/local/bin/arduino-cli'), Path('/usr/bin/arduino-cli'), Path.home() / 'bin/arduino-cli',
                  Path.home() / '.local/bin/arduino-cli', Path('/snap/bin/arduino-cli'),
                  Path('/opt/arduino-ide/resources/app/lib/backend/resources/arduino-cli')]
    return found


def find_arduino_cli(bundled_dir):
    return find_executable('arduino-cli', arduino_cli_candidates(bundled_dir))


def find_ollama():
    if MACOS:
        extra = [Path('/Applications/Ollama.app/Contents/Resources/ollama'), Path.home() / 'Applications/Ollama.app/Contents/Resources/ollama',
                 Path('/opt/homebrew/bin/ollama'), Path('/usr/local/bin/ollama')]
    elif WINDOWS:
        extra = [root / 'Programs/Ollama/ollama.exe' for root in _program_files()]
    else:
        extra = [Path('/usr/local/bin/ollama'), Path('/usr/bin/ollama'), Path('/snap/bin/ollama')]
    return find_executable('ollama', extra)


def find_pixi():
    extra = [Path.home() / '.pixi/bin' / ('pixi.exe' if WINDOWS else 'pixi')]
    if MACOS:
        extra.insert(0, Path('/opt/homebrew/bin/pixi'))
    return find_executable('pixi', extra)


def find_webots():
    if MACOS:
        extra = [Path('/Applications/Webots.app/Contents/MacOS/webots')]
    elif WINDOWS:
        extra = [root / 'Webots/msys64/mingw64/bin/webotsw.exe' for root in _program_files()]
    else:
        extra = [Path('/usr/local/bin/webots'), Path('/usr/bin/webots'), Path('/snap/bin/webots'), Path('/usr/local/webots/webots')]
    return find_executable('webots', extra)


def pixi_env_binary(project, name):
    """Executable inside the project's default Pixi environment."""
    env = Path(project) / '.pixi/envs/default'
    if WINDOWS:
        for folder in (env, env / 'Scripts', env / 'Library/bin'):
            for suffix in ('.exe', '.bat', '.cmd', ''):
                if (folder / (name + suffix)).is_file():
                    return folder / (name + suffix)
        return env / (name + '.exe')
    return env / 'bin' / name


def interrupt(process):
    """Polite stop that lets rosbag and similar tools finish their files."""
    if WINDOWS:
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        except (OSError, ValueError, AttributeError):
            process.terminate()
    else:
        process.send_signal(signal.SIGINT)


def new_process_group():
    """Popen keyword arguments so interrupt() reaches only the started tool."""
    return dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if WINDOWS else {}


def open_folder(path):
    """Show a folder in the system file manager (explicit user action only)."""
    path = str(path)
    if WINDOWS:
        os.startfile(path)  # noqa: S606 - user-requested
    elif MACOS:
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])
