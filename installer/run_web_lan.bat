@echo off
REM Same as run_web.bat, but also reachable by other devices on the same
REM WiFi/network — not just this computer. Still completely free, no
REM accounts, no internet connection required; it's your own machine
REM acting as the server for anyone else on the same local network.

cd /d "%~dp0"

if not exist "index.html" (
    echo index.html not found in this folder.
    echo Place this script directly inside the "web" folder that
    echo flet build web produced ^(the one containing index.html^).
    pause
    exit /b 1
)

echo Finding this computer's local network address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do set LOCAL_IP=%%a
set LOCAL_IP=%LOCAL_IP: =%

REM See run_web.bat for why ".exe" is checked explicitly rather than a
REM bare "py"/"python" — avoids PATHEXT matching a stray non-Python file
REM (e.g. a leftover "python.js") and handing off to Windows Script Host
REM instead of actually running Python.
where py.exe >nul 2>nul
if %errorlevel%==0 (
    set PYCMD=py.exe
) else (
    where python.exe >nul 2>nul
    if %errorlevel%==0 (
        set PYCMD=python.exe
    ) else (
        echo Could not find a real Python installation on this system
        echo ^(checked for py.exe and python.exe specifically^). Install
        echo Python from python.org, making sure to check "Add python.exe
        echo to PATH" during install, then try again.
        pause
        exit /b 1
    )
)

echo.
echo Starting server using: %PYCMD%
echo   On this computer:      http://localhost:8000
echo   On other devices (same WiFi): http://%LOCAL_IP%:8000
echo.
echo Share that second address with anyone else who needs to open it.
echo Press Ctrl+C to stop the server when you're done.
echo.

start "" http://localhost:8000
%PYCMD% -m http.server 8000
