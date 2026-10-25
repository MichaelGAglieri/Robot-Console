# Third-party components

Original application and firmware sources in this release: GPL-3.0-only, Michael Giuseppe Aglieri.

| Component | Author/source | License and distribution |
| --- | --- | --- |
| AccelStepper 1.64 | [Mike McCauley / AirSpayce](https://www.airspayce.com/mikem/arduino/AccelStepper/) | GPLv3 open-source option; fetched through Arduino CLI, source not bundled in this application archive |
| Arduino AVR core 1.8.8 and toolchain | [Arduino](https://github.com/arduino/ArduinoCore-avr/tree/1.8.8) | External build dependencies with their own LGPL/GPL notices; installed separately |
| Arduino CLI / IDE | Arduino | External tool; no executable redistributed in this source/app package |
| Python, Swift/Apple frameworks | Python contributors / Apple | Runtime and platform dependencies; not bundled or relicensed here |
| Ollama and selected models | Respective upstream authors | Installed separately; model licenses vary and no model weights are bundled |
| Robot Console icon | Michael Giuseppe Aglieri, supplied AI-generated illustration | Project visual asset; identified as an illustration, not a photo of a verified robot |

The firmware subclass and motion configuration build on AccelStepper; they are not an independently authored replacement for that library. Keep the library's notices in any compiled firmware distribution. If distributing compiled firmware separately, also provide its exact corresponding sources and build dependencies as required by the applicable licenses.

No ToolBox Robotics CAD, Cyberbotics model, model weights, Arduino CLI executable or user conversation history is embedded in the application. Its mechanical hardware reference links back to the original design sources through DOC-Robotics.
