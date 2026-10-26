# Robot Console

> **Work in progress.** This project is under active development. Hardware, software, interfaces and configuration can change. See the [roadmap](ROADMAP.md).

A native macOS application for teaching, previewing and replaying arm poses on up to six joint channels. The physical D.O.C. reference robot has five DOF. It was developed during my D.O.C. robotics project and currently ships with that project's hardware configuration.

## Features

- Preview mode without hardware and explicit USB connection to the robot.
- Italian / English selection and light, dark or automatic macOS appearance, with saved preferences.
- Operator-defined HOME, editable joint limits and independent 1–20°/s joint speeds within the hardware profile limit.
- Per-joint STOP with holding torque, confirmed ENABLE control on wired drivers, and an autosaved operator notes sidebar.
- Pose recording, editing, reordering, deletion, temporary exclusion and one-step undo.
- Per-pose gripper state, pauses, repeat cycles and return along recorded paths.
- Bundled DOC 5 DOF presentation/Webots visualization, orbit/zoom/fit controls, local URDF import, joint exclusion, mapping, sign/offset calibration and TCP.
- Position-only preview IK, approximate workcell boxes, bounded program blocks and CSV recordings.
- Per-axis motor steps, microstepping, reducer ratio and direction; editable firmware sources, revisions, compilation and confirmed upload.
- RViz visualization topics, ROS health, optional tool launchers, camera/QR and authenticated loopback sensor API.
- Optional local Ollama chat, conversation journal, on-device Italian dictation and a read-only ROS 2 observer.

**Supported in this release:** macOS 14 or later on Apple Silicon, Python 3, Mega 2560 and the documented RAMPS/A4988/DM542 configuration. The firmware backend remains Mega/RAMPS: J1/X A4988, J2/Y external DM542, J3/Z, J4/E0, J5/E1; The bundled visualization retains five arm DOF; J6 can be tested in preview, excluded, or configured for a separate external STEP/DIR driver. Other boards and Windows are not supported yet. See [Studio guide](docs/STUDIO.md) for exact limits.

## Install or build

Download the macOS application from [Releases](https://github.com/MichaelGAglieri/Robot-Console/releases), unzip it and copy `Robot Console.app` into Applications. Python 3 must be installed. For firmware compilation/upload, install [Arduino CLI](https://arduino.github.io/arduino-cli/) or Arduino IDE; the app finds either installation. Ollama is optional and is installed separately.

The current build is ad-hoc signed, not notarized or signed with an Apple Developer ID. Follow normal macOS security checks and review the source; this repository does not provide commands to disable Gatekeeper.

To build the app locally, install Apple's Command Line Tools and run:

```sh
zsh native/build.command
```

This creates `Robot Console.app` in this directory without opening USB, starting Ollama or uploading firmware. Read [docs/STUDIO.md](docs/STUDIO.md) and [docs/USAGE.md](docs/USAGE.md) before connecting a robot. Current version: **2.0.0**; included firmware protocol: **Regia 4**.

## First use

1. Open the app and choose **Anteprima**. Confirm a virtual HOME and apply small limits.
2. Move a virtual joint, choose a gripper state and record a pose. Use **Modifica** to change it and the row switch to exclude/re-enable it.
3. Return to virtual HOME and replay. Only enabled poses perform their pause and gripper action.
4. For physical use follow the [hardware guide](docs/HARDWARE.md), establish HOME and apply limits before moving. USB connection and a firmware acknowledgement do not measure the real arm's position.

Physical movements remain sequential, one joint at a time. Clearing a joint checkbox can release winding current on wired A4988 drivers after confirmation; support a loaded axis before releasing it. J2/DM542 ENA is unwired in the reference configuration, so software exclusion cannot remove its holding torque. Per-joint ENABLE control requires the updated bundled firmware; updating the app never uploads it automatically.

Pose editing saves data without moving the robot. New joint values extend the original recorded path in J1–J6 order; they are not collision-checked. Excluded poses can still be crossed by the recorded paths of later enabled poses.

## Tests

```sh
python3 scripts/run_tests.py
```

Tests isolate user data and use preview, mocks or pseudo-terminals. They do not require a connected Mega and do not establish mechanical performance. Optional integration checks: `python3 -m unittest test_local_api` (loopback socket), `python3 scripts/verify_firmware_workspace.py` (installed Arduino dependencies, compilation only), and `python scripts/verify_ros_observer.py` (prepared ROS environment). The macOS build workflow also compiles the Swift application.

## D.O.C. and ROS 2

The simulation and ROS 2 package are maintained in [DOC-Robotics](https://github.com/MichaelGAglieri/DOC-Robotics). Select that checkout in the app to enable the optional ROS observer. The robot controller works without ROS 2.

## Credits and license

Project by **Michael Giuseppe Aglieri**, with AI-assisted development and bench-driven iteration. Code is GPL-3.0-only; the bundled firmware uses Mike McCauley's AccelStepper. The app illustration was generated with AI and supplied by the project author. See [AUTHORS.md](AUTHORS.md), [THIRD_PARTY.md](THIRD_PARTY.md) and [LICENSE](LICENSE).
