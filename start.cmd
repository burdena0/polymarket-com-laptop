@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run the installation commands in docs\LAPTOP.md first.
  exit /b 1
)
if exist "data\paper-v1\STOP" del "data\paper-v1\STOP"
".venv\Scripts\python.exe" -m weather_laptop.app
pause
