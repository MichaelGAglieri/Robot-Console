# Robot Console

> **Work in progress.** This project is under active development. Hardware, software, interfaces and configuration can change. See the [roadmap](ROADMAP.md).

A desktop application for **macOS, Linux and Windows** to teach, preview and replay arm poses on up to six joint channels. The physical D.O.C. reference robot has five DOF (Arduino Mega 2560 + RAMPS 1.4). It was developed during my D.O.C. robotics project and ships with that project's hardware configuration.

Since 2.1.0 the app is a native **Qt (PySide6)** window on every platform. The original SwiftUI app for macOS stays in `native/` and uses the same controller.

## Features

- Preview mode without hardware and explicit USB connection to the robot.
- Italian / English and light, dark or system appearance, with saved preferences.
- Operator-defined HOME, editable joint limits and independent 1–20°/s joint speeds within the hardware profile limit.
- Simultaneous joint groups, shared manual/group speed controls and estimated speed/duration previews.
- Per-joint STOP with holding torque, confirmed ENABLE control on wired drivers, and an autosaved operator notes sidebar.
- Pose recording, editing, reordering, deletion, temporary exclusion and one-step undo; simultaneous or ordered joint motion between poses.
- 3D view of the DOC arm (Qt Quick 3D): orbit, pan, zoom, preset views, planned path, TCP trail, work frames and targets.
- Cartesian jog and IK preview, MoveJ / MoveL planning, offline programs with loops, conditions, variables and functions; one plan for preview, validation and execution.
- Collision checks against the arm itself, obstacles and the table, with fixed capsules fitted to the EB-15 geometry.
- Per-axis motor steps, microstepping, reducer ratio and direction; editable firmware sources, revisions, compilation and confirmed upload through Arduino CLI.
- ROS 2 visualization topics, ROS health, optional tool launchers, local camera/QR and an authenticated loopback Python API.
- Voice motion commands with spoken readback and explicit one-use confirmation (typed, or dictated offline with Vosk).
- Optional local Ollama chat, conversation journal and a read-only ROS 2 observer.

## The DOC model

The joints, link lengths and the position of every part come from the assembly of the ToolBox Robotics **EB-15** arm and **EBG-30** gripper done for D.O.C. The ToolBox parts are licensed CC BY-NC-ND 4.0, so this repository does **not** contain them or meshes derived from them:

- out of the box you see a **schematic** DOC model (capsules, discs and boxes, GPL);
- to see the **detailed** model, download [EB-15](https://www.thingiverse.com/thing:6488872) and [EBG-30](https://www.thingiverse.com/thing:6460300) from Thingiverse and choose **Studio → Importa pezzi EB-15…** (or run `python eb15_model.py EB-15.zip EBG-30.zip`). The app recognises the original files by SHA-256 and builds the meshes in your own data folder, for personal non-commercial use.

Collision checks use the same capsules with either model. See [models/doc5/NOTICE.md](models/doc5/NOTICE.md).

## Install and run

### Packages (no Python needed)

From [Releases](https://github.com/MichaelGAglieri/Robot-Console/releases):

- **Linux (Ubuntu 22.04+ / Debian 12+, x86-64):** `robot-console_<version>_amd64.deb` → `sudo apt install ./robot-console_*.deb`. It also installs the menu entry and the udev rule for the Mega serial port; then log out and in once.
- **Windows 10/11 (x64):** `Robot-Console-<version>-Windows-x64-setup.exe` (or the portable `.zip`). The installer is not code-signed, so SmartScreen may ask *More info → Run anyway*.
- **macOS (Apple Silicon):** `Robot-Console-<version>-macOS-arm64.dmg` → drag the app to Applications. It is ad-hoc signed, not signed with a paid Apple Developer ID: on first start right click → **Open**, or System Settings → Privacy & Security → **Open Anyway**.

Packages are built by GitHub Actions with `python scripts/build_desktop.py` (PyInstaller); you can run the same script locally.

### From source

Requirements: **Python 3.10+** (3.12 recommended). For firmware compilation/upload install [Arduino CLI](https://arduino.github.io/arduino-cli/) or Arduino IDE; Ollama is optional.

```sh
git clone https://github.com/MichaelGAglieri/Robot-Console.git
cd Robot-Console
./run.sh                # macOS and Linux: creates .venv on first start
```

On Windows double-click **`run.bat`** (or run it from a terminal). Manual setup on any system:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # Windows: .venv\Scripts\python -m pip …
.venv/bin/python robot_console.py
```

Useful options: `--no-hardware` (preview only, the USB port is never opened) and `--data FOLDER` (separate data folder). Optional extras in `requirements-optional.txt`: OpenCV for QR codes, Vosk + sounddevice for offline dictation.

### Platform notes

| | Serial port | Data folder |
| --- | --- | --- |
| macOS | `/dev/cu.usbmodem*`, `cu.usbserial*`, `cu.wchusbserial*` | `~/Library/Application Support/DOC Regia` |
| Linux | `/dev/ttyACM*`, `/dev/ttyUSB*` | `$XDG_DATA_HOME/doc-regia` (default `~/.local/share/doc-regia`) |
| Windows | `COM*` (through pyserial) | `%APPDATA%\DOC Regia` |

- **Linux:** your user needs access to the serial port: `sudo usermod -aG dialout $USER` and log in again, or install [packaging/linux/99-robot-console.rules](packaging/linux/99-robot-console.rules). A desktop launcher template is in `packaging/linux/`. Qt needs the usual system libraries (`libegl1`, `libxkbcommon0`, `libfontconfig1`). Text-to-speech uses speech-dispatcher when installed.
- **Windows:** install the Arduino Mega driver if the board does not appear as a COM port; close the Arduino IDE serial monitor before connecting. The J.A.R.V.I.S. local socket channel is not available on Windows.
- **macOS:** the SwiftUI app can still be built with `zsh native/build.command` (Command Line Tools required); it is ad-hoc signed, not notarized.

Only one controller runs per data folder: close the macOS SwiftUI app before opening the Qt app on the same data, or use `--data`.

## First use

1. Open the app and choose **Anteprima**. Confirm a virtual HOME and apply small limits.
2. Move a virtual joint, choose a gripper state and record a pose. Use **Modifica** to change it and the row switch to exclude/re-enable it.
3. Return to virtual HOME and replay. Only enabled poses perform their pause and gripper action.
4. For physical use follow the [hardware guide](docs/HARDWARE.md), establish HOME and apply limits before moving. USB connection and a firmware acknowledgement do not measure the real arm's position.

**Esc** stops every motion; **Alt/Option + ←/→** jogs the selected joint in the Operator workspace. Clearing a joint checkbox can release winding current on wired A4988 drivers after confirmation; support a loaded axis before releasing it. J2/DM542 ENA is unwired in the reference configuration. Per-joint ENABLE control and simultaneous groups need the bundled firmware; the app never uploads it automatically.

**Supported hardware:** Mega 2560 and the documented RAMPS/A4988/DM542 configuration: J1/X A4988, J2/Y external DM542, J3/Z, J4/E0, J5/E1; J6 can be tested in preview, excluded, or configured for a separate external STEP/DIR driver. See the [Studio guide](docs/STUDIO.md) for exact limits.

## Tests

```sh
python scripts/run_tests.py
```

Tests isolate user data and use preview, mocks or pseudo-terminals (pseudo-terminal tests are skipped on Windows). With PySide6 installed they also drive the Qt window offscreen against the real controller in preview mode. They do not require a connected Mega and do not establish mechanical performance. CI runs them on Ubuntu, Windows and macOS. Optional integration checks: `python scripts/verify_firmware_workspace.py` (Arduino dependencies, compilation only) and `python scripts/verify_ros_observer.py` (prepared ROS environment).

## D.O.C. and ROS 2

The simulation and ROS 2 package are maintained in [DOC-Robotics](https://github.com/MichaelGAglieri/DOC-Robotics). Select that checkout in the app to enable the optional ROS observer. The robot controller works without ROS 2.

## Credits and license

Project by **Michael Giuseppe Aglieri**, with AI-assisted development and bench-driven iteration. Code is GPL-3.0-only; the bundled firmware uses Mike McCauley's AccelStepper; the mechanical reference is the ToolBox Robotics EB-15 / EBG-30 design. See [AUTHORS.md](AUTHORS.md), [THIRD_PARTY.md](THIRD_PARTY.md) and [LICENSE](LICENSE).
