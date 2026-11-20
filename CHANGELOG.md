# Changelog

## 2.0.1 · build47 — ordine dei giunti nelle sequenze

- Movimento simultaneo o un giunto alla volta con ordine salvato e pause individuali.
- Anteprima e validazione usano gli stessi passaggi delle sequenze, compreso il ritorno HOME opzionale.


## 2.0.1 · build46 — interferenze modello in Operatore (locale)

- Scelta per la connessione corrente: interferenze 3D bloccanti oppure solo avvisi per sequenze, pose e HOME. Conferma esplicita e indicatore visibile; ripristino alla connessione successiva.
- Limiti, velocità, STOP, firmware e modello invariati; Studio MoveJ/MoveL conserva i controlli. Piani invalidati al cambio della scelta.
- Prove esclusivamente simulate; non determina se `link_3 / link_5` corrisponda a una collisione fisica.


## 2.0.1 · build45 — campi, pose visibili e riferimento (locale)

- HOME del modello e dominio ROS usano bozze di testo: cancellazione libera, segni e decimali, validazione finale, nessun clamp durante la scrittura. Velocità in modifica protette dagli aggiornamenti, ripristino limiti a cinque/sei canali corretto e jog da tastiera esclusi durante l’immissione.
- Sequenze dalla posizione attuale, solo pose attive in ordine visibile, transizioni articolari simultanee con le velocità dei giunti. Rimane sull’ultima posa per impostazione predefinita; ritorno HOME diretto e facoltativo, anteprima e conferma.
- Pose eliminate/escluse non inseriscono tappe storiche, anche nei ritorni. Riferimenti stabili nei programmi con errore esplicito quando la posa è eliminata; migrazione con copia del file originale.
- Modifiche virtuali da fermo conservano il riferimento del controllore; STOP, reset, USB e rilascio mantengono le protezioni. Percorsi diversi dalle vecchie build: rivedere l’anteprima prima di prove reali. Nessun firmware o modello modificato.


## 2.0.1 · build44 — Funzioni e sottoprogrammi (locale)

- Editor con definizioni, parametri, richiami modificabili e risultati opzionali. Le variabili restano locali; le definizioni non eseguono per caduta dal programma principale.
- Chiamate annidate e uscita anticipata, ricorsione rifiutata; tutte le diramazioni sensore restano sul pianificatore comune.
- Passo passo distingue i richiami della stessa istruzione e mostra funzione/corpo; STOP continua ad annullare senza ripresa.
- Stesso formato per editor e API Python, salvataggio/esportazione, esempio presa/deposito e guida IT/EN aggiornata. Nessuna modifica al firmware, ai driver o al modello EB-15.

## Local build 42 (unreleased)

- Roadmap phase 6, second increment: Repeat N times … End (nested, optional counter), If … Else … End, Variable and Sensor wait in offline programs. `program_lang.py` parses expressions with a whitelist of syntax nodes (numbers, names, arithmetic, comparisons, and/or/not) and checks the block structure (8 levels).
- Variables, repeat counts and target offsets (e.g. “Z above” = `60 + strato*20`) are known while planning; sensors are read only in If conditions and waits. At a sensor condition both outcomes are planned; identical states merge, so branches that rejoin are planned once (limits: 128 branches, 120,000 samples). The executor (`movej_run.run_tree`) reads the condition and continues on a planned branch only; the preview follows the branch chosen per condition (True/False).
- Real robot: only fresh (under 1 s), non-simulated sensor data count. Problems in branches not shown are reported with the branch. Program panel: insertion after the selected row, indentation, structure-aware delete, branch choice, conditions read.
- 9 new tests (224 total). Guide chapter 12 and `docs/PROGRAMMI.md` updated. Not tested on the physical arm.

## Local build 41 (unreleased)

- Roadmap phase 6, first increment: offline programs. New MoveJ (scene target with Z offset and target axis or position only, HOME, saved pose, current angles) and MoveL (straight line to a target, gripper held or free, 0.1–2 mm tolerance) instructions, each with its own speed as 10–100% of the Move and observe joint speeds (minimum 1 °/s, the Mega's floor).
- `program_plan.py`: each instruction starts where the previous one ends (IK seeded with those angles, MoveL waypoints); the whole program becomes one shared MoveJ plan, so 3D preview, estimated duration per instruction, validation and execution are the same plan. Before every group the executor recomputes the profile and refuses to send pulses if speeds or duration differ.
- Problems are located on their instruction and segment (red row, cause and angles); Validate program plans MoveJ/MoveL programs the same way.
- Step-by-step execution (Next instruction / Continue to the end / STOP) with the active row highlighted; preview jumps to previous/next instruction. Measured duration excludes operator pauses. A program ending at HOME clears the return route.
- Programs are saved in the project; programs without MoveJ/MoveL keep the taught-route behaviour. Sensor waits, variables and conditions are the next increment.
- 10 new tests including a pick-and-place task checked line by line against a simulated Mega (215 total). Documentation: `docs/PROGRAMMI.md`, guide chapter 12 (IT/EN). Verified in the isolated preview; not tested on the physical arm.

## Local build 38 (unreleased)

- Roadmap phase 5: collisions and whole-program validation. `collision.py` derives up to four capsules per link from its meshes (any URDF arm), checks self-collisions, workcell boxes and an optional work plane z = 0 with an adjustable margin; adjacent, rigid, finger and close-by-design pairs are excluded automatically. Used by preview, IK/jog, MoveJ/MoveL and Studio targets.
- `validation.py`: Validate program / Validate sequence replay the taught routes as the controller runs them (shared prefix, backwards legs, return to HOME) at 1° steps against applied limits, calibrated URDF limits and collisions, reporting leg, problem and angles. Play and Run program run it first: blocking in Preview or with the declared physical match, logged otherwise.
- Workcell controls (work plane, margin) saved in the project. 9 new tests (199 total). Documentation: `docs/COLLISIONI.md`, guide chapter 18 (IT/EN). Not tested on the physical arm.

## Local build 37 (unreleased)

- Professional industrial look, especially in light mode: neutral cool palette (grey canvas, white cards with fine border and soft shadow, distinct sidebars), DOC lime kept as brand accent and deep green for readable active text; dark mode harmonised to neutral graphite.
- Dark header bar in both themes with brand mark, connection and mode chips (amber for real robot), Events/Notes/Guide controls and STOP; lime rule under the header.
- Panel titles as uppercase technical labels with a divider, compact buttons, warning banner, neutral 3D viewport background, compact step buttons without truncation, legible selected segments.
- Contrast: text 15–18:1, secondary 5.9–7:1, accent 4.8–5.7:1 in light mode. Presentation only: no motion, firmware or model changes.
- Studio “3D arm · virtual target”: only the viewport has a height, with its own drag handle (280–900 pt, remembered, double-click resets); title, HOME, view buttons, view picker and TCP readout are always visible (they were clipped by a fixed 440 pt frame). Header subtitle removed.

## Local build 36 (unreleased)

- Roadmap phase 4: MoveL. `movel.py` samples the straight TCP line every millimetre with continuous IK (URDF and controller limits), then merges points into the fewest joint-linear segments whose executed path (angles rounded to 0.01°) stays within a chosen tolerance (0.1–2 mm). Unreachable sections are located by distance and reason; orientation deviation is reported.
- MoveL is a new source of the shared MoveJ plan, so preview, obstacle sampling, Execute MoveJ…, STOP and HOME are unchanged. Real-robot execution needs the declared physical model match.
- The executor measures the real duration of every stage (shown against the estimate) to learn the Mega's timing.
- 6 new tests (190 total). Documentation: `docs/MOVEL.md`, user guide chapter 17 (IT/EN). Not tested on the physical arm.

## Local build 35 (unreleased)

- Roadmap phase 2 completed: shared MoveJ execution. `movej_run.py` runs exactly the previewed plan (same id and context) after explicit confirmation; each segment is one `move_group` (validated `~multi` line, MULTI ACK/DONE, timeout, STOP generation), gripper and dwell from the plan, pause between segments. Completed groups join the trail, so HOME returns along them; no automatic resume after STOP, USB loss, missing interface, timeout or firmware ERROR.
- MoveJ planning and visual preview now also work with the robot connected (pure geometry). Real-robot execution requires MULTI_AXIS_V1 firmware, the declared physical match for the Studio joints source and poses recorded in robot mode.
- “Execute displayed target…” now plans and executes the shared MoveJ (simultaneous, path sampled against obstacles); firmware without MULTI_AXIS_V1 keeps the previous one-joint-at-a-time route. Play, Once and Run program keep their taught routes.
- MoveJ panel: Execute MoveJ… with confirmation, segment progress, STOP and result. 10 new tests with a simulated Mega protocol (184 total). Not tested on the physical arm.

## Local build 34 (unreleased)

- Roadmap phase 3, first increment, preview only: prioritized five-axis IK (TCP position, then gripper axis, then rotation about it) in `ik5.py`, Studio adapter `ik_studio.py`, new **IK and Cartesian jog · preview** panel.
- IK to a point in the base or a work frame (free, along −Z of the frame, keep current) and to saved targets (position, Z axis, Z axis and rotation). Several configurations listed with labels; the closest to the current pose is applied, others selectable.
- Cartesian jog XYZ and Rx/Ry/Rz about the tip in base, work frame or tool. Steps start from the current pose; rejected with the preview unchanged when out of reach, beyond limits, needing a large joint jump or a rotation the five axes cannot realize. Singularity warning and explicit unreachability reasons.
- The legacy `studio_ik` request now uses the new solver (position only by default). No controller, serial, firmware or execution-path changes; existing “Run displayed target…” is unchanged.
- 10 new tests (174 total). Documentation: `docs/IK_JOG.md`, user guide chapter 18 (IT/EN), Studio notes.

## Local build 32 (unreleased)

- Base-relative work frames, local XYZ/RPY targets, scene tree and 3D axes/markers; geometric metadata only, no new motion or firmware authority.
- Restore valid project mesh paths before reporting unavailable assets, retaining genuine missing-mesh diagnostics.
- Schema 2 projects preserve references/targets through export/import. Legacy schema 1 migration creates a dated recovery copy; imported projects never grant physical authorization.
- Preserve Claude’s approved EB-15/EBG-30 geometry and model-upgrade migration. Updated the obsolete UR3e guide text.
- ToolBox mesh redistribution remains unresolved: do not publish this local build automatically.

## Local build 31 (unreleased)

- Replace the bundled DOC visualization with the five-axis assembly of the original ToolBox EB-15 arm and EBG-30 gripper STL parts (generated by D.O.C.Mac/hardware/modello_doc5/genera_modello.py). Joint zero is the arm straight up; link lengths come from the CAD parts, not physical measurement.
- The ToolBox meshes are CC BY-NC-ND 4.0: review licensing before publishing this build or its sources.
- Projects saved with the previous bundled reference are upgraded on launch: a dated copy of project.json is kept, hardware mapping, signs, enabled axes and scene are preserved, offsets return to the new nominal HOME.
- No firmware, motion-planning or controller changes.

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

## Locale — 2.0.1 build 33, 29 ottobre 2026

- Primo piano MoveJ condiviso **solo virtuale** per angoli, Studio, pose e programmi;
  riusa velocità individuali, accelerazione e budget dei gruppi simultanei.
- Traccia TCP, tempo stimato, picchi, ritorno opzionale, cursore, riproduzione/arresto.
  Rifiuto dei piani scaduti e dei limiti/interferenze rilevabili lungo i campioni.
- Guida completa IT/EN: 30 capitoli per lingua, ricerca, indice, navigazione e
  esportazione Markdown offline. Descrive anche i limiti reali delle integrazioni.
- Nessuna modifica a firmware, modello approvato o semantica dei percorsi insegnati;
  nessuna pubblicazione o prova fisica. L’esecuzione comune resta da completare.

## Locale — 2.0.1 build 39, 29 ottobre 2026

- Revisione delle build 34–38 di Claude, conservando MoveJ, MoveL, IK/jog e collisioni.
- MoveL rifiuta anche il tratto minimo se supera la tolleranza dopo arrotondamento;
  controllo incluso sul punto iniziale e passo di verifica sempre entro 0,25°.
- Validazione: blocchi pinza nell’ordine effettivo, programmi di sola pinza e secondo
  ciclo di Ripeti con lo stato finale della pinza. Nessun cambio ai percorsi insegnati.
- MoveJ monouso anche senza spostamenti; stato completato preservato nei piani istantanei.
- Guida IT/EN riallineata alle funzioni correnti e ai limiti delle verifiche campionate.
- Nessun firmware, geometria approvata o parametro hardware modificato; nessuna prova fisica.

## Locale — 2.0.1 build 40, 29 ottobre 2026

- Vista 3D: due dita sul trackpad ruotano su entrambi gli assi, Maiusc + due dita trasla la camera, pizzico e rotella regolano lo zoom. Arresto senza inerzia e aggiornamenti senza animazioni accodate.
- Normali smussate sulle sole mesh verdi con soglia di spigolo di 45°: curve levigate, bordi netti conservati; vertici, triangoli, URDF e geometria originali invariati.
- Sagome a filo nascoste quando coincidono col modello solido, evitando triangoli sovrapposti; restano visibili per pose diverse.
- Guida IT/EN e suggerimento sotto la vista aggiornati. Test nativi dedicati a camera e integrità delle otto mesh verdi. Nessun cambiamento al controllo del robot o al firmware.

## Locale — 2.0.1 build43, 29 ottobre2026

- Client Python standard library e API loopback per programmi, piano completo, rami, stato, passo passo e STOP sul motore Studio condiviso. Permessi spenti a ogni avvio; Anteprima autorizzabile dall’app e ogni esecuzione reale subordinata a conferma nativa monouso.
- Lease dello script e STOP alla perdita del client; risultato finale associato al piano, conservato anche dopo una nuova pianificazione GUI.
- Istruzione uscita digitale, definizioni in Diagnostica, simulazione locale e protocollo adattatore con conferma correlata, timeout, proprietà della sessione e rifiuto di ACK dopo STOP.
- Ingressi con origine esplicita, freschezza e heartbeat; vecchio endpoint sensori senza sessione trattato come simulato. Anche le attese legacy passano dalla stessa verifica del dato.
- Esempi di presa/deposito e ingresso simulato, contratto documentato e guida IT/EN capitolo24 aggiornata. Nessun firmware, modello o pubblicazione modificati.

- Correzioni emerse nelle verifiche: revisioni del workspace firmware create con prenotazione atomica univoca (nessuna collisione fra salvataggi ravvicinati); identificativi dei sensori conservati letteralmente anche nell’interfaccia inglese. Nessuna modifica ai sorgenti Arduino inclusi.
