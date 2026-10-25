# Stat Tracker 4.0.21 - GitHub upload guide

## Changes

- Separate St Stithians College and Kearsney choices. Old cached/server combined names are split in the selector without duplicating St Stithians or changing old match records.
- Basketball Attack includes Short pass (half court and shorter), Long pass (half court and longer) and Dribble, plus their incomplete variants in normal and fullscreen modes. A pass exactly half court can be classified with either button; log it only once. Incomplete replaces the completed result, does not change the score and does not automatically add a turnover. Sequences use Sp, Lp, Dr and an exclamation mark for incomplete. Definitions are in the Basketball dictionary.
- Account label is Admin. Staff is removed from account-type choices; Admin and User remain. Existing Staff accounts retain their permissions until an administrator explicitly changes their role.
- Fixtures show only games created by the signed-in user or explicitly opened for editing. Close match removes the fixture without deleting its data. Choices persist per account on this device. Use Account > Browse saved games to reopen a game. Viewing alone does not open a fixture. Ordinary users can browse the games already available to their account; server access rules are unchanged.
- Saved-game basketball views show basketball statistics. Other non-soccer sports show recorded SCC event counts and the scoreboard instead of soccer-only calculated metrics.

## Upload

1. Extract Stat-Tracker-4.0.21-Source.zip and upload its contents to the repository main branch, preserving .github, packages, server, installer, tests and web-downloads. main.py belongs at the repository root.
2. Wait for Deploy web build to GitHub Pages to succeed. Check version 4.0.21 on the website.
3. Create release v4.0.21 and attach the Windows installer, Android APK, source ZIP and checksum file. Android build number is 22.
4. No server migration is required for these changes. Existing authentication settings are unchanged.

Release attachments alone do not update the website; the source must also be uploaded to main.

## Validation

103 app tests passed, covering pass/dribble outcomes, undo, school choices, per-user fixture filtering, closing/reopening, view-only behavior and sport-specific statistics. Physical Android interaction was not tested.

Windows, Android and web builds succeeded. Normal/fullscreen pass and dribble controls and saved outcomes were verified in the browser. Fixture closure persisted with match data retained; the empty fixture dropdown was visually verified after reload (its canvas label is not exposed as browser text). Installer code, school data, Android signing continuity and archive integrity were verified.
