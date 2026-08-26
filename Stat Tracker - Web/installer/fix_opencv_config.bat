@echo off
REM Fixes a specific, now fully-understood packaging issue: `flet build`
REM compiles every .py file to .pyc and removes the original .py source
REM from the built app. That's normally invisible, but OpenCV's own
REM loader (cv2/__init__.py) doesn't use Python's regular import system
REM for its two small config files — it manually checks for the literal
REM "config.py" / "config-3.py" filenames on disk with os.path.exists()
REM and exec()'s their raw source text. Without the actual .py files
REM physically present, cv2 raises:
REM   "OpenCV loader: missing configuration file: ['config.py'].
REM    Check OpenCV installation."
REM — even though cv2.pyd itself (the real compiled OpenCV binary) is
REM completely intact. This restores just those two tiny text files
REM (a few lines each, not the actual OpenCV binaries) from your local
REM working opencv-python install into the build output.
REM
REM Run this once, every time, right after `flet build windows` and
REM before testing the app or building the installer:
REM
REM   flet clean
REM   flet build windows --project "Stat Tracker"
REM   installer\fix_opencv_config.bat
REM   "path\to\ISCC.exe" installer\StatTracker.iss

setlocal

for /f "delims=" %%i in ('python -c "import cv2, os; print(os.path.dirname(cv2.__file__))" 2^>nul') do set CV2_DIR=%%i

if "%CV2_DIR%"=="" (
    echo Could not locate a local opencv-python install. Run "pip install opencv-python" first,
    echo then re-run this script.
    exit /b 1
)

if not exist "%CV2_DIR%\config.py" (
    echo %CV2_DIR%\config.py not found - your local opencv-python install looks incomplete.
    exit /b 1
)

if not exist "build\windows\site-packages\cv2" (
    echo build\windows\site-packages\cv2 not found - run "flet build windows" first,
    echo from the project root, before running this script.
    exit /b 1
)

copy /Y "%CV2_DIR%\config.py" "build\windows\site-packages\cv2\config.py" >nul
copy /Y "%CV2_DIR%\config-3.py" "build\windows\site-packages\cv2\config-3.py" >nul

echo Done — copied config.py and config-3.py into build\windows\site-packages\cv2\
echo The camera should now actually work in the built app.

endlocal
