@echo off
cd /d "%~dp0"
if not exist "data\paper-v1" mkdir "data\paper-v1"
type nul > "data\paper-v1\STOP"
echo Stops the observer and simulator after the current bounded requests.
