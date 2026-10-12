# Stat Tracker 4.0.27

Inputs now update the current view while keeping the scrolling panels mounted. Logging a stat, marking it incomplete, using a time control, or refreshing synced data no longer rebuilds the entire workspace and returns it to the top. Applies to the normal logger, fullscreen side panels, camera mode and coach views. Changing matches or switching screens still opens the selected screen normally.

## Upload through GitHub
Upload the source ZIP contents to your repository, including hidden .github files. Run the existing Deploy web build workflow for the website. Publish the Windows installer and Android APK as release v4.0.27 (Android build 28).

This fix does not change the server or database. If you have not deployed 4.0.26's Owner/hidden-account update yet, follow UPLOAD-4.0.26.md and run the server workflow as well.

## Checks
121 app tests passed, including retained scroll panels, updated callbacks and fullscreen camera/clock references. Browser checks cover logging and incomplete/time actions without jumping back to the top. Windows and Android packages built successfully; Android interaction has not been tested on a physical device.
