# Stat Tracker 4.0.17 — GitHub upload guide

## Requested changes

- Basketball's normal logger matches the soccer layout: the same compact scoreboard, large action-tile grid, Attack / Defence / Cards tabs, and a separate Incompletes panel.
- Fullscreen uses the same structure: incomplete buttons down the left, score/clock controls above the central video, action tiles down the right, and discipline/undo controls below the video. Narrow screens use the scrolling layout.
- Incompletes is enabled only for the latest eligible action on the selected team. For a missed shot, first log the shot, then press its incomplete button. This changes one made attempt into one missed attempt, with no duplicate attempt or points. Undo restores the previous outcome. Failed defensive actions are not credited as successful steals, blocks or rebounds.
- The Cards tab uses basketball technical, unsportsmanlike and disqualifying fouls. It does not introduce soccer yellow/red cards into basketball.
- Basketball is team-only. There are no player selectors, player-entry forms, lineup controls or player-stat panels. No player identity is recorded by the basketball logger. Older saved data is preserved for compatibility.
- Rules, definitions and formulas stay in Dictionary → Rules → Basketball rules.
- The separate Connect phone or tablet button is removed. Scan for streams remains available for remote camera discovery.
- The current-user/all-users Windows install choice and scoped local-data cleanup on uninstall from 4.0.16 are retained. Online matches and exported reports are kept.

- Camera-picture zoom is available in Camera mode, Inputter mode and fullscreen. Use zoom in/out (1x–4x), reset, pinch or drag to inspect the image. Buttons, text and panels remain the same size; zoom does not change the transmitted stream.

- Sign-in offers Password, Authenticator app, Email code and SMS code. Authenticator-only sign-in must be enabled in Profile and security → Manage sign-in methods after setting up a TOTP authenticator. It uses your account email plus a fresh six-digit code; recovery codes still require password sign-in.
- Email and SMS are prepared for later activation and clearly report when the sending service is not configured. Users must verify their saved contact before code sign-in is allowed. Existing 2FA remains required for password/email/SMS sign-in.

## GitHub upload

1. Create release **v4.0.17** and attach `Stat-Tracker-Android-4.0.17.apk`, `Stat-Tracker-Windows-4.0.17-Setup.exe`, `Stat-Tracker-4.0.17-Source.zip` and `SHA256SUMS-4.0.17.txt`.
2. Extract the source ZIP and replace the repository's source files on `main`, preserving folders, including `.github`, `packages`, `server`, `installer` and `web-downloads`. `main.py` belongs at the repository root.
3. Wait for **Actions → Deploy web build to GitHub Pages** to complete. Attaching a source ZIP to a release alone does not publish the website.
4. Confirm the website/app shows **4.0.17**. Android retains the same package ID and update-signing key, with build number 18.

Run **Actions → Deploy account and sync server → Run workflow** after uploading the source. It adds the sign-in tables and deploys the new account endpoints. Existing passwords, accounts and matches are preserved. Keep the existing authenticator encryption key. Email/SMS delivery remains off until configured; see `server/SIGN-IN-SETUP.md`. Earlier source/release files remain available; use the 4.0.17 files for this update.

## Validation

83 app tests and 48 server tests passed, including normal and fullscreen controls, team-only logging, incomplete shots, defensive outcomes, undo, saved-data roundtrips and existing soccer behavior. Windows and Android builds passed; APK integrity, signing-key continuity, embedded Python source and source-ZIP checks passed. The fresh website build was blocked by dependency download timeouts; the browser preview uses the unchanged previously built Flutter runtime with the current app package. GitHub must build and publish the website from the source ZIP. Camera hardware and multi-user Windows installation/uninstallation were not exercised on physical test devices in this update.
