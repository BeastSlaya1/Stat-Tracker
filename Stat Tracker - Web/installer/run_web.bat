@echo off
REM Double-click this file to run the built web app locally.
REM
REM Why this exists: opening index.html directly (double-clicking it, or
REM file:// in the address bar) doesn't work for a Flutter web app —
REM browsers block it from loading its own JS/wasm assets that way, as a
REM security restriction, not a bug. A real web app needs to be served
REM over http://, even for local testing. This script does that for you
REM with one double-click instead of typing commands.
REM
REM Place this file directly inside the "web" folder — the one that
REM contains index.html — then just double-click it.

cd /d "%~dp0"

if not exist "index.html" (
    echo index.html not found in this folder.
    echo Make sure this script is placed directly inside the "web" folder
    echo that flet build web produced ^(the one containing index.html^),
    echo not somewhere else.
    pause
    exit /b 1
)

REM Prefer the "py" launcher — the standard, official way to invoke
REM Python on Windows regardless of what else is installed. Falls back to
REM "python" only if "py" genuinely isn't available.
REM
REM Checking "py.exe"/"python.exe" specifically (not bare "py"/"python")
REM matters here: Windows' command resolution can match a bare name
REM against ANY extension listed in PATHEXT (.EXE, .BAT, .CMD, .VBS, .JS,
REM etc, in that order) — if something on this system left a stray
REM "python.js" on PATH (a leftover from a since-uninstalled tool, for
REM example), a bare "where python" can find and return THAT instead of
REM a real Python install, and invoking it hands off to Windows Script
REM Host as JScript instead of running Python at all — producing exactly
REM a cryptic "JavaScript compilation error" instead of anything
REM Python-related. Being explicit about ".exe" avoids this entirely.
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

echo Starting local server for Stat Tracker using: %PYCMD%
start "" http://localhost:8000
%PYCMD% -m http.server 8000
