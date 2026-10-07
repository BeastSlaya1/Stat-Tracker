# Stat Tracker 4.0.19 - GitHub upload guide

## Changes

All sports log SCC (St Charles College) actions only. Basketball's opponent-team selector has been removed, and a stale selection cannot change the recorded team. Existing match history is retained. Opponent scoreboard adjustments remain available without recording opponent performance stats.

Basketball has these controls in both the normal logger and fullscreen:

- **Layup** adds two points and one two-point attempt. **Layup incomplete** changes that attempt to a miss and removes those two points. Undo restores the made layup.
- **Shot** records an action without guessing its value. **Shot incomplete** marks it unsuccessful. Unclassified misses and unresolved shots are reported separately from two-point, three-point and free-throw attempts.
- **Conversion** is available once, immediately after Shot. Choose 1, 2 or 3 points, optionally check Assist below the point choices, then select Record conversion. The preview and sequences use `S^1`, `S^2`, `S^3`, or `S^A1`, `S^A2`, `S^A3`. A conversion adds only one scoring attempt; the selected assist is counted once. One-point conversions count as free throws. Cancelling the popup, opening it, or choosing another logging action uses or clears the conversion opportunity. Undo removes conversion points and its assist together.
- **Attack > Penalty** opens an adjacent menu for awards to SCC. **Defence > Penalty** records awards to the opponent against SCC, within SCC's defence log. Options include Free throw, Personal, Shooting, Offensive/charge, Blocking, Holding, Technical, Unsportsmanlike and Disqualifying fouls, Team-foul penalty, Violation and Other penalty. Awards do not automatically add points. Individual foul buttons have been removed from Attack and Defence. The Cards tab remains available for disciplinary entries; do not enter the same decision twice.
- SCC Attack, Defence and Cards sequences are visible and included in TXT exports. Definitions and logging rules remain under Dictionary > Basketball rules.

## Upload through GitHub

1. Extract `Stat-Tracker-4.0.19-Source.zip` and upload its contents to the repository's `main` branch, preserving `.github`, `packages`, `server`, `installer`, `tests` and `web-downloads`. Keep `main.py` at the repository root.
2. Wait for **Actions > Deploy web build to GitHub Pages** to succeed. Check that the website displays **4.0.19**.
3. Create release **v4.0.19** and attach `Stat-Tracker-Windows-4.0.19-Setup.exe`, `Stat-Tracker-Android-4.0.19.apk`, `Stat-Tracker-4.0.19-Source.zip` and `SHA256SUMS-4.0.19.txt`. Install the updated app on your devices. Android build number is 20.
4. This sports update has no new server migration. If the earlier Auth0/account server update has not yet deployed successfully, finish configuring the Cloudflare GitHub secrets and run **Deploy account and sync server**. That is still needed for Auth0 and the new sign-in methods, independently of this basketball update.

A release attachment does not update the repository or website. The source contents must also be uploaded to `main`.

## Validation

96 app tests passed, including all point/assist combinations, SCC-only logging across sports, layup misses, conversion cancellation, stale popups, penalties, scoring corrections, undo, deletion and saved-data round trips. Existing historical basketball events remain supported.

Windows, Android and the website built successfully. Browser checks verified normal and fullscreen conversions, optional assists, layup incomplete, Attack personal-foul and Defence free-throw menu selections, SCC-only persisted events and the expected scoreboard, with no browser errors. APK signing-key continuity and embedded source integrity were verified. Physical Android interaction was not tested.
