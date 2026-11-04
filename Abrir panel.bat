@echo off
rem Double-click to open the panel. Closing this window stops it.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m panel.launcher
) else (
  where python >nul 2>nul
  if errorlevel 1 goto nopython
  python -m panel.launcher
)
if errorlevel 1 pause
exit /b
:nopython
echo Hace falta Python 3.9 o superior para abrir el panel.
echo Se descarga gratis de https://www.python.org/downloads/
echo Al instalarlo, marcar la casilla "Add python.exe to PATH".
pause
