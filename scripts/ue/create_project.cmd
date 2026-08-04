@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..\..") do set "AAAGAME_REPO_ROOT=%%~fI"
set "PYTHONPATH=%AAAGAME_REPO_ROOT%;%PYTHONPATH%"
if defined AAAGAME_PYTHON (
  "%AAAGAME_PYTHON%" -m engine_adapters.ue5.cli create-project %*
) else (
  python -m engine_adapters.ue5.cli create-project %*
)
exit /b %ERRORLEVEL%
