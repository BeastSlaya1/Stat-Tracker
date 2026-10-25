# Stat Tracker 4.0.13

## Camera selection

Detect Cameras now uses the same WebRTC device list as playback, and the buttons display camera names. Selection retains the device ID if the enumeration order changes. The app releases the previous capture before starting a replacement. If the native library returns a different camera, that stream is stopped and an error is displayed. Changing cameras while broadcasting keeps the sender role (the receiver must reconnect to the new stream).

After installing, click Detect Cameras and select each camera by name. Check the image changes to that physical camera. Unplug a selected external camera and confirm the app reports it unavailable instead of opening the built-in camera. Automated tests simulate device order changes and native fallback; physical USB/capture-card testing remains necessary.

## Profile details and authenticator 2FA

Open Account/Database, then Profile and security. Email is the sign-in address; phone is optional and uses an international country code, e.g. +27821234567. These details are not verified by email/SMS. Changing them requires the current password and, when enabled, a fresh authenticator or unused recovery code.

To enable 2FA, enter your current password and click Set up authenticator. Add the displayed setup key as a time-based account in your authenticator app, then enter its six-digit code and confirm. Save the ten recovery codes before closing the screen. Each recovery code works once. The setup key and recovery codes are not saved to app preferences. Use a fresh code on the next login: a code used to confirm setup cannot be reused.

Sign-in accepts password plus an authenticator/recovery code. Other signed-in devices are revoked when 2FA is enabled or disabled or profile details change. Disable 2FA using your password plus a fresh authenticator/recovery code. Losing both the authenticator and all recovery codes requires administrator-assisted account recovery; changing the password alone does not bypass 2FA.

## Required server deployment

The local implementation is complete; the live Cloudflare service has NOT been changed. This Windows account was not authenticated with Cloudflare. The new Profile and security screen requires this server update. Camera selection works independently of it.

From the `server` directory, with Node.js installed:

1. `npm ci`
2. `npx wrangler login` and sign in to the account that owns the existing `stat-tracker` database and Worker.
3. `npx wrangler d1 execute stat-tracker --remote --file security-migration.sql`
4. `node configure-mfa-key.mjs` — creates a strong encryption secret only if absent; never prints it. Do not remove or replace this secret after accounts enroll.
5. `npm test`
6. `npx wrangler deploy`

The migration only adds the account-security table; existing accounts and matches remain. Deploy the updated clients before enabling 2FA for an account: old clients do not have a code field. The Worker source includes rate limits, replay prevention, encrypted authenticator keys and hashed single-use recovery codes. Do not copy test encryption keys into production.

## Builds

Source version: 4.0.13, build number 14. Rebuild using the existing Flet 0.86.5 tooling and project configuration. The desktop camera change is in the compiled Flutter extension, so replacing Python files in an old installation is insufficient.

Windows: `flet build windows --project "Stat Tracker" --product "Stat Tracker" --org com.flet --permissions camera --build-number 14 --build-version 4.0.13`
Use a short working path to avoid Windows C++ include-path limits. After building, download the same OpenCV wheel version shown in `build/windows/site-packages/opencv_python-*.dist-info/METADATA` with `python -m pip download opencv-python==VERSION --no-deps -d wheelhouse`, then run `python scripts/finalize_windows.py wheelhouse/EXACT_WHEEL_FILENAME.whl`. Flet removes the source configuration files OpenCV reads at runtime; this restores them from the matching wheel. Then compile `installer/StatTracker.iss` with Inno Setup 7.

The provided Windows installer was built successfully, and the bundled camera/account modules were verified against the tested source. Its OpenCV 5.0.0 and NumPy 2.5.3 runtime imported successfully. An isolated launch check passed after correcting PNG artwork loading: the existing PNG files now load directly, avoiding embedded metadata being incorrectly treated as SVG. The artwork itself is unchanged.

Android: use the original Android build environment and signing certificate with `flet build apk --project "Stat Tracker" --product "Stat Tracker" --org com.flet --permissions camera --build-number 14 --build-version 4.0.13`. The Android SDK has now been provisioned under the current Windows account. The original signing certificate was recovered and matches the 4.0.12 APK. Use the existing key explicitly when rebuilding so Android can install the update over the existing app. Keep the keystore outside the source tree and release archive.

Website: upload the source contents to the existing repository to run its deploy-web workflow. This does not deploy the separate Cloudflare Worker. Existing public download links remain at 4.0.12 until replacement installers are published.

## Validation

57 Python app tests passed. 37 server tests passed, including RFC 6238 reference vectors, replay rejection, concurrent OTP use, enrollment expiry/session binding, single-use recovery, rate limits, encrypted storage, profile validation, and account deletion. Cloudflare dry-run bundling passed. 22 Flutter tests also passed, including the native-method-channel test covering discovery, reordered IDs, fallback rejection and disconnected devices.

## Android APK delivered

`Stat-Tracker-Android-4.0.13.apk` was built successfully with Flet 0.86.5 and Flutter 3.44.8. App ID is `com.flet.stat_tracker`, version 4.0.13, build 14. Supports Android 7.0/API 24 and later, with arm64-v8a, armeabi-v7a and x86_64 in one APK. It uses the same signing certificate as the supplied 4.0.12 APK, allowing an in-place update. Install it over the existing app; do not uninstall first.

APK signature verification and archive integrity checks passed. The packaged camera and account modules match the tested source, and artwork assets match the originals. Diagnostic logs and signing files are absent from the app archive. No physical Android device was connected, so on-device camera testing remains necessary. Profile details and authenticator 2FA still require the separate server deployment described above.

Build environment notes: use a short working directory and UTF-8 console output. On this Windows host, Android cross-packaging needed a PEM bundle containing the system-trusted certificates supplied via `PIP_CERT`. The local camera extension was built as a wheel with `pip wheel packages/stc_camera_preview --no-deps --no-build-isolation` and the staging configuration pointed to that wheel; its Flutter code was verified against the source. Keep build logs outside app assets (or exclude `*.log`). Set the four `FLET_ANDROID_SIGNING_KEY_*` variables to the original key credentials, and pass `--android-signing-key-store` explicitly. No signing key is included in the source archive.
