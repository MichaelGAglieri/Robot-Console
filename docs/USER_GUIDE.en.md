# Robot Console — complete user guide

## Model warnings during a demonstration — build46

In **Operator → Connection and reference**, turn off **Block model collisions · Operator**, then confirm **Use warnings only**. This prevents approximate model collisions from blocking Operator sequences and HOME. Check the physical path yourself; this does not establish that physical collisions are absent. Limits, speed, STOP and Studio MoveJ/MoveL checks remain active. The choice lasts only for the current connection; reconnecting restores blocking. [Details](CAMPI_E_SEQUENZE.md).


Offline manual for local version 2.0.1, build 45. This project is under development.

## Joint order in sequences

Under **Your sequence → Joint order…**, select **One joint at a time**. Use the arrows to reorder the joints and enter a pause of 0 to 60 seconds after each one. The pause starts when the joint finishes, and is applied only if another joint needs to move. The pose dwell still applies at the end. The saved order covers every transition and the optional end-of-cycle HOME. **Sequence preview → Play preview** shows the path and pauses. The 3D view shows mapped joints only.

## 01 · What Robot Console does

Robot Console is an application for macOS, Linux and Windows for controlling an articulated arm, teaching and replaying poses, observing a 3D model and using local integrations. The four workspaces are **Operator**, **3D studio and programs**, **Diagnostics and ROS 2**, and **Assistant**. This guide works offline: search for a word, select a chapter or use Previous/Next chapter. Save manual exports the full text in the selected language.

**The DOC robot has five degrees of freedom**, J1–J5. The application exposes six channels for other configurations; J6 does not add a sixth joint to the DOC model. The model represents EB-15 and the EBG-30 gripper reconstructed from CAD. Its dimensions do not establish calibration of the assembled robot.

On first start you see the **schematic DOC** (capsules, discs and blocks with the same dimensions). The original ToolBox Robotics parts are licensed CC BY-NC-ND and are not included: for the **detailed model** download the [EB-15](https://www.thingiverse.com/thing:6488872) and [EBG-30](https://www.thingiverse.com/thing:6460300) packages from Thingiverse, then in **Arm model** press **Import EB-15 parts…** and choose the ZIP or STL files. The app recognises the original files by SHA-256 and builds the meshes in your data folder, for personal use only; do not share the generated files. Mapping, signs and scene are kept and collisions use the same capsules with both models.

Keep three kinds of information separate: the model's **virtual target**, **commanded angles** calculated from pulses, and **measured positions** from any sensors. This version has no integrated encoder feedback that corrects motor movement. A convincing animation or a completed serial command does not prove that the physical robot reached that location.

**Preview** runs a simulated controller and does not open a serial port. **Robot USB** opens the selected port after confirmation. Switching workspace or hiding a panel neither changes that mode nor stops movement.

**MoveJ** is the shared joint plan for Studio, poses and programs: the same plan is inspected in preview and, after confirmation, executed with **Execute MoveJ…**; **Execute displayed target…** uses it too. Play and programs of recorded poses connect active targets directly; programs with MoveJ/MoveL instructions use the same plan in preview and execution (chapter 12). **MoveL** moves the tip in a straight line with measured deviation. Collision geometry is approximate; automatic homing, arbitrary six-component Cartesian orientation and physical closed-loop control are not completed features.


**Build45 changes routes and input editing.** Sequences start at the current commanded position and visit only enabled pose targets, in visible order, using direct simultaneous joint transitions. The default is to stay at the last pose. “Return HOME at the end of the sequence” is optional; “Go HOME…” plans a direct return and asks for confirmation. Old recorded jog paths are archived and are no longer replayed by sequence/pose/HOME actions. Inspect Sequence preview before trying old sequences on hardware. A reference must be valid; the arm need not be at zero. Pure model/scene edits while idle keep the controller reference. STOP, reset, USB loss, firmware changes and physical release still require re-establishing it. Pose references in programs have stable IDs: deleting a pose causes a missing-pose error, never an index-based substitution.

**Input editing:** clear a field completely, enter a sign and finish a comma or dot decimal. Model HOME uses text drafts and preserves the last valid preview while incomplete; invalid values do not become zero. Apply/Save validates the complete text. Editing model HOME, mapping, TCP and work targets while idle does not disconnect USB or zero the physical count. The interface shows HOME reference valid, distinct from reaching HOME.

The following procedures describe build45. The bundled `docs/CAMPI_E_SEQUENZE.md` details migration and verification.

## 02 · First launch and testing without hardware

Start **Robot Console** with `run.sh` (macOS and Linux) or `run.bat` (Windows): the first start creates the `.venv` Python environment with PySide6. On macOS the SwiftUI app in Applications is also available. Launching does not automatically connect the Mega or upload firmware. Ollama, ROS 2 and Arduino CLI are needed only for their respective features. `--no-hardware` never opens the USB port; `--data FOLDER` uses a separate data folder.

To learn without moving the robot:

1. Under Operator → Connection and reference, select **Preview** and **Start preview**.
2. Press **Confirm HOME**. This establishes only a virtual zero in Preview.
3. Choose the **±5°** preset, press **For all joints**, then **Apply limits**. Filling fields alone does not apply them.
4. Set a 1° step in Move and observe and try J1 plus/minus. Watch the angles and events; enable **Follow commands** to make the model follow the count.
5. Record two named poses and try Once. Also try STOP, then re-establish HOME before continuing.

For the new planner, open Studio, enter J1=5, J2=−5 and the other MoveJ fields=0, optionally include a return, then plan and play. This animates the model without changing controller angles; it differs from jogging the simulated controller.

Neither an AI model nor ROS is needed for these tests. Read the USB, HOME, ENABLE and firmware chapters before controlling hardware.

## 03 · Interface, themes, language and panels

The top bar contains **Events**, **Notes**, **Guide**, **Language**, **Theme** and **STOP**. Select Italiano or English and Light, Dark or System appearance. System follows the operating system appearance. Highlighted controls show selections and available actions; dim controls usually mean a prerequisite is missing.

**Events** toggles the left activity/session sidebar. **Notes** toggles the right notebook. Drag their dividers to change width; double-click to restore the standard width. Shortcuts are ⌘B for Events and ⌥⌘B for Notes. The central area uses the remaining space with either or both sidebars hidden.

Central panels resize **vertically only**, using the lower handle. Fit restores natural content height. Disclosure headings expand advanced sections. A long form, grid or editor may have its own scrollbar inside the main page.

Appearance preferences stay on this computer. They are not firmware parameters and do not alter movement. Read messages above the workspace before repeating a failed action; they describe missing conditions or errors.

## 04 · USB connection and firmware identification

For physical control select **Robot USB**, choose the Mega port and press **Connect Mega**. Read the confirmation before proceeding. Opening serial may reset the board. Wait for firmware identity, capabilities and speed recognition before confirming HOME. A lit LED establishes board power, not a successful protocol handshake.

Arduino Serial Monitor or another application may occupy the port. Close that monitor before using Robot Console. Use a single controller instance for the personal data directory. The separate Studio Preview test app uses isolated data and blocks hardware access.

If the app reports **Mega without USB response**, check the selected port, data cable, port availability and the previous upload result. Allow time for startup. Do not repeatedly reset or upload solely because a response is missing: inspect the logs and confirm compatible firmware first.

The supplied profile targets Mega 2560/RAMPS 1.4, A4988 drivers and an external DM542 on J2. The editor supports certain driver variants and external J6; it does not automatically support any board or robot. USB can power logic but does not replace the required motor and servo supplies.

**Disconnect control** closes an idle controller connection. Do this before structural configuration or firmware work. After reconnection, reset, interruption or lost reference, do not assume the previous position is still valid.

## 05 · HOME: reference and return

**Confirm HOME** declares that the arm is already in the operator's chosen starting posture and zeros controller angles. It does not search for switches or move the arm to a known location. Without reference sensors, this is not automatic homing.

On hardware, confirmation may enable motor holding torque. Place the arm at the reference posture and support axes that could drop during a holding-state change. In Preview it establishes only a virtual zero.

**Go HOME…** plans a direct joint-space connection from the current position to zero angles, shows its trace and asks for confirmation. It does not replay old jogs or deleted poses. It respects each joint speed, checks all axes before starting and leaves the gripper unchanged. It is not a straight TCP line in space.

STOP, errors, reset or joint release can invalidate HOME. Restore the physical reference before confirming again; do not confirm merely to dismiss a message. Pulse counts cannot detect a manually displaced axis or missed steps.

**Model HOME…** is separate: it aligns the 3D representation. It does not change the controller reference or zero physical angles. See the model and TCP chapter.

## 06 · Joint limits and presets

Minimum and Maximum define each channel's commanded range in degrees relative to HOME. Zero ranges initially block motion. Ranges must include zero and remain within the software domain of −360° to +360°; that domain is not a claim that your mechanism can travel throughout it.

A field can be emptied while editing. Empty text is an unfinished draft; Apply requires valid numbers. Use a minus sign for the lower limit and review every axis before applying.

The preset menu offers Locked 0°, ±5°, ±15°, ±30°, ±45°, ±90°, ±180° and ±360°. **For all joints** fills all six pairs; each joint's menu fills only its pair. **Apply limits** submits and confirms the set. A preset does not know end stops, cables, covers or nearby equipment.

**Restore previous** fills values saved for the current mode; apply them explicitly. Preview and Robot USB have separate stored ranges. A visible value may still be a draft rather than an accepted limit.

Controller ranges and URDF limits are different. New MoveJ checks both, including calibrated signs and offsets. Keep unused axes locked or excluded consistently with the hardware configuration.

## 07 · Move and observe: step, angles and speed

In **Single** mode, each joint's minus/plus buttons request the selected relative angular step. A **step** is degrees per click, not speed. Use the quick buttons from 1° to 360°, slider, ±1° stepper, or type an angle and press **Set angle**.

For example, with commanded J1=10° and a 5° step, plus requests 15° and minus returns to 10°. Requests outside the applied range are rejected. The displayed angle describes the configured geared output, accounting for microstepping and reduction, not just the motor shaft.

Each joint has its own **speed in °/s**. Drag its slider or type a value and press **Return or ✓**. Hundredths are preserved. The common speed and **Apply to all** replace all six speed settings; they do not replace angle limits.

Individual speeds apply to controller jogs, groups, poses, programs and returns. The maximum depends on the profile; the current profile exposes up to 20°/s. That is not a guarantee for every reduction and load: the pulse budget can reduce actual planned speed.

Speed does not adjust driver current. A4988 and DM542 current are hardware settings. Step frequency affects available torque, losses and motion conditions. The app does not measure temperature, current or torque margin.

The **Keyboard** menu selects a joint for ⌥← and ⌥→ in Operator. Avoid these while entering text; HOME, limits and controller state still apply. **Additional channels** exposes unmapped J6 without adding model geometry.

## 08 · Simultaneous movements

Choose **Simultaneous** within Move and observe. Enter relative displacements, for example J1=10°, J2=−5°, others=0°. Zero keeps a channel stationary. Use the same joint speed fields as Single mode.

Apply every edited speed with Return or ✓, then use **Move together…**, review destinations, peak speeds and duration, and confirm. Hardware firmware must announce **MULTI_AXIS_V1**; older firmware can support single-axis movement without supporting groups.

Joints share a normalized acceleration profile while respecting each individual maximum. If one joint travels 10° and another 5° in the same segment, their effective speeds are proportional to distance. Each axis need not reach the number entered as its maximum.

The planner also caps aggregate steps at **2000 pulses/s**. This is a software design budget, not a certified bench measurement. High microstepping and reduction need more pulses per output degree and can greatly extend duration.

Changing position, speeds, HOME, limits, enabled axes or configuration after review invalidates the group; prepare it again. **STOP on any moving group member stops the whole group**. Recording a pose after a group retains that structure; sequence transitions now use direct simultaneous joint moves.

## 09 · STOP, joint checkboxes and current

Top-bar **STOP** and **Esc** interrupt current movement and sequence. They are software controls, not a certified hardware emergency stop, and do not isolate the power supply. Firmware retains holding torque where supported and the reference must be re-established after interruption.

**STOP Jn** stops that joint if it is the active single axis. If it belongs to a moving group, it stops the entire group. If Jn is stationary while another axis moves singly, use global STOP to stop the moving axis.

Unchecking a **joint checkbox** excludes movement and, with compatible firmware and wired ENABLE, disables the driver. On A4988 this releases coil current: a loaded axis can drop. Support it before confirming release. The sequence is interrupted and HOME invalidated.

In the current wiring, **J2's DM542 has ENA disconnected**. Excluding J2 prevents movement but does not remove current or holding torque. The UI states this explicitly. Software cannot operate an unwired connection. Unconfigured physical J6 drives no pin.

Checking an axis again prepares it; holding is re-enabled at HOME confirmation. The UI shows firmware acknowledgement, not an electrical measurement. Older firmware without per-axis ENABLE cannot provide all these actions.

**Stop preview / ■ MoveJ** stops only the graphical MoveJ animation and preserves controller HOME and angles. Global STOP remains a controller command and invalidates the virtual plan.

## 10 · Gripper and servo

**Open gripper** and **Close gripper** send the two firmware-configured commands. The default servo signal uses D11. Correct supply voltage, shared ground and servo compatibility must be established separately; the Mega USB supply is not a gripper power source.

The app shows the **last request**, not measured opening or force. It does not detect a successful grasp or automatically stop closing upon object contact. Grip depends on servo, supply, mechanism, friction and mechanical limits.

For a pose choose **Open**, **Close** or **Keep**. Open/Close are issued upon arrival; Keep sends nothing new. Playback retains gripper actions and dwell. Returning HOME does not automatically reverse the last gripper request.

Programs can contain a separate Gripper block between poses. New MoveJ planning displays gripper action virtually and allocates a conventional 1.5 s; this is not a measured servo duration. Gripper endpoints are firmware settings; forcing beyond a mechanical stop is not a way to increase grasp strength.

## 11 · Record, edit and reorder poses

Recording requires an idle controller connected in the chosen mode with a valid reference, without being at zero. Reach the position, enter a name, pause and gripper action, then press ＋ Record pose. Final angles are saved with a stable ID. Old taught routes remain archive data and are not used to reach pose targets.

Poses depend on the session HOME and robot configuration. A Preview pose is not automatically physically validated. Changing gear ratios, zero, signs or assembly can change its physical result.

**Edit** opens name, angles, pause, gripper and enable state. Save changes edits data without moving the robot. Directly editing angles differs from teaching a route: the app validates the resulting route under current rules but does not establish physical testing.

Use **Up/Down** to reorder and Trash to delete. **Undo last pose edit** restores the available last sequence edit, not unlimited history. Revision checks prevent an old editor silently overwriting a sequence that has changed.

A pose checkbox **temporarily excludes** that pose, including pause and gripper action, without deleting it. Routes to other poses may still traverse original path points or HOME. Excluding a pose does not eliminate every traversal of its spatial region.

**Once** starts at the current position and stops at the last active target. Repeat connects the last target to the first of the next cycle. Return HOME at the end is optional; Finish this cycle ends the current cycle. Inspect Sequence preview before confirming a run. Clear deletes the list after confirmation.

Reordering changes the order of direct simultaneous transitions. Deleted or disabled poses do not remain hidden stages. Inspect the new preview before using sequences from older versions.

## 12 · Programs: MoveJ and MoveL instructions

Under Studio → **Programs · instructions and preview**, pick the type in **Instruction**, fill in the row below and press **Add instruction**. The name is optional: without one the app proposes it (“MoveJ → Pezzo +60 mm”). Arrows reorder, the bin deletes and the checkbox skips the instruction without removing it. The program is saved in the project on every change and exported with **Export project…**.

**MoveJ** moves all joints together to: a **scene target** (with the **Z above** offset in millimetres in the target's frame, and the gripper aligned with the target axis or **position only**), **HOME** (all joints at 0°), a **saved pose** (its final angles) or the controller's **current angles**. For a target the app picks the IK solution closest to where the previous instruction ends. **MoveL** moves the tip in a straight line to a target, with the gripper held or free and a tolerance from 0.1 to 2 mm. **Gripper**, **Wait**, **Note** and **Repeat** complete the program; **Recorded pose** becomes a MoveJ to the pose angles.

MoveJ and MoveL **speed** is a percentage (10–100%) of the joint speeds set in Move and observe, editable on every row. The firmware accepts at least 1 °/s per axis: a lower percentage stays at 1 °/s. The pulse budget may still limit the simultaneous move; the row duration shows it.

**Plan program** computes the whole program: each instruction starts where the previous one ends, and the path is checked every degree against controller limits, URDF limits, self-collisions, obstacles and the work plane. Each row shows its duration; below appear the total estimated duration, segments and, for every MoveL, length, segments and maximum deviation. If an instruction cannot be carried out, planning stops there: the row gets a red border and a box gives instruction, segment, cause (for example “interference … work plane” or “unreachable: out of reach”) and angles. **Validate program** runs the same planning.

**Preview** animates the 3D arm along the plan; **⏮ / ⏭** jump to the previous or next instruction and the row marked ▶ is the one about to run; the slider shows any instant. Any change to instructions, targets, speeds, limits or model makes the plan expire: plan again.

**Run program…** runs exactly the plan shown, after confirmation: same segments, same speeds, same order. Before every segment the controller recomputes the profile and stops without sending pulses if it differs from the plan. **Step by step…** runs the first instruction and then stops before each of the others: **Next instruction** goes on by one, **Continue to the end** completes the rest, STOP interrupts. While running, the active row shows ⚡ (or ⏸ while waiting). At the end the measured duration appears next to the estimate (step-by-step pauses are not counted). If the program ends at HOME the return route is cleared; otherwise Go HOME plans a direct return on request. No automatic resume after an error.

On the real robot, programs with targets or MoveL need the declared physical model match, and the poses used must be recorded on the real robot.

**Repeat N times … End** repeats the instructions inside; the number may be an expression and the optional **counter** (for example `strato`) is 0, 1, 2… on each round. **If (condition) … Else … End** chooses between two groups of instructions. **Variable** assigns a value (`passo = 20`, `n = n + 1`). Repeat and If nest up to 8 levels; inner instructions are indented. A new instruction goes after the selected row (click the row): right after “Repeat” or “If” it goes inside them. Deleting a Repeat or an If also removes its End and Else while the inner instructions stay; disabling it skips the whole block.

**Expressions** use numbers, variables, the sensor names defined in Diagnostics, + - * / // %, comparisons (== != < <= > >=) and and, or, not; nothing else is executed. MoveJ and MoveL “Z above” also accepts an expression, for example `60 + strato*20` to stack. Variables, repeat counts and offsets are known at planning time; **sensors are read only in If conditions and waits**.

**Sensor wait** waits until the input has the given value, at most for the timeout; then the program stops. It counts as zero seconds in the estimate. An **If condition on sensors** cannot be known in advance: planning checks **both branches** at every condition, repeats included, and merges branches that come back to the same state (same position, gripper and variables). The box shows the branches checked; for each condition choose **True/False** for the preview and durations. While running, the condition is read at that moment and the program continues on the matching branch, always already checked; the conditions read appear under the plan and in the log. A problem in a branch not shown is still reported, with its branch (“branch: If at block 4 true”). Beyond 128 branches planning stops: reduce conditions inside loops that change variables differently.

In Preview a simulated value is enough (Diagnostics → Simulate 0/1). On the **real robot** only non-simulated data updated in the last second, sent by an adapter (local API), count; otherwise the program stops naming the sensor. The old “Repeat from the first block” stays for simple programs; with Repeat N times or If use the … End structure.

A program **without** enabled MoveJ/MoveL instructions, structures, variables, outputs or functions remains a **program of recorded poses**: targets are reached directly from current angles, sensor waits have a timeout and execution ends at the last instruction. There is no mandatory zero start or implicit HOME at the end. The JSON editor saves the list; stored pose references use persistent IDs in addition to display indices.

### Reusable functions and subprograms (build44)

In **Instruction → Function**, enter a technical name (e.g. `pick`) and comma-separated parameters (e.g. `height`). Add it: the definition and End function are appended at the top level. Select its start and insert the body between those two rows. The Z above field can use `height` as an expression. The main program skips definitions: only **Call function**, with a value for every parameter, runs the body, for example `height = 60`.

To call it from the main program, select End function or a main-level row, choose **Call function**, select the name and fill in the arguments. Add further calls with different values. The pencil edits a signature or a call; renaming updates call references, but changed parameters require updating arguments. Deleting a function deletes its whole body; remaining calls must be fixed. Any edit invalidates a computed plan.

Variables are **local**: a function sees only its parameters and variables created in its body. Returning restores the caller's environment, while position, gripper and I/O keep the state reached. **Return** exits immediately, including from nested loops/conditions, and can supply a numeric expression. To use it, set a **Result variable** in the call. Every reachable path must return a value if a result is requested; reaching End function without one is rejected. Example: `double(x)` → `Return x*2`; call with `x=30` and result `height`, which becomes 60.

Up to 32 functions, 8 parameters each and 8 call levels are supported; recursion is rejected. Parameters are numeric/boolean: target, pose and I/O references stay fixed in the body. Sensors may be read in conditions or waits, never in arguments or returned values. All sensor branches are planned with separate local environments and return points. Use Repeat N times … End; the older backward-jump Repeat cannot be combined with functions.

Plan, inspect and try **Step by step…** in Preview. The active label shows call → function → body instruction; execution pauses between body instructions and distinct calls, while segments belonging to one MoveL continue together. The first instruction starts immediately. STOP cancels without automatic resume. Speeds, limits and geometry checks belong to the shared plan; no firmware change is needed for subprograms.

Project save/export preserves everything; apps older than build44 cannot read these instructions. The bundled `docs/SOTTOPROGRAMMI.md` contains the full Italian procedure and JSON format. `examples/python_subprograms.py` plans pick/place with two functions; execution requires `--execute`, explicit permissions and, on the real robot, approval in the native app.

## 13 · 3D view and visual indicators

Swipe with **two fingers** on the trackpad or drag within the viewport to **orbit** the arm in both directions. **Shift + two fingers** (or Shift + drag or right-button drag) pans the view. **Pinch** on the trackpad or use the mouse wheel to zoom. Orbit stops when you lift your fingers; ↺/↻ rotate the camera incrementally. 3D, Front, Side and Top change only the viewpoint. **Fit view** includes the robot, work frames and targets and, when a valid plan exists, MoveJ TCP samples.

**Follow commands** shows estimated controller motion. Turn it off to prepare a virtual target using joint fields or IK. The model and any commanded-position ghost help distinguish target and count; neither is an image or measurement of the physical arm.

Small markers identify independent joints, not fixed flanges or gripper fingers. The orange line is the new MoveJ TCP path; recent points form a model trail. Red/green/blue coordinate axes represent X/Y/Z of frames and targets. TCP values below the view are in millimetres.

Obstacles and interference messages use capsules derived from links: self-collision between checked pairs, boxes and the work plane. Some nearby-by-design pairs are excluded. This approximate check does not cover every mesh detail, cable or held object. Graphics are not a safety certificate.

## 14 · URDF, joints, mapping and DOC model

With control disconnected, open **Arm model → Joints, hardware mapping and TCP**. **Import URDF…** requires an expanded URDF; convert Xacro first. Keep meshes and package assets near the file at supported paths. Missing-mesh warnings indicate that placeholder geometry may be shown.

For each independent joint, **Motor** maps to J1–J6 or Model only. **Direction** applies the sign; **offset** aligns geometric zero. Apply mapping saves configuration without rewiring pins or changing driver parameters. Avoid mapping two independent joints to the same channel.

URDF limits describe the model. Rotary UI angles are degrees while internal geometry uses radians. Prismatic units must be consistent; physical prismatic execution is not implemented by this joint controller. New MoveJ requires rotary joints and unique mappings for moving axes.

The joint checkbox excludes that joint from associated preview/control. A physically mapped channel may trigger the ENABLE release procedure; it is not merely a display switch.

**Load DOC 5 DOF** restores the reference model with five independent joints. J6 can appear as an additional channel without becoming a DOC joint. **I physically verified model, mapping, directions and offsets** is an operator declaration required for physical Studio workflows, not a measurement.

**Save project** stores the configuration. **Export project…** creates an archive with supported project/model assets; **Open project…** imports it and resets physical authorization. Operator notes and AI journal are excluded. Resource licensing remains in the original notices: importing a model does not grant redistribution rights.

## 15 · Model HOME and TCP

With control disconnected, press **Model HOME…** next to the 3D view. The sheet displays the model at commanded zero and lets you adjust offsets using sliders or numeric fields. Orbit and fit the view while aligning it visually to your chosen real posture.

**Cancel** discards the trial. **Save model HOME** preserves a project revision, applies offsets and requires renewed physical verification for Studio execution. It does not move motors, modify firmware or change controller HOME/angles.

This is **visual alignment**, not measured calibration. TCP accuracy, actual dimensions, backlash and signs need measurement. If the controller count was nonzero, the model can remain at the new HOME target; Follow commands returns to the current count.

The **TCP** is a tool point relative to the selected Tool link. XYZ fields are millimetres and apply with **Save TCP**. For example Z=50 mm adds 50 mm along that link's local Z axis, which rotates with the link rather than remaining world-vertical.

Changing TCP changes reported coordinates, paths and the IK problem, not mechanics or pulse counts. This version has a current tool/TCP, not a complete interchangeable-tool catalog.

## 16 · Work frames and local targets

Open this section with control disconnected. **Robot base** is implicit and immutable. A **work frame** defines an origin and orientation relative to base. A **target** is a position/orientation expressed in that frame.

Choose Frame, create a new item, name it, enter XYZ in mm and Roll/Pitch/Yaw in degrees, then Save frame. Frames are direct children of base in this version, without nesting. Rotation convention is Rz(yaw) · Ry(pitch) · Rx(roll).

Choose Target, create it, select its frame, enter name and local pose, then save. The tree and 3D markers show the result; base coordinates allow checking the transform. Moving a frame changes its targets in world space while retaining their local coordinates.

Example: frame XYZ=(100,200,0) mm with yaw=90°; local target=(50,0,0) mm. Base target=(100,250,0) mm. Move the frame to X=150 mm and base target becomes (150,250,0) mm. This is geometry, not a motor command.

Select an item to edit and save. Before deleting a frame, remove or reassign its dependent targets; base cannot be deleted. Schema 2 project persistence preserves the scene and creates a backup before older projects migrate.

Target orientation is stored and drawn; from build 34 **Compute IK for target** can use it (chapter 18). Named targets do not automatically become motion commands. A five-axis arm cannot generally realize every arbitrary six-component Cartesian pose: the console measures and shows the deviation.

## 17 · MoveJ and MoveL: planning, inspection and execution

**MoveJ** interpolates joint coordinates over a shared time profile. The TCP generally follows a curve, not the Cartesian straight line implied by MoveL. Planning, the time cursor and preview playback are pure calculations, also with the robot connected, while the controller is idle: they do not change commanded angles, HOME, route, poses or gripper. Only **Execute MoveJ…**, described at the end of this chapter, moves the controller.

Choose **Absolute angles** for six final angle values; **Studio joints** for the current virtual model target; **Saved pose** for pose angles, gripper and dwell; or **Program** for enabled poses, gripper, waits, notes and supported repeats. It builds new direct MoveJ segments without rewriting the existing taught routes.

If commanded J1=10°, entering J1=15° requests a +5° segment. **Use current angles** copies controller counts, not the manually edited geometric target; use Studio joints for that. Unmapped channels such as DOC's J6 must remain stationary.

Apply Preview limits in Operator and the desired per-joint speeds in Move and observe. An active simulated controller with virtual HOME lets you set them; planning does not require physical hardware. **Include return to starting point** adds and checks a direct return segment; the return moves the controller only when Execute MoveJ is confirmed, in the selected mode.

Press **Plan MoveJ**. Review estimated duration, sample count, segments and peak speed per joint. The calculation shares the simultaneous group's individual maxima, acceleration and aggregate 2000-pulse/s budget. Durations are estimates; gripper action uses a conventional 1.5 s.

**Play preview / ▶ MoveJ** animates from the start. **Stop preview / ■ MoveJ** freezes only that animation. The time slider inspects other instants and stops playback while dragging. Fit view includes the orange path. **Clear plan** removes the estimate without editing poses or programs.

Planning checks applied limits, calibrated URDF limits, exclusions, mappings and intermediate points against current obstacles. Sampling is at most 1° per joint; it is not full mesh collision checking or continuous checking between samples. Limits are 64 movement segments, 200 instructions, 4096 samples and one estimated hour. Sensor waits are rejected. If even the shortest rounded MoveL segment exceeds tolerance, planning is refused; tolerance is never silently widened.

Changing controller state, speeds, limits, model or program expires the plan; replan after review. Restoring previous values does not automatically revive an expired plan. Plans are temporary and not persisted.

**Execute MoveJ…** (from build 35) runs **exactly the displayed plan** after a confirmation stating mode, segments and duration. It needs confirmed HOME, an idle controller and a plan that has not expired. Each segment becomes one simultaneous controller move: same limits, excluded axes, speeds and pulse budget; on the real robot the app sends one `~multi` line per segment and waits for MULTI ACK and MULTI DONE from the Mega before the next. Gripper and dwell follow the plan; **Pause** holds execution between segments. Completed segments join the recorded route, so **HOME** returns along them.

**STOP**, USB loss, a missing interface, a DONE timeout or a firmware error interrupt at once: the count stays at the last completed segment, HOME must be re-established and **there is no automatic resume**. An executed or interrupted plan never restarts: plan again. On the real robot the Studio joints source needs the declared physical model match, and poses must have been recorded on the real robot, not in Preview. Programs with sensor waits stay on the existing program engine. Play, Once and programs of recorded poses connect active targets directly; programs with MoveJ/MoveL instructions run from the Programs panel (chapter 12).

**MoveL line** (build 36) is a MoveJ panel source: the tip travels **in a straight line** from the commanded position to a point, in the base or a work frame. Choose the gripper — **Keep** (axis and rotation stay as at the start, when the five axes allow it) or **Free** — and the **tolerance** (0.1–2 mm). **Use current point** and **Use saved target** fill the fields. The console solves IK every millimetre, each time starting from the previous solution, then merges the points into the few simultaneous moves that stay within the tolerance: the controller runs each segment by interpolating the joints, with angles rounded to 0.01°, and the deviation is measured on exactly that path. The summary shows length, segments, **largest deviation from the line**, end error and orientation deviation. If part of the line cannot be reached the plan is refused, stating **how many millimetres from the start** and why: out of reach, joint limits (including the limits applied to the controller), excluded joints, or a singularity or configuration change. The rest is the normal MoveJ: preview, obstacle checks, **Execute MoveJ…**, STOP and HOME. The backend runs one group at a time, so the arm pauses briefly between segments; after execution the panel shows the **measured duration** of each segment against the estimate, useful to learn the real Mega timing. On the real robot MoveL needs the declared physical model match.

## 18 · IK, Cartesian jog and obstacles

The **IK and Cartesian jog · preview** panel, below the Studio 3D arm, shows tip X/Y/Z in mm and the gripper direction in the chosen frame (robot base or a work frame). Everything here changes **only the virtual model**: no motor commands.

**Cartesian jog.** Choose a step (0.5–25 mm) and press −X/+X, −Y/+Y, −Z/+Z. With **Tool** the axes follow the gripper: +Z advances along the fingers. **Keep tool direction** preserves the gripper orientation while the tip translates. Rx/Ry/Rz rotate the gripper about the tip by 1, 5 or 15°. Each step starts from the current pose and looks for the closest solution; it is **rejected**, leaving the preview as it was, if the point is out of reach or beyond the limits, if one joint would turn more than 15° in a step (singularity or configuration change) or if the requested rotation cannot be achieved.

**Why some rotations are rejected.** The DOC has five axes: J1 orients the arm plane, J2–J4 work in that plane, J5 turns the gripper about its own axis. The gripper can therefore tilt only within the arm plane and spin about itself; a sideways tilt would need a sixth axis. With the gripper pointing down, for example, Rz (gripper rotation) works while a sideways tilt is rejected with its deviation in degrees. When translating with the direction kept, if the orientation cannot be preserved the step is applied and the deviation shown.

**IK to a point.** Enter X/Y/Z in mm in the chosen frame, pick the gripper mode — **Free** (position only), **Along −Z of the frame** (perpendicular to the plane, downward in the base) or **Keep current** — and press **Compute IK**. Position always comes first; orientation is reached when the five axes allow it, otherwise the console reports the deviation.

**IK for a saved target.** Choose a Work frames target and an orientation: **Position only**, **Position and Z axis** or **Z axis and rotation**. In targets the Z axis is the gripper direction (out of the flange) and the X axis its rotation: for a top-down grasp use roll 180°.

**Configurations.** The same point can often be reached in several ways, for example **Arm forward · elbow +** or **Arm backward · elbow −**. The console lists the solutions (angles, largest change, deviation), applies the one closest to the current pose and **Use** selects another. If the point cannot be reached it states why — out of reach (with distance and estimated reach), joint limits or excluded joints — and leaves the preview unchanged. The singularity warning appears when some directions would need large rotations, for example with the arm fully upright.

The calculations use the model dimensions and the Studio calibration (signs, offsets, TCP), not measurements of the arm. A preview result is not a request to execute regardless.

Calculation updates the virtual model. **Execute displayed target…** is separate and requires confirmation, HOME, limits, mapping and physical verification. From build 35 it plans and runs the shared MoveJ (chapter 17): all joints together, with the path sampled against obstacles; only firmware without simultaneous moves falls back to one joint at a time. It does not provide straight-line motion or automatic obstacle avoidance.

The obstacle JSON is a list of objects with name, center and size in metres, for example `[{"name":"table","center":[0.4,0,0.1],"size":[0.2,0.3,0.1]}]`. Center is base-relative; size is full extent, not half extent. **Apply obstacles** validates and saves the list.

Collision checking uses capsules derived from the link meshes, self-collisions, obstacles and the work plane z=0. Validate sequence checks direct transitions between active targets starting at the current position, with HOME only if selected; Play runs the same check and rejects a reported problem before moving. Validate program uses its program plan. Simplified geometry does not describe cables, held objects or every detail; no detected interference does not certify the physical route.

The validation follows explicit gripper blocks in program order, including gripper-only programs, and carries the resulting finger state into the next path and return. Before Repeat playback it also checks the second cycle starting with the last gripper state; later cycles repeat that state pattern. Gripper checks cover requested endpoint geometry, not a continuously sampled servo sweep. A standalone Validate sequence report checks one cycle; Repeat playback adds the second-cycle check automatically.

## 19 · Firmware parameters, microstepping and reduction

The editor works on a **local source workspace**, not directly on Mega flash. Disconnect control, expand **Firmware · parameters and editor → Microstepping, gear ratios and sources**. Reload profile fills the saved configuration.

Each axis has available driver, motor steps/revolution, microstepping, reduction and inversion. A 1.8° motor has 200 full steps/revolution. **Microstep 8 means 1/8**; reduction 38.4 means 38.4 motor revolutions per output revolution. Conversion is steps/revolution × microstep × reduction / 360 pulses per degree.

Values must match the actual A4988/DRV8825 jumpers, DM542 DIP switches and gearbox. Entering a number **does not electrically change jumpers or switches**. A mismatch changes physical angles and speed relative to the UI. Current, supply and cooling remain hardware settings.

RAMPS has five motor slots. **Physical J6** needs an external driver and compatible pins. The editor shows allowed pins; −1 means unwired. The current DM542 profile leaves ENA unwired. Do not assign pins without checking accessories and conflicts.

**Generate and save from parameters…** preserves a revision and regenerates local firmware constants. **Upgrade joint commands…**, when offered, replaces the main source with the bundled version and reapplies the profile. Review and recover any manual source customizations from the revision.

Select a file, Reload file, edit and **Save source**. Saving neither compiles nor uploads. Free-form edits can break identification, watchdog, limits and pin assignments. **Restore original firmware…** preserves the current workspace revision. **Export sources…** creates an archive; Open source folder shows local files.

Profile identity compares prepared parameters with recognized firmware; it cannot establish physical switch settings. Updating the app does not automatically program the robot.

## 20 · Compile and upload without Arduino IDE

Firmware tools need **Arduino CLI**, Arduino AVR core and AccelStepper. Arduino IDE is not required. The panel shows tool availability, boards and logs, with an official CLI installation link. **Prepare dependencies…** asks for confirmation and may download required components.

**Check compilation** builds saved sources without uploading to the board. Success does not establish wiring compatibility or physical behavior.

To upload: disconnect control, prepare the Mega with USB only and actuator supplies disconnected, refresh ports, select the correct board and press **Upload to Mega…**. Read and confirm. Do not let Arduino Serial Monitor or another controller use the same port.

Wait for the log result. Do not disconnect USB/power during writing. Cancel is available during cancellable phases, not noninterruptible flashing. The app stays disconnected after upload; reconnect explicitly, wait for recognition and re-establish HOME.

For a compile error, inspect the first meaningful diagnostic. For upload failure, check selected port and board availability. A successfully uploaded but unrecognized firmware needs protocol/parameter diagnosis, not blind movement commands.

## 21 · Robot voice commands and confirmation

Open **Move and observe → Robot voice commands**. This differs from AI chat dictation. The macOS app uses Apple's local speech recognition. In the Qt app (macOS, Linux, Windows) type the command in the field, or dictate it offline with Vosk: install `vosk` and `sounddevice` (`requirements-optional.txt`) and copy a Vosk model for the language (for example vosk-model-small-en-us) into the data folder under `speech/en` or `speech/it`. No audio leaves the computer. Typed or spoken, the confirmation is still “yes, confirm” and expires after 30 seconds. Ollama does not interpret these motor commands.

Press **Talk to robot** and speak clearly. “Move J2 by 5 degrees” requests a relative change. “Move J2 to 5 degrees” is absolute. “Move J1 to 5 degrees, J2 to 3 and J3 to minus 2” prepares a simultaneous group. “Start pose 1” follows the first pose's taught route, gripper and dwell and remains there.

After about 1.5 s without new words, the app validates and reads final positions and displacements. **Wait until it finishes**, then say **“yes confirm”** or **“cancel”**. Confirmation listening starts as a new session after synthesized speech, so the spoken summary is not treated as consent.

Italian examples: “muovi J2 di 5 gradi”, “muovi J2 a 5 gradi”, “avvia posa 1”, “sì, confermo” and “annulla”. Ambiguous phrases or unrecognized numbers are rejected, but transcription errors remain possible: listen to the entire summary.

Consent is one-use and expires after 30 s. Changes to HOME, position, mode, limits, speeds, enabled axes, poses or firmware invalidate it. Cancel listening closes the session. **Listen for next command when motion completes** continues only after successful completion; errors, STOP and cancellation do not restart it. About 20 s without a command ends listening.

Use buttons or Esc during motion. Noise, permissions and recognition latency make voice unsuitable as an emergency stop. Test this chain first in Preview with small angles and no hardware.

## 22 · Diagnostics, charts and sensors

**Record session** periodically collects commanded positions, mode, state and gripper information. The session retains up to 18000 samples; the chart shows recent data. **Export CSV…** saves collected samples. A recording is not a pose and CSV is not automatically an executable program.

The Origin label distinguishes **virtual** from **commanded pulses · without encoders**. Lines show those counts, not measured movement. A stalled motor or slipping gearbox may not be detected.

Enter an input name/type and **Define sensor** to add a data definition. Types include digital, distance, force, encoder and temperature. Defining a sensor neither installs hardware nor assigns a Mega pin or closes a feedback loop.

In Preview, **Simulate 0/1** supplies explicitly synthetic test values. Real inputs require an adapter reporting current values with the appropriate origin. Freshness is displayed. Missing/stale data must not be interpreted as a current reading; physical program waits reject synthetic data.

Adapters can use the local API for defined sensors. Motor control remains pulse-based: displaying encoder values here does not automatically implement position control, homing, collision avoidance or a safety-rated stop.

## 23 · ROS 2, RViz, Webots and Gazebo

The console uses an **already prepared ROS/Pixi project**; it does not install the full ecosystem. Select its folder and ROS domain, then **Connect ROS 2**. Default domain is 42 and must match tools you want to observe. Discovery is local.

The panel shows observer status, heartbeat, nodes and laboratory-topic age. **Disconnect** stops the app's connection. A recent heartbeat establishes observer activity, not physical robot movement.

Published visualization/state include `/doc_regia/stato`, `/robot_console/joint_states`, `/robot_console/robot_description` and TF prefixed `robot_console/`. Preview values are virtual; Robot USB values are pulse estimates. **ROS does not send motor commands into this app**, avoiding a second hardware owner on the serial link.

Expand **Optional tools and integrations**, detect project tools and launch those available. **RViz 2** displays the console model with appropriate frames/topics. **Webots** opens the separate laboratory, initially paused. **Gazebo** opens a sample scene, not a calibrated DOC dynamics model.

**rosbag recording** collects integration-defined topics. Stop controls processes started by this app, not every externally running instance. Logs stay local.

Masses, inertias, ros2_control, MoveIt, dynamics and simulation-to-robot transfer require separate implementation and tests. A launch button does not establish all those capabilities.

## 24 · Python API, programs and I/O adapters

In **Diagnostics and ROS2 → Python API · programs and I/O**, click **Start local API** and copy the session address and token. The service listens only on **127.0.0.1**, on a random port. Every request uses `Authorization: Bearer TOKEN`. Permissions and token reset whenever the API starts and are excluded from projects.

Enable **Allow program planning through the API** to submit instructions. Also enable **Allow script execution in Preview** for simulated execution. The standard-library Python3 client `robot_console_client.py` offers `plan(blocks, scenario)`: the same blocks as Studio replace the active project instructions and produce the same verified plan, with stages, duration, branches and localized problems. `execute(plan)` requires that plan’s exact id and fingerprint. No endpoint can connect USB, upload firmware, establish HOME or change limits.

**Every script execution on the real robot requires confirmation in the app.** The banner shows the script name, plan, duration and branches. Review in Studio, then Approve and execute or Reject request. Approval is single-use, expires after 60 s and is invalidated by plan, mode or state changes. The script must maintain its heartbeat while awaiting confirmation too.

`wait(run)` follows progress and renews the script heartbeat every 0.2 s. A script absent for 3 s triggers STOP without automatic resume. Script timeout and Ctrl-C also request STOP. App STOP and script `stop()` interrupt the same executor. Stopping the API or revoking permissions stops the API program. In step mode use `step(run)` or `continue_program(run)` while maintaining heartbeat. Measured durations are software observations, not measured robot positions.

Define inputs and **Digital outputs and adapters** in Diagnostics. A **Digital output** instruction selects a name, value 0/1 and timeout. Preview changes simulated state only. On the robot an external adapter receives a request; execution continues only after it acknowledges the requested value before timeout. No Mega pin is changed. Planning and preview do not command outputs. The shown duration excludes I/O waiting; the client also exposes an upper estimate including timeouts.

Adapters register their names, `simulated` origin and a session with a separate token. Heartbeat and samples must arrive within 1 s. An expired session requires registration again. Unregistered samples are always simulated. The real robot accepts only declared non-simulated, fresh samples; the adapter’s declaration is not hardware attestation. Conditions with unusable data stop; sensor waits continue until their timeout. Missing output adapter, wrong ACK or adapter loss stops execution. Expired or post-STOP acknowledgements never resume a program. STOP cannot retroactively undo an output already applied by the external device.

Main routes: `GET /v1/health`, `/v1/state`, `/v1/plan`, `/v1/runs/ID`; `POST /v1/program/plan`, `/execute`, `/heartbeat`, `/step`, `/continue`; `POST /v1/stop`. Sensors use `/v1/sensors`, adapters `/v1/adapters`, acknowledgements `/v1/io/ack`. **PYTHON_API.md**, bundled with the app, provides the complete protocol and examples (Italian technical reference). `examples/python_pick_and_place.py` only plans unless `--execute` is supplied and requires existing Pezzo and Deposito targets. Examples never configure hardware, HOME or limits automatically.

## 25 · Camera, images and QR codes

In **Vision · local camera**, select a device, refresh if necessary and press **Start video**. The system may request Camera permission on first use (on macOS for the app or terminal that starts Robot Console); if denied, update the Privacy setting before trying again. QR recognition in the Qt app needs the optional `opencv-python-headless` package.

Video, frames and codes shows a local feed. **Save frame…** writes a PNG where you choose. **Detect QR** reads visible codes from the current frame and shows their text; it does not execute that text as instructions.

**Stop video** releases the session; leaving the camera section also stops acquisition. External cameras must be recognized by the operating system. Video is not automatically sent to Ollama, a cloud service or ROS.

Optical calibration, 3D object pose, AprilTag, tracking and automatic grasping are not implemented here. Mapping pixels to robot coordinates needs camera/base calibration and an additional validated workflow.

## 26 · Assistant, memory and offline Ollama

The Assistant reads state and local journal and **does not execute movement**. Ask “What is the status?”, “Which poses are saved?” or “What happened?”. **Remember: …** explicitly stores an AI-journal note, separate from the operator sidebar notebook.

Type a question and Send. **Speak** dictates into the input; Stop dictation ends listening. This is neither a motor order nor motion consent. **Read response** reads the last assistant reply, omitting model-identification labels. **Silence** stops synthesized speech.

**Free conversation · offline AI with Ollama** enables a local model. The panel distinguishes installation, running service, selected model and models loaded in memory. Refresh rereads status; **Start and load model** prepares the selection. Sending a question with AI enabled can also start and load it.

Only already installed models are used; no model is automatically downloaded. If Ollama is missing, use the official link. Install an initial model with Ollama tools and refresh. The first download needs Internet; the local path works offline when runtime and model are available.

**Stop AI and free memory** disables free conversation and unloads the selected model, leaving it on disk. If this app started the service, it stops it; an externally owned service can remain running. Wait until a reply/load finishes before stopping. Apple Silicon memory is shared; disk model size does not equal live RAM usage.

The **Persistent journal** shows recent database entries. It records requests and software events, not physical measurements. A language model can be wrong; deterministic controls, not chat, authorize motion.

## 27 · Events, notes, projects and backups

**Robot activity** shows up to 300 recent session events with time and mode. Follow latest events toggles automatic scrolling. Hiding this sidebar neither clears events nor stops the robot. The persistent AI journal is separate.

**Operator notes** is a local auto-saved notebook, excluded from exported projects and not automatically passed to chat. Remember commands deliberately create AI-journal entries instead.

Personal application data resides under `~/Library/Application Support/DOC Regia`. Studio project data includes model, mapping, offsets, TCP, scene and blocks. The controller sequence and supported export data follow the current archive format. Export and check a copy before importing work on a different configuration.

Firmware/HOME revisions and pre-migration backups are distinct from app bundles. The local installer keeps current and penultimate managed app generations and moves older managed copies to Trash. It does not remove personal data backups with old apps.

Downgrading can require compatible data as well as the older executable. Earlier builds may not understand schema 2 work frames or grouped routes. Preserve and restore appropriate data backups rather than assuming binary replacement is enough.

## 28 · Ending a session and quitting

Wait for the controller to stop and inspect state, angles and surroundings. The left **HOME and quit** action offers an available return; while cycling, finishing the current cycle can reach HOME in order. The app finally requests **visual verification of HOME** because completion is pulse-based, not sensor-based.

**STOP and quit** interrupts without ensuring a return. If position is uncertain, do not confirm HOME just to remove the warning. Force-quitting the system cannot complete an orderly route.

Firmware watchdog stops on missing expected communication under its rules, but does not guarantee against electrical faults, axis drops or incorrect wiring. The DM542 with ENA unwired may keep holding torque after exit. The app does not replace equipment shutdown procedures.

Disconnect control and prepare the bench before firmware or wiring changes. Do not install an app update while the robot is moving or its serial port belongs to an active session.

## 29 · Troubleshooting

**Plus/minus disabled:** check mode, connection, recognized firmware, confirmed speed, HOME, applied limits and joint enable. USB alone supports board logic/recognition, not actuator power. Preview works without physical supplies.

**Apply edited speeds before moving the group:** confirm each draft with Return or ✓. If anything changes after group review, prepare it again. Applied speeds retain hundredths; changing to another number is not necessary just to submit the same value.

**Firmware HALTED/watchdog:** firmware stopped or missed expected communication. Read logs, check serial ownership, solve the cause and restore the reference. Do not disable watchdog or queue extra commands as a shortcut.

**MoveJ expired:** review target, limits and speeds and replan. **Calibrated URDF limit:** check model sign and offset as well as controller limits. **Unmapped axis:** a requested channel has no model joint, such as DOC J6. **MoveJ interference:** inspect the indicated segment and revise target/environment.

**Program will not start:** check HOME, pose mode, enabled poses, valid blocks and fresh sensor inputs. Synthetic input cannot substitute for a real sensor. **Model does not follow:** check mapping and Follow commands. A virtual target or MoveJ cursor can differ from controller count without moving anything physical.

**Physical motion wrong while graphics look right:** bench-check DIP/jumpers, microstepping, reduction, directions, coupling, supplies and calibration. Do not infer a cause from graphics alone or automatically compensate a fault with larger angles or current.

**AI or ROS unavailable:** these are optional. Check runtime/project, installed model, service state and logs; manual Preview does not depend on them. **Microphone/camera denied:** adjust the relevant system Privacy permission and retry explicitly.

## 30 · Glossary and current limits

**Joint:** a model motion degree. **Jn channel:** controller output mapped to a joint. **DOF:** independent degree of freedom; coupled gripper fingers do not make DOC a six-axis arm.

**Pose:** taught joint configuration, dwell, gripper and route. **Target:** geometric or joint destination, not automatically a physically tested pose. **TCP:** tool centre point. **Frame:** coordinates in which a target is expressed.

**FK:** computes geometry/TCP from angles. **IK:** seeks angles for a target: position first, then gripper direction and rotation when the five axes allow it. **MoveJ:** interpolates joint values, generally giving a curved TCP path. **MoveL:** straight TCP path, split into simultaneous moves within a measured tolerance (chapter 17).

**ACK:** firmware recognized a command. **DONE:** software completed planned pulses. Neither is encoder measurement. **Watchdog:** firmware interruption after missing expected communication. **ENABLE:** driver enable when wired, distinct from main power.

The project is work in progress. Position sensors, encoders, cameras, proximity sensors, LiDAR, full collisions, advanced planning and other backends require verified increments. The local build is ad-hoc signed. Apple Developer ID signing/notarization is not completed and requires the author's enrollment.

This manual describes available behavior and its boundaries; it does not certify electrical safety, load capacity or assembly accuracy. Learn the workflow in Preview, then use an appropriate physical commissioning procedure for the actual hardware.
