# Robot Console Studio 2.0

Work in progress. The physical DOC arm has five DOF. The console provides six
logical joint channels. J6 is optional and can be excluded using its checkbox.
Language: choose Italiano or English in the header; this does not reconnect USB,
reset HOME, alter angles or change firmware. The preference is saved.

## Preview first

Operator → Start preview → Confirm HOME → choose ±5° → For all joints → Apply
limits. Try a 1° move, select a gripper state and record a pose. Return HOME before
replay. Preview does not open serial hardware. Recorded angles are commanded
pulse counts, not encoder measurements. STOP invalidates HOME and stops pulses;
an external DM542 with unmanaged ENA can retain holding torque.

## Five-axis DOC model

The bundled URDF is the same illustrative five-axis UR3e adaptation used by the
DOC presentation and Webots laboratory, with lime/black geometry and the radial
gripper. It is not physical EB-15 CAD. Nominal offsets align the presentation
HOME only; verify calibration before physical use. The gripper fingers are
visual elements, not the J6 channel. Fit view frames the whole model. Drag on the model to orbit, scroll or pinch to
zoom, or use ↺/↻ for 15° camera turns. These gestures never command the robot.

Import URDF accepts local, expanded arm descriptions and local STL/OBJ/DAE mesh
files. Xacro is not executed and assets are not downloaded. Imported models are
initially unmapped. Expand Joints, hardware mapping and TCP to assign channels,
sign/offset and tool position. Disabling a mapped joint blocks dependent commands,
sequences and HOME before execution, without electrically disabling the driver.
Prismatic joints are preview-only with the current rotary firmware backend.

Cartesian IK is position-only and updates preview. Execute displayed target
requires confirmation and physical mapping verification. Motion remains
sequential, one joint at a time. Workcell boxes use approximate link segments and
sampled paths: no complete mesh/self-collision or certified physical protection.

## Firmware editor

Disconnect control, then expand Firmware · parameters and editor. Set motor
steps/rev, microstep multiplier (8 means 1/8), reduction ratio and direction per
axis. Physical jumpers/DIP switches must match; firmware cannot change them.
Pulses per degree = motor steps × microstep × reduction / 360. Current settings
and power remain hardware adjustments. Speed is capped at 20°/s and by the
configured pulse budget; this is not a loaded mechanical speed guarantee.

Generate and save from parameters updates recognized constants and preserves a
revision. The source editor can edit saved .ino/.h/.cpp files. Save source before
Verify compilation or Upload to Mega. Compilation does not write a board. Upload
requires explicit confirmation and verifies board identity before writing. It
never starts motion afterwards. Reconnect and re-establish HOME manually.
Source motor constants that differ from the profile block physical control until
aligned. Free source edits require technical review even when compilation passes.

RAMPS has five motor outputs. Physical J6 requires a separately wired external
driver and explicit STEP/DIR configuration; its pins remain inactive by default.
Legacy five-axis poses and limits are extended with J6 at zero. Firmware reports
must match the active generated profile. No physical J6 test has been performed.

## Programs, projects and recordings

Programs support pose, gripper, wait, sensor, bounded repeat and note blocks.
Reorder, exclude, delete or edit them through the block editor. Start idle at HOME.
Errors and STOP never resume automatically. Excluded poses are skipped in programs.
Missing or stale sensor data times out. Sensor adapters must refresh at least once
per second; simulated samples cannot satisfy waits on the physical robot.

Project ZIP files contain URDF, meshes, configuration, sensor definitions, blocks
and poses. Import validates routes and replaces the local sequence; the last pose
change can be undone. Pose blocks refer to sequence indexes: recheck references
after reordering or deletion. Hardware authorization, conversations and credentials
are excluded. Firmware profiles are not automatically applied on import.
Record session keeps up to 18000 samples; export CSV for commanded angles,
mode, gripper and busy state. These values are not measured encoder feedback.

## ROS 2, camera and API

Choose an already prepared ROS/Pixi project. Connect ROS 2 displays observer
heartbeat, discovered nodes and laboratory topic freshness. It publishes console
state, /robot_console/joint_states, /robot_console/robot_description and TF under
robot_console/. These visualize preview or commanded estimates, not physical
measurements. ROS cannot command the hardware through this observer.

Optional RViz opens the console model. Webots opens the separate laboratory
paused. Gazebo opens an example scene, not a calibrated DOC dynamic twin.
rosbag records the documented topics. Tools are not installed automatically;
the app only stops processes it started. Full ros2_control, MoveIt planning,
calibrated vision/AprilTag and physical sensor feedback remain future work.

Camera and QR detection start only on request and require macOS permission.
Frames stay local. QR data never executes commands. The optional loopback API
requires the temporary Bearer token shown by the app. GET /v1/state and
/v1/health are read-only. POST /v1/sensors accepts a predefined input and value.
There are no USB, firmware, HOME or motion endpoints.

## Offline assistant and distribution

Ollama uses an installed local model; it can be started and unloaded from the app.
The assistant reads state and memory but cannot execute robot commands. English
is used for new assistant replies when selected. Historical notes, user content,
source code, firmware serial messages and third-party tool logs retain their
original language. English dictation requires an on-device macOS language model.

Apple Silicon macOS 14+, Python 3 and optional tools are external dependencies.
This build is ad-hoc signed, not Apple-notarized. A Developer ID/notarytool release
script is prepared for a future enrolled developer account. Third-party model
credits and BSD/GPL license notices are included in the app and source archive.

## Per-joint speeds, STOP and local notes

Each J1–J6 card in **Move and observe** has a speed in degrees/s. Use its slider
or enter a number and press Return or ✓. Settings are saved on this Mac and
apply to the next move, including programs and HOME returns. The controller moves
**one joint at a time**. The profile limit remains in force, up to 20°/s; speed
settings do not increase the driver's hardware current setting. **Apply to all**
replaces all six speeds with the common value.

**STOP Jn** stops that joint's pulses if it is the active joint, retains holding
torque and cancels the sequence. A STOP for an idle joint does not stop another
axis. Global STOP/Esc remains available for the current motion. Re-establish HOME
after a stop; there is no automatic resume. These software commands are not a
certified hardware emergency stop.

Unchecking a joint excludes it from commands and, with the updated firmware,
disables its ENABLE output if wired. J1, J3, J4 and J5 A4988 drivers release winding
current: **support a loaded axis before confirming**. Exclusion cancels the
sequence and invalidates HOME. Driver status is a firmware acknowledgement, not
an electrical measurement. Rechecking a joint prepares it; it is energized only
when the operator confirms HOME.

**J2/DM542 ENA is unwired in the current installation.** Exclusion blocks commands
but cannot remove its winding current or holding torque. The app states this
explicitly. Unconfigured J6 does not drive any pin.

Previous firmware still supports motion, speed and STOP, but cannot control
per-joint ENABLE. Disconnect control and use **Update joint commands…** in the
editor to prepare the new source: a revision is saved and microsteps, ratios,
directions and pins are retained. The main sketch is replaced; manual edits
remain in the revision. Compilation and uploading require explicit operator
actions with motor power removed. Updating the app never flashes the Mega.

**Notes** shows/hides a sidebar; drag the divider to resize its width. Notes are
automatically saved in the app's local preferences, excluded from exported
projects and never sent to the AI assistant. Development checks use preview,
mock serial and firmware compilation, without physical movement.
