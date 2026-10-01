@echo off
rem BananaTrade control panel - double-click to open
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Khong tim thay .venv. Hay cai dat moi truong truoc.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m bananatrade.gui
