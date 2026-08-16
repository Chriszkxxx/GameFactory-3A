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

"%PYTHON_BIN%" -m engine_adapters.three_js.cli import-asset %*
exit /b %ERRORLEVEL%
