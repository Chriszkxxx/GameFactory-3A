@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPOSITORY_ROOT=%%~fI"
set "PYTHONPATH=%REPOSITORY_ROOT%;%PYTHONPATH%"

if defined A3GAME_PYTHON (
  set "PYTHON_BIN=%A3GAME_PYTHON%"
) else (
  set "PYTHON_BIN=python"
)

where node >nul 2>nul
if errorlevel 1 (
  echo node was not found on PATH; install Node 20 or newer first. 1>&2
  exit /b 127
)

"%PYTHON_BIN%" -m engine_adapters.three_js.cli run %*
exit /b %ERRORLEVEL%
