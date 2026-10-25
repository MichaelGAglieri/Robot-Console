# Changelog

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
