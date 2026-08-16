@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "A3GAME_REPO_ROOT=%%~fI"
set "PYTHONPATH=%A3GAME_REPO_ROOT%;%PYTHONPATH%"
if defined A3GAME_PYTHON (
  "%A3GAME_PYTHON%" -m engine_adapters.ue5.cli create-project %*
) else (
  python -m engine_adapters.ue5.cli create-project %*
)
exit /b %ERRORLEVEL%
