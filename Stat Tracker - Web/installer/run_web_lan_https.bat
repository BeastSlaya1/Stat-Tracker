@echo off
REM Serves the built web app over HTTPS to this PC and to other devices
REM on the same WiFi/LAN — including phones (iOS/Android). Plain
REM run_web_lan.bat (http://) works fine for viewing the app on a phone,
REM but iOS Safari and Android Chrome both block camera access
REM (getUserMedia) on any page that isn't https:// or http://localhost —
REM so the web build's "This Device's Camera" option needs this HTTPS
REM version specifically to work from a phone.
REM
REM Requires the 'cryptography' Python package once, to generate a local
REM certificate: py -m pip install cryptography
REM (serve_web_https.py will tell you this too if it's missing.)
REM
REM Place this file (and serve_web_https.py) directly inside the "web"
REM folder — the one that contains index.html — then just double-click it.

cd /d "%~dp0"

if not exist "index.html" (
    echo index.html not found in this folder.
    echo Place this script directly inside the "web" folder that
    echo flet build web produced ^(the one containing index.html^).
    pause
    exit /b 1
)

if not exist "serve_web_https.py" (
    echo serve_web_https.py not found next to this script.
    echo Copy it into the same "web" folder as this .bat file.
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
echo Starting HTTPS server using: %PYCMD%
echo   On this computer:             https://localhost:8443
echo   On phones/other devices (same WiFi): https://%LOCAL_IP%:8443
echo.
echo Share that second address with anyone opening this on a phone.
echo Expect a "connection is not private" warning the first time on each
echo device — that's expected for a self-signed certificate, tap
echo Advanced / Details then "proceed anyway" once.
echo.
echo Press Ctrl+C to stop the server when you're done.
echo.

start "" https://localhost:8443
%PYCMD% serve_web_https.py
