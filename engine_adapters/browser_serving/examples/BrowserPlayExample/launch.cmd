@echo off
setlocal EnableExtensions

set "A3GAME_BROWSER_PLAY_DIR=%~dp0"
for %%I in ("%~dp0..\..\..\..") do set "A3GAMEFORGE_ROOT=%%~fI"

echo Browser Play: http://127.0.0.1:7870/game/
echo The selected Engine backend must already be configured by the Pipeline.
pushd "%A3GAMEFORGE_ROOT%"
python -m engine_adapters.browser_serving gateway
set "A3GAME_RESULT=%ERRORLEVEL%"
popd
exit /b %A3GAME_RESULT%
