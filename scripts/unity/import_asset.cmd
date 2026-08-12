@echo off
REM Thin wrapper for the public a3game-unity asset commands.
REM Dispatch import-batch before adding the default import-asset command.
setlocal
set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..\..
set PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%
set PYTHON=%A3GAME_PYTHON%
if "%PYTHON%"=="" set PYTHON=python
if /I "%~1"=="import-batch" (
  shift
  "%PYTHON%" -m engine_adapters.unity3d.cli import-batch %*
  exit /B %ERRORLEVEL%
)
"%PYTHON%" -m engine_adapters.unity3d.cli import-asset %*
