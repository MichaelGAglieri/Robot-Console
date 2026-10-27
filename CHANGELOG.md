# Changelog

## 2.0.1

Published update incorporating local builds 27–30: simultaneous joint groups and confirmed voice commands, responsive sidebars and model HOME preview, light-theme improvements, and corrected joint-speed acknowledgement. See [release notes](docs/RELEASE_2_0_1.md).

## Local build 30 (unreleased)

- Fix stale edited-speed warnings after acknowledging joint speeds: reconcile explicitly even when the displayed value does not change.
- Preserve two decimal places from the controller instead of rounding applied speeds to tenths; observe each joint speed independently.
- Verified in hardware-blocked preview: reproduce the old 1.25 to 1.2 mismatch, confirm decimal speed, perform two successive groups, and check that only unapplied edits block execution.
- No firmware or motion-planning changes.

## Local build 29 (unreleased)

- Responsive central panels and adaptive joint/3D layouts for open or hidden sidebars.
- Continuous inset button outlines, shared bright lime accents and larger high-contrast captions in light mode.
- Compact eager limits grid avoids oversized scrolling regions; native selectors use readable text in light mode.
- Presentation-only changes; firmware and motion settings unchanged.

## Local build 28 (unreleased)

- Flexible larger 3D pane and visual model-HOME editor, with pure preview, explicit save, project recovery copy and no hardware-zero changes.

- Left robot activity sidebar with timestamped session events, right operator notes and independent persistent visibility controls.

- Single and simultaneous motion share one set of joint cards and speed controls.
- Read-only group speed/duration preview, applied-speed gating, and stale-summary rejection; voice readback includes estimated joint speed peaks.
- MULTI_AXIS_V1 firmware unchanged from build 27.

## Local build 27 (unreleased)

- Explicit simultaneous joint groups, shared acceleration profile and bounded aggregate pulse rate; preserves grouped taught routes.
- Local Italian/English motion dictation with spoken readback and single-use spoken confirmation, plus individual pose execution.
- Updated firmware required for groups; no automatic upload. Physical timing and acoustic recognition remain to be validated by the operator.

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
