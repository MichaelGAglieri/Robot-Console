Robot Console 2.0 adds a native arm workspace while retaining the five-axis DOC bench configuration.

- **Independent joint speeds**, stored per axis and used in sequences, with a common Apply to all control. Motion remains sequential.
- **Per-joint STOP**, holding torque retained, plus acknowledged ENABLE exclusion for wired drivers. Clearing a joint requires support of loaded axes and a new HOME reference. **J2/DM542 ENA remains unwired: software cannot remove its holding torque.** The feature requires the updated firmware; source upgrades preserve profiles and revisions without automatic upload.
- **Operator notes sidebar**, autosaved locally and kept separate from exported projects and AI memory.
- **Italian / English** language selection, saved across launches, with an English guide and local assistant replies.
- **DOC 5 DOF visualization** from the existing Webots/presentation model, with lime/black mesh geometry, three visual gripper fingers, orbit/zoom controls and fit view. This is an illustrative UR3e adaptation, not calibrated physical EB-15 CAD.
- Local URDF import, joint exclusion, sign/offset mapping, TCP and position-only preview IK.
- Six logical joint channels, including **J6 preview/exclusion and optional external driver configuration**. RAMPS still has five motor outputs; J6 pins stay inactive by default.
- Editable firmware sources with revisions, per-axis microstepping/reduction settings, compile and explicitly confirmed upload.
- Pose editing/reordering/exclusion and gripper recording; bounded program blocks; portable model/pose projects and CSV recordings.
- ROS heartbeat/nodes/topics, visualization URDF/JointState/TF and optional RViz/Webots/Gazebo-example/rosbag launchers.
- Optional local camera/QR and authenticated loopback telemetry/sensor API without motion endpoints.
- Light/dark/system appearance and model metadata excluded from spoken assistant replies.

**Requirements:** Apple Silicon Mac, macOS 14+, Python 3. Arduino CLI or Arduino IDE plus the documented dependencies are needed for firmware builds. Ollama and a local model are optional; ROS tools require a separately prepared environment. No model weights or toolchains are bundled.

**Work in progress:** the app is ad-hoc signed and **not Apple-notarized**. Physical motion remains sequential and pulse-estimated, without encoder feedback. Approximate geometry/IK checks are not certified collision protection. Gazebo opens an example scene, not a calibrated DOC dynamic twin. The chat and ROS observer cannot command the hardware.

Development verification: **117 automated tests passed locally**, including actual sketch command logic with inert C++ GPIO/serial stubs; three AVR firmware profiles compiled successfully. Further checks used preview, pseudo-terminals and isolated loopback ROS/API messaging. **No Mega upload or physical robot movement was performed for this release.** J6 physical operation has not been bench-tested.

Application/firmware integration: **GPL-3.0-only**, Michael Giuseppe Aglieri, with AI-assisted development. Bundled UR3e-derived geometry retains **BSD-3-Clause** attribution and license; DOC illustrative gripper and integration are credited separately. See THIRD_PARTY.md and models/doc5/NOTICE.md.

Download the Apple Silicon ZIP, extract Robot Console.app and copy it to Applications. The source ZIP contains corresponding sources and build scripts; SHA256SUMS.txt lists both archive digests. Existing five-axis pose data is read with J6 at zero. Back up your configuration and use Preview before reconnecting hardware. Historical user text, source code, firmware output and third-party logs retain their original language.
