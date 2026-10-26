# Changelog

## 2.0.0

- Add saved independent joint speeds, per-joint STOP and autosaved operator notes sidebar.
- Add acknowledged per-joint ENABLE exclusion for wired drivers; keep J2/DM542 explicitly unmanaged. Preserve the exclusion mask through HOME/ARM and require a new reference after release.
- Add explicit source upgrade with revisions and retained hardware parameters; no automatic Mega upload.

- Add Italian/English language selection, an English guide and English assistant replies.
- Bundle the existing DOC five-axis presentation/Webots visualization with orbit, zoom and automatic framing; preserve its third-party credits.
- Add local URDF import, an embedded 3D arm, selectable/excludable joints, TCP and mapping calibration.
- Add preview position IK, approximate workcell boxes, portable projects and recorded-path preview.
- Add bounded pose/gripper/wait/sensor/repeat/note programs and CSV telemetry.
- Add six logical joint channels with J6 preview, exclusion and optional external driver firmware; migrate five-axis poses and limits.
- Add editable firmware workspace, revisions, per-axis steps/microstepping/reduction/direction, compile and confirmed upload.
- Publish visualization URDF/JointState/TF; show ROS heartbeat/nodes/topics; launch optional RViz, Gazebo examples, Webots and rosbag.
- Add opt-in local camera/QR and authenticated loopback telemetry/sensor API without motion endpoints.
- Prepare Developer ID/notarization workflow; this local build remains ad-hoc signed.

## 1.7.8

- Exclude leading Ollama model attribution from speech while keeping it in chat.

## 1.7.7

- Add light, dark and system appearance with a persistent preference.

## 1.7.6

- Edit a pose's name, absolute joint angles, pause, gripper state and enabled flag.
- Temporarily exclude and re-enable individual poses without deleting them.
- Persist enabled state; reject stale edits and edits during motion.
- Extend the original route for angle edits and recheck limits before playback.

## 1.7.5

- Increase the configured speed range to 1–20°/s with Regia 4 firmware.
- Reorder/delete individual poses, undo the last sequence change and expose per-pose gripper requests.
- Reuse recorded path segments when transitioning between reordered poses.

## 1.7.4 and earlier

- Native macOS preview and Mega control, local assistant, Ollama lifecycle and ROS observer.
- Serial exclusivity, bootloader quiet interval, firmware/speed handshake and UI heartbeat while editing controls.
