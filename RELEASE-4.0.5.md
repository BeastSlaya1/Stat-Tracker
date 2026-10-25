# Stat Tracker 4.0.5

## Install and connect

1. Install Stat-Tracker-Android-4.0.5.apk on Android and Stat-Tracker-Windows-4.0.5-Setup.exe on Windows. Close the old Windows app first. Keep existing app data; do not uninstall Android just to update it.
2. Sign in through Database on both devices using your staff account.
3. On the sending device, open Device Mode → Camera Mode → Start Streaming. Allow camera access.
4. On the receiving device, open Live Match Video → Scan for cameras. Choose the sending device.
5. On the sender, select Approve receiver. The video appears inside Live Match Video.

Rotate view and Mirror view adjust the display on each device independently. Keep Camera Mode open and the sender unlocked. Use the same Wi-Fi where possible; restricted school, guest or mobile networks may need a relay, which is not configured.

## Update the website through GitHub

The camera service is already deployed. The main website still needs this source update.

1. Extract Stat-Tracker-4.0.5-Source.zip.
2. Update the repository with its contents, preserving folders such as packages, server, scripts, web-downloads and .github. main.py and pyproject.toml belong at the repository root.
3. Wait for the Deploy web build to GitHub Pages workflow to finish successfully.
4. Create a GitHub release with tag v4.0.5. Attach the two installer files with their original names. The downloads page checks that release before enabling downloads.
5. Refresh the website on both devices. In Edge use Ctrl+Shift+R if the old interface remains.

The separate Camera Link page and Receive iPhone / browser camera button are removed. Its old address redirects to the main website. iPhone/iPad users can use the updated website in Safari, with Camera Mode for sending and Scan for cameras for receiving. No separate camera sign-in page is needed.

## Validation

- Android and Windows builds completed successfully.
- 31 Python app checks and 10 server checks passed.
- Two browser sessions displayed actual remote video through the embedded control using the deployed service; discovery, approval and stopping were verified.
- The downloads page was checked at widths from 320 to 1920 pixels.
- Physical Android-to-Windows and iPhone/iPad camera tests remain necessary. Native Apple installation still requires signing; no installable iOS file is included.
- The Windows installer is unsigned, and Android retains the existing signing certificate.

The service stores temporary camera connection details, not the video itself. Your existing matches, staff accounts and shared reference data are retained.
