# Stat Tracker 4.0.28

## Included changes

- Basketball possession shows the current team with a prominent ball indicator and possession buttons.
- Opponent-related actions move into Opposition, with red action buttons, amber penalties and a separate sequence. This applies to sports with opponent actions.
- Portrait fullscreen keeps the score, clock, possession and video above a separately scrolling area containing actions, incompletes and sequences.
- Installed apps can host or join a shared match over a local Wi-Fi network or hotspot. The host controls the camera, possession and timer; approved devices log stats. No internet is required for this session.
- iPhone/iPad source configuration, unsigned GitHub build workflow and IOS-SETUP.md are included. An iOS build and physical-device tests are still required.

## GitHub upload

1. Upload the source ZIP contents into the repository, including the hidden .github folder.
2. Run your Deploy web build workflow to update the website.
3. Create release v4.0.28 and attach the Windows installer and Android APK (Android build 29).
4. For iOS preparation, follow IOS-SETUP.md. The unsigned archive workflow does not publish to TestFlight or the App Store.

No new Cloudflare migration is needed for local match sharing. If the earlier Owner/hidden-account server update has not been deployed, follow UPLOAD-4.0.26.md separately.

## Sharing a match without internet

1. Install this version on participating Windows/Android devices. Sign in beforehand; offline sharing does not provide offline account registration or first-time sign-in.
2. Connect all devices to the same trusted Wi-Fi network or hotspot. On Windows, allow the app through the firewall on private networks if prompted. Networks with device/client isolation will prevent sharing.
3. On the host, open the match, select a camera attached to that device, and choose Shared match > Host this match.
4. On each joining device, choose Shared match and enter the host address, join code and a device name. Request to join.
5. The host opens Shared match, refreshes the waiting-device list and approves the invited device. The guest then presses Connect after approval.
6. Turn on the host camera. Guests receive the video and match clock and can log stats. Each guest can mark or convert its own latest action even when another device has logged an intervening action.
7. Keep the host app open and the device awake. If a connection drops, keep the guest match open so pending inputs can retry. Wait for pending inputs before ending the session. The host retains the combined match and resumes cloud sync after sharing ends.

Use the installed apps for local hosting/joining; the website does not support this mode. Local match and camera connection messages use HTTP, so use a trusted network. Camera video uses WebRTC. The host approves each device; hidden and normal sessions remain separate. A shared session is limited to eight joined devices, and camera performance depends on the host and network. This mode does not relay an already-remote camera source.

## Validation and limits

135 Python tests passed, including concurrent inputs, duplicate retries, device approval, per-device undo/conversion, host clock controls, Opposition sequences and portrait layout structure. Windows, Android and web builds completed. Browser checks passed for retained scrolling, fixed portrait camera/header, and Opposition scoring. Real Windows-to-Android camera sharing and iPhone/iPad hardware tests remain pending; do a practice match before relying on shared mode during a fixture.

