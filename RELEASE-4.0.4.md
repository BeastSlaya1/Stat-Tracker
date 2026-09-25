# Stat Tracker 4.0.4

Update **both** installed apps:

- Android: `Stat-Tracker-Android-4.0.4.apk`
- Windows: `Stat-Tracker-Windows-4.0.4-Setup.exe`

Install these as updates over the existing apps. There is no need to remove
the existing app or clear its stored data.

## Rotate the camera view

Press **Rotate view** in Camera Mode or beside the match video controls.
It is also available in full-screen logging and on browser video. Each tap
turns the displayed video 90 degrees clockwise; four taps restore the original
view. The stream stays connected. Each device controls its own view.

Use **Mirror view** to flip the displayed video left-to-right; press it again
to restore the normal view. It works alongside rotation in both modes and
on the browser camera page, without interrupting the stream.

## Android camera to installed Windows app

1. Put both devices on the same Wi-Fi.
2. On Android, choose **Camera Mode → Start Streaming**.
3. On Windows, choose **Auto-Discover Cameras** and select the Android device.
4. Approve the matching number on Android.

This update removes the extra Android preview rotation, adjusts outgoing
frames for device orientation, and fixes the Windows receiver waiting for
more data before displaying small frames.

## iPhone/iPad browser camera

Open this page on both devices:

https://stat-tracker-sync.joshuapieterse1.workers.dev/camera

1. Sign in using your staff account on each device.
2. On the phone/tablet, choose **Send this camera** and allow camera access.
3. On the other device, choose **Receive a camera** and enter the displayed code.
4. Approve the receiving device on the phone/tablet.

On Windows, the app's **Receive iPhone / browser camera** button opens this
page. Browser video appears in that separate page; keep the match workspace
beside it. Use Safari on iPhone/iPad, keep the camera page visible, and leave
the device unlocked. Use **Stop connection** when finished.

Use the same Wi-Fi for the most reliable connection. Restricted school/guest
networks and some mobile connections may need a video relay, which has not
been configured. Audio is not captured. No native Apple installer is included.

## Publish the website and downloads

The browser camera service is already live. The main website and download
page changes still need the GitHub update:

1. Extract `Stat-Tracker-4.0.4-Source.zip`.
2. Copy its contents into your Stat-Tracker repository, preserving all folders
   including `.github`, `packages`, `assets`, `scripts`, `server`, and
   `web-downloads`. Commit and push the changes using GitHub Desktop or Git.
   The ZIP itself is not the website source upload.
3. Let the **Deploy web app** workflow finish. If Edge shows the old page,
   press **Ctrl+Shift+R**. Do not clear stored site data to refresh the layout.
4. Create a GitHub release with tag **v4.0.4**, attach the APK and EXE above
   with their exact filenames, and publish it. The downloads page checks
   that release before enabling the download buttons.

Source: https://github.com/BeastSlaya1/Stat-Tracker

## Included and verified

- Compact header and at least 60% of the app content height for the workspace.
- Saved-name startup fix; no download button inside the installed apps.
- Hidden database-address field; existing staff sign-in and synchronization.
- Blue downloads page, matching logo/icons, and responsive sizing.
- Android camera orientation and Windows stream-reader fixes.
- Rotate-view controls without restarting capture or pairing.
- Browser camera pairing with staff sign-in and sender approval.

Automated checks covered camera conversion/lifecycle, paired HTTP delivery,
database access, app layout/state, and real browser-to-browser WebRTC video
with a simulated camera. Physical Android and Apple camera hardware still
needs your device check. The Android APK uses the existing development
signing certificate; the Windows installer is not code-signed.
