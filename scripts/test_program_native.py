#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Native DTO/structure regressions from actual app source; macOS + Xcode CLI tools."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'native/MoveJPreviewView.swift').read_text()
dto=s[s.index('struct ProgramCallFrame:'):s.index('struct MoveLInfo:')]
s=(root/'native/ProgramView.swift').read_text()
structure=s[s.index('enum ProgramStructure'):s.index('struct ProgramProblem')]
boundary=s[s.index(' func boundaries('):s.index(' func step(',s.index(' func boundaries('))]
core='import Foundation\n'+dto+'\nstruct ProgramBlock {let kind:String}\nstruct MoveJPlan {let stages:[MoveJStage];let duration:Double}\n'+structure+boundary
with tempfile.TemporaryDirectory(prefix='robot-console-native-') as folder:
    p=Path(folder);(p/'Core.swift').write_text(core)
    subprocess.run(['xcrun','swiftc','-parse-as-library','-module-cache-path',str(p/'cache'),'-o',str(p/'Tests'),str(p/'Core.swift'),str(root/'native/tests/ProgramFunctionsTests.swift')],check=True)
    subprocess.run([str(p/'Tests')],check=True)

with tempfile.TemporaryDirectory(prefix='robot-console-input-') as folder:
    p=Path(folder)
    subprocess.run(['xcrun','swiftc','-parse-as-library','-module-cache-path',str(p/'cache'),'-o',str(p/'InputTests'),str(root/'native/InputDraft.swift'),str(root/'native/tests/InputDraftTests.swift')],check=True)
    subprocess.run([str(p/'InputTests')],check=True)
