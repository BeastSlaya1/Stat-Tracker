# Stat Tracker for iPhone and iPad — source preview

This port includes the Android/Windows camera lifecycle and pairing fixes,
iOS BGRA camera-frame conversion, local-network/camera permission descriptions,
and an unsigned cloud build workflow. It has NOT been built with Xcode, signed,
or tested on a physical iPhone/iPad. This is source, not an installable IPA.

## Build from Windows using GitHub

Upload this folder's contents to a separate GitHub repository, including the
hidden `.github/workflows/ios-build.yml` file. In Actions, select
**Build iPhone and iPad archive**, then **Run workflow**. Set your Apple bundle ID
(the default is an example). A GitHub-hosted Mac performs the build; you do not
need a local Mac. GitHub runner usage is subject to your account's limits.
The workflow runs only when requested and uploads a temporary unsigned archive.
It does not publish to TestFlight or the App Store and needs no signing secrets.

The archive cannot install on an iPhone. For distribution, enroll in the Apple
Developer Program, register the bundle ID, configure a signing certificate and
provisioning profile on the cloud Mac, then export a signed IPA and upload to
App Store Connect/TestFlight. Store signing material in GitHub Actions secrets,
never in the repository. See https://flet.dev/docs/publish/ios/ and
https://developer.apple.com/testflight/ .

## Camera connection

Allow Camera and Local Network access when prompted. Keep the app in the
foreground, with both devices on the same Wi-Fi. Start Camera Mode on iPhone or
iPad. Type the displayed stream URL into Windows and complete number matching.
The same app is intended for both iPhone and iPad.

Automatic UDP discovery is disabled on iOS because it needs Apple's restricted
multicast entitlement. Manual stream URLs use the existing approval handshake.
Android/Windows auto-discovery is unchanged. Rotate the device and test front/back
cameras on hardware before distribution; iOS orientation is handled by AVFoundation.

## Validation

Twelve Flutter tests passed in the Windows test harness: frame channel order,
row padding, mirroring, downsampling, invalid frames, iOS startup configuration,
and seven camera lifecycle regressions. Static analysis passed. Native plugin
behavior and signing still require the cloud Mac build and physical devices.
