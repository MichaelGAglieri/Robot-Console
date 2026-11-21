#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Build the desktop package for the current system.

    python scripts/build_desktop.py            # macOS: SwiftUI app .dmg · Linux: Qt .deb · Windows: Qt setup .exe (+ .zip)
    python scripts/build_desktop.py --check    # also start the packaged controller and check one reply
    python scripts/build_desktop.py --qt       # macOS only: package the Qt app instead (for testing it on a Mac)

macOS: the main app is the SwiftUI one (native/), built with native/build.command
(Command Line Tools); it runs the controller with the Python 3 already on the Mac.
Linux/Windows: the Qt app, built with PyInstaller (requirements.txt + PyInstaller);
Python and Qt are bundled. Output goes to dist/.

The macOS app is ad-hoc signed only (no paid Apple Developer ID): on first start use
right click → Open, or System Settings → Privacy & Security → Open Anyway.
"""
import argparse, json, os, platform, plistlib, shutil, subprocess, sys, tempfile, textwrap, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qtui import __version__ as VERSION  # noqa: E402

NAME = 'Robot Console'
SLUG = 'robot-console'
BUNDLE_ID = 'io.github.michaelgaglieri.robotconsole'
DIST, BUILD = ROOT / 'dist', ROOT / 'build' / 'pyinstaller'
# Backend modules also shipped as source: the ROS observer runs them with the ROS Python.
OBSERVER_SOURCES = ['robot_model.py', 'native/ros_observer.py']
DATA = ['models', 'RegiaDemo', 'docs', 'examples', 'native/Localization/English.json', 'qtui/viewport.qml', 'qtui/icons',
        'LICENSE', 'THIRD_PARTY.md', 'AUTHORS.md']
QT_EXCLUDES = ['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.QtPdf',
               'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs', 'PySide6.QtSql', 'PySide6.QtTest',
               'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
               'PySide6.QtLocation', 'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
               'tkinter', 'matplotlib', 'IPython']


def run(*args, **kw):
    print('+', ' '.join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True, **kw)


def pyinstaller():
    sep = os.pathsep
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--python-option', 'X utf8', '--name', NAME,
            '--distpath', DIST, '--workpath', BUILD, '--specpath', BUILD,
            '--paths', ROOT, '--paths', ROOT / 'native',
            '--hidden-import', 'native_bridge', '--hidden-import', 'serial',
            '--collect-submodules', 'qtui']
    icon = ROOT / ('native/DOCRegia.icns' if sys.platform == 'darwin' else 'qtui/icons/app.ico' if os.name == 'nt' else 'qtui/icons/app.png')
    if icon.exists():
        args += ['--icon', icon]
    if sys.platform == 'darwin':
        args += ['--osx-bundle-identifier', BUNDLE_ID]
    for item in DATA:
        path = ROOT / item
        if path.exists():
            target = item if path.is_dir() else (str(Path(item).parent) if Path(item).parent != Path('.') else '.')
            args += ['--add-data', '%s%s%s' % (path, sep, target)]
    for item in OBSERVER_SOURCES:
        args += ['--add-data', '%s%s.' % (ROOT / item, sep)]
    for module in QT_EXCLUDES:
        args += ['--exclude-module', module]
    args.append(ROOT / 'robot_console.py')
    run(*args)


def windows_icon():
    """PyInstaller wants .ico on Windows; build it from the PNG with Qt."""
    target = ROOT / 'qtui/icons/app.ico'
    if os.name != 'nt' or target.exists():
        return
    from PySide6.QtGui import QImage
    image = QImage(str(ROOT / 'qtui/icons/app.png')).scaled(256, 256)
    image.save(str(target), 'ICO')


def check(command, label='Packaged controller'):
    """Start the packaged controller, send one heartbeat, expect a state reply."""
    with tempfile.TemporaryDirectory() as data:
        env = dict(os.environ, DOC_REGIA_DATA=data, DOC_REGIA_NO_HARDWARE='1')
        process = subprocess.run([str(c) for c in command], input='{"op":"heartbeat"}\n', capture_output=True,
                                 text=True, encoding='utf-8', env=env, timeout=120)
    lines = [l for l in process.stdout.splitlines() if l.strip()]
    reply = json.loads(lines[0]) if lines else {}
    if 'state' not in reply or reply.get('error'):
        raise SystemExit(label + ' check failed:\n' + process.stdout[-2000:] + process.stderr[-2000:])
    print('%s OK: mode %s, model %s' % (label, reply['state'].get('mode'), (reply.get('studio') or {}).get('name')))


def make_dmg(app, dmg, note):
    """Drag-to-Applications disk image with a short bilingual note."""
    staging = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(app, staging / app.name, symlinks=True)
        (staging / 'Applications').symlink_to('/Applications')
        (staging / 'LEGGIMI - READ ME.txt').write_text(note, encoding='utf-8')
        if dmg.exists():
            dmg.unlink()
        run('hdiutil', 'create', '-volname', NAME, '-srcfolder', staging, '-fs', 'HFS+', '-format', 'UDZO', '-ov', dmg)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


SIGNATURE_NOTE = """\
L'app ha una firma ad-hoc, non una firma Apple Developer ID: al primo avvio clic destro
sull'app > Apri (oppure Impostazioni di Sistema > Privacy e sicurezza > Apri comunque).

The app is ad-hoc signed, not signed with an Apple Developer ID: on first start right click
the app > Open (or System Settings > Privacy & Security > Open Anyway).
"""


def macos_swift():
    """The main macOS app: SwiftUI interface + the Python controller run by the Mac's Python 3."""
    run('zsh', ROOT / 'native/build.command')
    built = ROOT / (NAME + '.app')
    with open(built / 'Contents/Info.plist', 'rb') as f:
        plist = plistlib.load(f)
    if plist['CFBundleShortVersionString'] != VERSION:
        raise SystemExit('native/Info.plist is %s, qtui/__init__.py is %s: align the versions' % (plist['CFBundleShortVersionString'], VERSION))
    app = DIST / built.name
    DIST.mkdir(exist_ok=True)
    shutil.copytree(built, app, symlinks=True)
    run('codesign', '--verify', '--deep', '--strict', app)
    dmg = DIST / ('Robot-Console-%s-macOS-AppleSilicon.dmg' % VERSION)
    make_dmg(app, dmg, ('Robot Console %s (macOS 14+, Apple Silicon)\n\n'
                        'Trascina Robot Console in Applicazioni. Serve Python 3.9 o successivo: quello degli\n'
                        'Strumenti da riga di comando (xcode-select --install), di Homebrew o di python.org.\n\n'
                        'Drag Robot Console to Applications. Python 3.9 or newer is required: the one from the\n'
                        'Command Line Tools (xcode-select --install), Homebrew or python.org.\n\n' % VERSION) + SIGNATURE_NOTE)
    resources = app / 'Contents/Resources'
    pythons = [sys.executable] + [p for p in ('/usr/bin/python3',) if Path(p).exists()]  # 3.9 on a plain Mac
    return [dmg], [[python, '-u', resources / 'native_bridge.py'] for python in pythons]


def macos_qt():
    app = DIST / (NAME + '.app')
    info = app / 'Contents/Info.plist'
    with open(info, 'rb') as f:
        plist = plistlib.load(f)
    plist.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION, LSMinimumSystemVersion='12.0',
                 NSHighResolutionCapable=True, NSHumanReadableCopyright='GPL-3.0-only · Michael Giuseppe Aglieri',
                 NSCameraUsageDescription='Video locale della telecamera per osservare il robot; nulla viene inviato in rete.',
                 NSMicrophoneUsageDescription='Dettatura offline dei comandi vocali; l’audio resta su questo computer.')
    with open(info, 'wb') as f:
        plistlib.dump(plist, f)
    # Ad-hoc signature: no Apple Developer ID needed; Gatekeeper asks once.
    run('codesign', '--force', '--deep', '--sign', '-', app)
    run('codesign', '--verify', '--deep', '--strict', app)
    dmg = DIST / ('Robot-Console-%s-Qt-macOS-%s.dmg' % (VERSION, platform.machine()))
    make_dmg(app, dmg, 'Robot Console %s · Qt (test build)\n\nTrascina Robot Console in Applicazioni.\nDrag Robot Console to Applications.\n\n' % VERSION + SIGNATURE_NOTE)
    return [dmg], [[app / 'Contents/MacOS' / NAME, '--controller']]


def linux():
    arch = subprocess.run(['dpkg', '--print-architecture'], capture_output=True, text=True).stdout.strip() or 'amd64'
    root = Path(tempfile.mkdtemp()) / SLUG
    try:
        shutil.copytree(DIST / NAME, root / 'opt' / SLUG, symlinks=True)
        (root / 'usr/bin').mkdir(parents=True)
        launcher = root / 'usr/bin' / SLUG
        launcher.write_text('#!/bin/sh\nexec "/opt/%s/%s" "$@"\n' % (SLUG, NAME))
        launcher.chmod(0o755)
        icons = root / 'usr/share/icons/hicolor/256x256/apps'
        icons.mkdir(parents=True)
        from PySide6.QtGui import QImage
        QImage(str(ROOT / 'qtui/icons/app.png')).scaled(256, 256).save(str(icons / (SLUG + '.png')))
        (root / 'usr/share/applications').mkdir(parents=True)
        (root / 'usr/share/applications' / (SLUG + '.desktop')).write_text(textwrap.dedent('''\
            [Desktop Entry]
            Type=Application
            Name=Robot Console
            Comment=Control console for the DOC 5-DOF robotic arm
            Exec=%s %%U
            Icon=%s
            Terminal=false
            Categories=Development;Engineering;
            ''' % (SLUG, SLUG)))
        (root / 'usr/lib/udev/rules.d').mkdir(parents=True)
        shutil.copy(ROOT / 'packaging/linux/99-robot-console.rules', root / 'usr/lib/udev/rules.d/')
        docs = root / 'usr/share/doc' / SLUG
        docs.mkdir(parents=True)
        shutil.copy(ROOT / 'THIRD_PARTY.md', docs)
        (docs / 'copyright').write_text('Robot Console\nCopyright (c) 2026 Michael Giuseppe Aglieri\nLicense: GPL-3.0-only\n'
                                        'Bundled Qt (PySide6): LGPL-3.0. See /opt/%s/_internal/LICENSE and THIRD_PARTY.md.\n' % SLUG)
        size = sum(f.stat().st_size for f in root.rglob('*') if f.is_file() and not f.is_symlink()) // 1024
        (root / 'DEBIAN').mkdir()
        (root / 'DEBIAN/control').write_text(textwrap.dedent('''\
            Package: %s
            Version: %s
            Section: science
            Priority: optional
            Architecture: %s
            Installed-Size: %d
            Depends: libegl1, libgl1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libdbus-1-3, libxcb-cursor0
            Recommends: speech-dispatcher
            Maintainer: Michael Giuseppe Aglieri <177836445+MichaelGAglieri@users.noreply.github.com>
            Homepage: https://github.com/MichaelGAglieri/Robot-Console
            Description: Control console for the DOC 5-DOF robotic arm
             Teach, preview and replay arm poses (Arduino Mega 2560 + RAMPS),
             3D studio with IK, MoveJ/MoveL and offline programs. Qt desktop app.
            ''' % (SLUG, VERSION, arch, size)))
        (root / 'DEBIAN/postinst').write_text('#!/bin/sh\nset -e\n'
                                               'command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules || true\n'
                                               'command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q || true\n')
        (root / 'DEBIAN/postinst').chmod(0o755)
        deb = DIST / ('%s_%s_%s.deb' % (SLUG, VERSION, arch))
        run('dpkg-deb', '--build', '--root-owner-group', root, deb)
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)
    return [deb], [[DIST / NAME / NAME, '--controller']]


def windows():
    folder = DIST / NAME
    outputs = []
    archive = DIST / ('Robot-Console-%s-Windows-x64.zip' % VERSION)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob('*'):
            z.write(f, Path(NAME) / f.relative_to(folder))
    outputs.append(archive)
    iscc = shutil.which('iscc') or next((str(p) for p in (Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6/ISCC.exe',
                                                          Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Inno Setup 6/ISCC.exe')
                                         if p.exists()), None)
    if iscc:
        script = BUILD / 'robot-console.iss'
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(textwrap.dedent(r'''
            [Setup]
            AppId={{8F1C2B9E-5D3A-4E7B-9A61-2C0D4F8B7E15}
            AppName=Robot Console
            AppVersion=%(version)s
            AppPublisher=Michael Giuseppe Aglieri
            AppPublisherURL=https://github.com/MichaelGAglieri/Robot-Console
            DefaultDirName={autopf}\Robot Console
            DefaultGroupName=Robot Console
            OutputDir=%(dist)s
            OutputBaseFilename=Robot-Console-%(version)s-Windows-x64-setup
            Compression=lzma2
            SolidCompression=yes
            ArchitecturesInstallIn64BitMode=x64compatible
            PrivilegesRequiredOverridesAllowed=dialog
            LicenseFile=%(license)s
            SetupIconFile=%(icon)s
            UninstallDisplayIcon={app}\Robot Console.exe
            WizardStyle=modern

            [Languages]
            Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
            Name: "english"; MessagesFile: "compiler:Default.isl"

            [Tasks]
            Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

            [Files]
            Source: "%(folder)s\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

            [Icons]
            Name: "{group}\Robot Console"; Filename: "{app}\Robot Console.exe"
            Name: "{autodesktop}\Robot Console"; Filename: "{app}\Robot Console.exe"; Tasks: desktopicon

            [Run]
            Filename: "{app}\Robot Console.exe"; Description: "{cm:LaunchProgram,Robot Console}"; Flags: nowait postinstall skipifsilent
            ''' % dict(version=VERSION, dist=DIST, license=ROOT / 'LICENSE', icon=ROOT / 'qtui/icons/app.ico', folder=folder)), encoding='utf-8')
        run(iscc, script)
        outputs.append(DIST / ('Robot-Console-%s-Windows-x64-setup.exe' % VERSION))
    else:
        print('Inno Setup not found: only the .zip was created.')
    return outputs, [[folder / (NAME + '.exe'), '--controller']]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='run the packaged controller once after the build')
    parser.add_argument('--qt', action='store_true', help='macOS: package the Qt app instead of the SwiftUI app')
    options = parser.parse_args()
    for old in (DIST / NAME, DIST / (NAME + '.app')):
        shutil.rmtree(old, ignore_errors=True)
    if sys.platform == 'darwin' and not options.qt:
        outputs, checks = macos_swift()
    else:
        windows_icon()
        pyinstaller()
        if sys.platform == 'darwin':
            outputs, checks = macos_qt()
        elif os.name == 'nt':
            outputs, checks = windows()
        else:
            outputs, checks = linux()
    if options.check:
        for command in checks:
            check(command, 'Packaged controller (%s)' % Path(str(command[0])).name)
    for path in outputs:
        print('Created %s (%.1f MB)' % (path, path.stat().st_size / 1e6))


if __name__ == '__main__':
    main()
