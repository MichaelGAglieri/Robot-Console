@echo off
rem Robot Console for Windows: creates .venv on first start, then opens the app.
rem Extra options are passed through, e.g.  run.bat --no-hardware
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creazione ambiente Python in .venv...
  py -3 -m venv .venv || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" robot_console.py %*
