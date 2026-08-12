@echo off
REM Unity-native generated-game wrapper.
setlocal
set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..\..
set PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%
set PYTHON=%A3GAME_PYTHON%
if "%PYTHON%"=="" set PYTHON=python
"%PYTHON%" -m engine_adapters.unity3d.cli generate-game %*
