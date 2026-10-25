# Stat Tracker 4.0.10 — clearer camera video

Camera capture now prefers 1920 × 1080 at 30 frames per second, instead of 1280 × 720 at 20 fps. The sender allows up to 8 Mbps, avoids deliberate resolution scaling, and requests preservation of detail on native backends that support that setting. The stream can still adapt to device and network limits; Full HD is a preference, not a guarantee on every camera or connection. Unsupported optional encoder settings do not prevent streaming.

The previous camera startup and fullscreen fixes remain included.

## Install

- Install **Stat-Tracker-Android-4.0.10.apk** over the existing Android app.
- Close the Windows app and install **Stat-Tracker-Windows-4.0.10-Setup.exe**.
- Update both sending and receiving devices, then stop and restart the camera stream. The sending device must have the update for higher-quality capture.

For the website, extract **Stat-Tracker-4.0.10-Source.zip** and upload its contents to GitHub, preserving folders including `.github`, `packages`, `scripts`, `server` and `web-downloads`. Wait for the web deployment workflow to succeed, then reopen the site; use Ctrl+Shift+R in Edge if needed. The website is not updated until deployment completes.

For the download buttons, publish a GitHub release tagged **v4.0.10**, with the Android APK and Windows installer attached using their exact filenames above.

No database migration or server deployment is needed. Existing matches and account permissions remain unchanged. Windows is unsigned; Android uses the existing signing certificate.

Higher resolution cannot remove noise caused by poor lighting or a camera sensor. Test with good lighting and a strong Wi-Fi connection. Physical camera quality still needs checking on your devices.

## Verification

Four Dart checks passed for camera lifecycle, capture preferences, encoding identity and optional-setting fallback. An actual embedded browser sender/receiver test with a simulated camera passed sign-in, discovery, approval, 1920 × 1080 remote rendering and stop cleanup. The test camera supplied 20 fps; 30 fps remains a preference for cameras that support it.
