@echo off
REM Thin wrapper for a3game-unity run
setlocal
set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..\..\..
set PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%
set PYTHON=%A3GAME_PYTHON%
if "%PYTHON%"=="" set PYTHON=python
"%PYTHON%" -m engine_adapters.unity3d.cli run %*
