# Stat Tracker 4.0.20 - GitHub upload guide

## Changes

- Removed the Sign in with Auth0 button from the sign-in screen.

- Action buttons use correctly interpreted transparent backgrounds, fixing the bright green backgrounds behind purple text on Offensive rebound and Loose ball recovered.
- Basketball Defence includes **Shot against (As)** and **Conversion**, in both normal and fullscreen logging.
- Shot against records an opponent shot against SCC. Conversion offers 1, 2 or 3 points and an optional opponent assist. Sequences use `As^1`, `As^2`, `As^3` or `As^A1`, `As^A2`, `As^A3`. Only the opponent scoreboard increases; SCC shooting and assist totals stay separate.
- **Shot against incomplete** records `As!` without adding points. Conversion is available once immediately after the shot; another action or opening/cancelling the conversion dialog clears it. Undo and event deletion remove the corresponding opponent points.
- Definitions remain under Dictionary > Basketball rules. Existing match history is preserved.

## Upload through GitHub

1. Extract `Stat-Tracker-4.0.20-Source.zip` and upload its contents to the repository main branch, including `.github`, `packages`, `server`, `installer`, `tests` and `web-downloads`. Keep main.py at the repository root.
2. Wait for **Deploy web build to GitHub Pages** to succeed. The website should show **4.0.20**.
3. Create release **v4.0.20** and attach the Windows installer, Android APK, source ZIP and checksum file. Android build number is **21**.
4. This update has no server changes or migrations. Earlier account-server updates still need their successful server workflow deployment.

Uploading release attachments alone does not update the website: upload the source to main as well.

## Lost authenticator

Use your password and an unused recovery code to sign in. In Profile and security, enter your password and a different unused recovery code, then select Disable 2FA. A recovery code works once. This release does not reset account authentication or change any live profiles.

## Validation

99 app tests passed, covering all opponent point/assist combinations, SCC-only event ownership, independent score totals, misses, undo, deletion, persistence and existing behavior.

Browser checks verified Shot against, incomplete and assisted/unassisted conversions in normal and fullscreen layouts, correct saved opponent scores and no browser errors. Button contrast was visually checked. Physical Android interaction was not tested.

Windows, Android and website release builds succeeded. Android used the previously downloaded dependencies after a network timeout. Android signing continuity, embedded application code and release archive integrity were checked.
