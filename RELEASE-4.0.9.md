# Stat Tracker 4.0.9 — camera startup and fullscreen

This update fixes a screen-update loop: the camera sent a Starting status, the app rebuilt the screen, and the camera restarted. Status and pairing changes now update in place. The video control also keeps its active camera and connection when moved between normal and fullscreen layouts.

## Install and publish

1. Close the Windows app and install **Stat-Tracker-Windows-4.0.9-Setup.exe**. On Android, install **Stat-Tracker-Android-4.0.9.apk** over the existing app.
2. For the website, extract **Stat-Tracker-4.0.9-Source.zip** and upload its contents to the GitHub repository, keeping the folders including `.github`, `packages`, `scripts`, `server` and `web-downloads`. Wait for the web deployment workflow to succeed, then close old app tabs and reopen the site. In Edge, press Ctrl+Shift+R if the old version remains.
3. To update the public download buttons, create a GitHub release tagged **v4.0.9** and attach the Android APK and Windows installer using their exact filenames above.

The live website does not change until the GitHub deployment completes. This fix needs no database migration or server deployment. Existing matches, account permissions and saved-game management are retained. The Windows installer is unsigned; Android uses the existing signing certificate.

## Check on your devices

Allow camera access, start Camera Mode and keep the page visible. It should reach the preview or the ready-to-pair status without repeatedly reloading. Pair your devices, then check entering and leaving fullscreen while the video is playing. Rotate and Mirror remain available.

The automated checks cover camera startup, screen resizing, rotation, mirroring, fullscreen transitions, stopping camera tracks and explicitly restarting capture. Browser camera checks use a simulated camera. Physical Android and Windows camera drivers still need checking on your devices.
