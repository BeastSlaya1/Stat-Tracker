# Stat Tracker 4.0.18 — GitHub upload guide

## Changes

- Fixes the camera-picture zoom timeout. Zoom now updates the picture without calling the failing InteractiveViewer zoom method. Buttons, text and panels stay the same size. Camera mode, Inputter mode and fullscreen retain zoom, reset and pan.
- Adds Auth0 browser sign-in for your Website, Windows and Android applications. Existing users connect their Auth0 identity once from Profile and security. Their existing matches and permissions are preserved.
- Keeps existing Stat Tracker 2FA enforced during Auth0 sign-in. The separate authenticator-only sign-in option still requires opt-in and a fresh code.
- Clearly explains when the old account server is missing the new sign-in endpoints, instead of showing an unrelated sign-in failure.
- Retains the basketball layouts, team-only logging, dictionary rules, camera changes and Windows installation/uninstallation behavior from 4.0.17.

## Upload and activate

1. Extract `Stat-Tracker-4.0.18-Source.zip`. Upload the contents to your GitHub repository's **main** branch, keeping folders such as `.github`, `server`, `packages`, `installer` and `web-downloads`. `main.py` must be at the repository root.
2. Run **Actions → Deploy account and sync server → Run workflow**. Wait for a green success result. This applies the account-security, optional sign-in and Auth0 migrations before deploying the Worker. Existing accounts and matches are preserved. Keep the existing authenticator encryption key.
3. Wait for **Actions → Deploy web build to GitHub Pages** to finish successfully. Refresh the website and confirm it shows **4.0.18**. If an old copy remains, close its tabs and reopen it; an installed website may need its cached version refreshed.
4. Create GitHub release **v4.0.18** and attach `Stat-Tracker-Windows-4.0.18-Setup.exe`, `Stat-Tracker-Android-4.0.18.apk`, `Stat-Tracker-4.0.18-Source.zip` and `SHA256SUMS-4.0.18.txt`. Install the new app on your devices. Android build number is **19**, with the same package and signing key as the previous release.
5. Sign in with your existing Stat Tracker password, then choose **Profile and security → Connect Auth0**. Use the same verified email in Auth0. Complete browser sign-in, return to the app and choose **Finish sign-in**. See `server/AUTH0-SETUP.md` for the full instructions.

A release attachment alone does not deploy either the website or account server. The previous live server was missing `/signin/methods`, which explains why refreshing did not enable authenticator-only login. The server workflow above is necessary.

Email/SMS options inside Auth0 depend on its configured connections and delivery providers. The app's separate email/SMS-code methods remain prepared for later setup; see `server/SIGN-IN-SETUP.md`.

## Validation

90 app tests and 60 server tests passed. The Cloudflare bundle dry run passed. Auth0 tests cover account preservation, verified-email linking, existing 2FA, token issuer/audience/nonce/expiry, cancellation, PKCE and replay protection. Live Auth0 sign-in needs a final check after deployment; no live server changes were made while preparing these files.

Windows, Android and a fresh website build completed successfully. Android is version 4.0.18 (build 19); its signature matches the previous release. Packaged Python code, APK integrity and source archive contents were verified. Physical camera devices and Windows multi-user install/uninstall were not retested for this update.

A browser check with a test camera confirmed fullscreen video zoom leaves action-button positions unchanged, and navigation to the Auth0 dialog produced no browser errors.
