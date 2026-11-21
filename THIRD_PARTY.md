# Third-party components

Original application and firmware sources in this release: GPL-3.0-only, Michael Giuseppe Aglieri.

| Component | Author/source | License and distribution |
| --- | --- | --- |
| AccelStepper 1.64 | [Mike McCauley / AirSpayce](https://www.airspayce.com/mikem/arduino/AccelStepper/) | GPLv3 open-source option; fetched through Arduino CLI, source not bundled in this application archive |
| Arduino AVR core 1.8.8 and toolchain | [Arduino](https://github.com/arduino/ArduinoCore-avr/tree/1.8.8) | External build dependencies with their own LGPL/GPL notices; installed separately |
| Arduino CLI / IDE | Arduino | External tool; no executable redistributed in this source/app package |
| Python, Swift/Apple frameworks | Python contributors / Apple | Runtime and platform dependencies; not bundled or relicensed here |
| Qt 6 / PySide6 | The Qt Company and contributors | LGPL-3.0 (open-source option); installed from PyPI with `requirements.txt`; bundled unmodified in the Linux `.deb` and Windows packages (not in the macOS app) |
| NumPy, pyserial | Respective upstream authors | BSD-3-Clause; installed from PyPI, not bundled |
| OpenCV, Vosk, sounddevice (optional) | Respective upstream authors | Apache-2.0 / Apache-2.0 / MIT; optional, installed separately; Vosk models keep their own licenses |
| Ollama and selected models | Respective upstream authors | Installed separately; model licenses vary and no model weights are bundled |
| DOC five-axis model | Assembly, joints and schematic meshes by Michael Giuseppe Aglieri; mechanical design ToolBox Robotics [EB-15](https://www.thingiverse.com/thing:6488872) / [EBG-30](https://www.thingiverse.com/thing:6460300) | Bundled URDF, placement data and schematic meshes GPL-3.0-only. The ToolBox STL parts (CC BY-NC-ND 4.0) and meshes derived from them are not distributed: they are generated on the user's computer from the user's own download. See models/doc5/NOTICE.md. |
| Robot Console icon | Michael Giuseppe Aglieri, supplied AI-generated illustration | Project visual asset; identified as an illustration, not a photo of a verified robot |

The firmware subclass and motion configuration build on AccelStepper; they are not an independently authored replacement for that library. Keep the library's notices in any compiled firmware distribution. If distributing compiled firmware separately, also provide its exact corresponding sources and build dependencies as required by the applicable licenses.

No ToolBox Robotics CAD or derived mesh, model weights, Arduino CLI executable or user conversation history is embedded in the application. Its mechanical hardware reference links back to the original design sources through DOC-Robotics.
