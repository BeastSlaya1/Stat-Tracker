# Stat Tracker 4.0.14 (build 15)

## Profile and authenticator setup

Profile and security opens immediately with a loading indicator. Connection failures and expired sign-ins appear inside the screen, with a Retry button for loading failures. Closing the screen prevents a late response from reopening it.

Email/phone profiles and authenticator 2FA are now deployed to the existing Cloudflare server. The account-security migration was applied on 3 October 2026, the encryption key was configured, and Worker version 13766401-fa20-4da0-8c10-0c47f31187d3 was deployed. Existing accounts and matches were preserved. Live health and unauthenticated-access checks passed.

To enable 2FA, open Account and database > Profile and security, enter your current password, and choose Set up authenticator. In Microsoft Authenticator choose Add account > Other account; in Google Authenticator choose Add > Scan a QR code. Other apps supporting standard six-digit, 30-second TOTP codes also work. Scan the QR code, enter the generated code in Stat Tracker, then confirm. If using the same phone, manually add the displayed setup key as a time-based account instead. Save the recovery codes before closing the screen. Update all devices you use before enabling 2FA; older clients without an authenticator-code field cannot sign in to a 2FA-enabled account. QR codes are generated locally and are never sent to an external QR service.

## Tablet and camera connections

The stream discovery button and instructions now say Scan for streams. Connect phone or tablet opens a stream picker. Selecting a Windows Virtual Camera device, including Beast's Tab S5e, opens this connection screen instead of silently choosing a local camera.

For a Stat Tracker connection, sign in on both devices. On the tablet, choose Camera Mode and Start Streaming, and keep that screen open. On the receiving computer, use Inputter Mode, choose the tablet option or Connect phone or tablet, and select its stream. Approve the connection on the tablet. Use the same Wi-Fi network; networks that require a relay may not connect with the current transport.

If Windows already supplies the tablet as a connected camera, choose Use Windows connected camera in the picker. Unlock the tablet and allow camera access when requested. Ordinary local-camera selections now start capture immediately. A preview that produces no frames reports a visible error after 20 seconds. Selection still verifies the actual device ID and rejects fallback to a different camera.

## Validation and installation

63 Python app tests, 37 server tests and 22 Flutter camera tests passed. Tests cover immediate profile loading, retry, closing during loading, local QR generation and clearing, virtual-tablet routing and selecting a specific remote stream. Windows bundled profile, QR and OpenCV imports passed; the isolated app startup reported no application errors. Physical tablet/camera testing remains necessary.

Install the Windows setup over the existing installation. Install the Android APK over version 4.0.12 or 4.0.13 without uninstalling. Android retains app ID com.flet.stat_tracker and uses version code 15. Keep the original Android signing key outside the source archive.

## Build notes

Use Flet 0.86.5, Flutter 3.44.8, version 4.0.14 and build number 15. qrcode 8.2 is now a shared Python dependency. Windows requires the native Flutter camera update as well as the Python modules. Build paths should be short. For Android on this Windows host, use the system-trusted certificates via PIP_CERT and UTF-8 Python console output. The local camera extension can be prebuilt as a wheel for cross-platform packaging; keep build logs excluded from app assets. Never replace the live MFA_ENCRYPTION_KEY after users enroll.

Final package checks: Windows installer compilation completed successfully and reports version 4.0.14. Android APK signature and archive integrity verification passed; its signing certificate matches the previous releases. The final APK includes the tested profile/camera code and local QR generation dependency, with no build logs or signing files in its app archive.
