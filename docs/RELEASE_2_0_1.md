# Robot Console 2.0.1

This update brings the locally tested builds 27–30 to the public macOS release.

- **Simultaneous joint groups:** enter relative joint movements, review the summary, then explicitly confirm. Each joint shares the same speed setting used by manual control and taught poses. Groups respect the profile limits and a conservative aggregate pulse budget; the interface displays estimated duration and peak speeds.
- **Joint-speed confirmation fix:** applied speeds retain two decimal places, and Return or ✓ clears the edited state even when the text does not change. Acknowledged speeds no longer falsely block subsequent groups; unapplied edits still block execution.
- **Italian/English voice commands:** local Apple recognition, spoken target readback, then a separate “yes confirm” / “sì confermo” or cancel step. Supports joint targets and individual recorded poses. Confirmation expires and is invalidated by changes to the relevant robot state. Ollama chat has no motion authority.
- **Flexible operator workspace:** robot events on the left, private notes on the right, independent sidebar visibility and widths, central panels that fill the available space, and compact adaptive joint limits.
- **Larger 3D preview and visual model HOME:** preview and save model-joint offsets while disconnected, with a recovery copy. This does not zero the physical robot or alter firmware. The bundled DOC visualization remains an illustrative five-DOF Webots/presentation model.
- **Light appearance:** consistent button outlines, larger and darker secondary text, readable native selectors, and the same bright lime accent as dark appearance.
- **Local update retention:** the optional installer preserves the immediately previous app and a separate data recovery archive; older managed application copies move to Trash.

## Firmware compatibility

Simultaneous physical moves require the bundled Regia 4 firmware to advertise `MULTI_AXIS_V1`. Updating the application does **not** upload firmware. Existing editable firmware workspaces are retained: use **Update joint commands…**, inspect/compile the saved sources and explicitly upload with motor power off. Older firmware continues to support its existing single-joint commands.

Legacy taught paths and Studio targets retain their original sequencing. New explicit groups are recorded and replayed as groups. STOP on an active group member interrupts the whole group and invalidates HOME while retaining holding torque. J2/DM542 ENA is unwired in the reference configuration; software cannot remove its holding torque.

## Requirements and verification

Apple Silicon, macOS 14+, and Python 3. Optional firmware, Ollama and ROS dependencies remain separate. The app is ad-hoc signed and **not Apple-notarized**.

**134 isolated automated tests passed locally**, alongside native compilation and preview regression checks. These checks validate software behavior. The speed-warning defect was reproduced on the old UI, then two successive virtual J1/J2 groups and decimal-speed confirmation were checked on the corrected UI. No hardware connection, firmware upload or physical motion was performed during this release preparation. Pulse timing, missed steps, loads, collision clearance and acoustic voice recognition in the real environment require separate validation. Positions are pulse estimates without encoder feedback.

## Download and data

Download `Robot-Console-2.0.1-macOS-AppleSilicon.zip`, extract the application and copy it to Applications after quitting the old app. The corresponding source archive and `SHA256SUMS.txt` accompany the release. Personal poses, notes, conversations, source-workspace revisions and local backup archives are excluded. Back up data before upgrading. Builds before simultaneous-group support cannot interpret new group paths; restore a matching data backup before downgrading.

**Work in progress.** Sensor and platform integrations remain on the roadmap. GPL-3.0-only project by Michael Giuseppe Aglieri, with AI-assisted development; third-party geometry and libraries retain their original credits and licenses. See `THIRD_PARTY.md` and `models/doc5/NOTICE.md`.
