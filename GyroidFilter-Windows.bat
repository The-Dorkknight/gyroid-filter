@echo off
rem Gyroid Filter launcher (Windows). Double-click it.
rem Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
rem Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Gyroid Filter needs Python 3.8 or newer, and it was not found.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and run this file again.
  pause
  exit /b 1
)
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
%PY% -m gyroid_filter %*
if errorlevel 1 (
  echo Gyroid Filter stopped with an error.
  pause
)
