# iPhone and iPad setup

The source is prepared to include the same possession, Opposition, portrait fullscreen and local shared-match code for iOS. No Apple Developer account is required to prepare the source or build an unsigned archive. A signed installation is still needed for an actual iPhone/iPad; this Windows workspace cannot build or sign iOS apps.

1. Upload the source, including .github/workflows/build-ios.yml, to GitHub.
2. Open Actions > Build iPhone and iPad archive > Run workflow. Choose a bundle ID you intend to register, such as your own organisation's reverse-domain ID.
3. Download the unsigned Xcode archive artifact. It is a build artifact, not an installable iPhone download.
4. When ready to distribute, enrol in the Apple Developer Program, register that bundle ID, create an Apple Distribution certificate and an App Store provisioning profile, and create the app in App Store Connect.
5. Open the archive in Xcode on a Mac, configure signing for your team, then distribute through TestFlight. Do not commit certificates, private keys or provisioning profiles to the repository.

On iPhone/iPad, allow Camera and Local Network access when prompted. All participating devices need the same Wi-Fi network or hotspot. Keep the host app open and the device awake; background hosting is not supported. This is local-network sharing, not remote internet conferencing. The camera source is the host's on-device or connected camera. Browser/Safari hosting and joining are not supported.

For offline sharing, target iOS/iPadOS 17 or later; the private-IP exceptions used here are supported from version 17. Local networking is scoped through NSAllowsLocalNetworking and private IPv4 ATS exceptions. Cloud account access continues to require HTTPS. Use a trusted Wi-Fi network or hotspot; local match/signalling traffic uses HTTP, with a join code and host approval. Video uses WebRTC.

The unsigned workflow has been prepared but has not been run on a macOS runner or tested on a physical iPhone/iPad in this workspace.

References: [Flet iOS packaging](https://flet.dev/docs/publish/ios/), [Apple local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy), [Apple ATS local networking](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking).

## First-device checks before release

- Test camera permission granted and denied, and Local Network permission granted and denied.
- Host from iPhone/iPad, then join from Windows and Android; also join an Android or Windows host from iOS.
- Disconnect internet while keeping Wi-Fi connected. Confirm that each device receives the host video, score, possession and clock.
- Log different stats simultaneously, disconnect and reconnect one guest, and check that retries do not duplicate events.
- Rotate between portrait and landscape and check fullscreen scrolling, fixed video and video-only zoom.
- Keep the host in the foreground. Backgrounding or locking it can interrupt the local server and camera.

These checks are still pending on physical Apple hardware. The wider shared-match changes are under validation; this guide is not a claim that an iOS build has passed.
