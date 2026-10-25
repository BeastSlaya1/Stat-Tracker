# Stat Tracker 4.0.8 — browse saved games

Sign in as an admin or staff member, then open **Database → Browse saved games**.

- Search by team, date or sport. Games are ordered newest first and listed in pages of 20.
- **View game** opens a read-only summary of the score, statistics and recent events. It does not switch the active game or save changes.
- **Edit details** selects that game and opens its editable details. Choose Save Changes when finished.
- **Open workspace** selects the game in the normal workspace, where you can work with its score, events and statistics.
- **Refresh games** checks for shared games using the existing sync process. Offline, the list shows games already saved on that device. Unsynced games from another device appear once that device syncs.

Admin and staff accounts can browse games from all accounts. User accounts retain access only to their own matches. The original match owner stays unchanged when staff edit a game. If a sync replaces a game while its details are being edited, reopen the editor before saving; this avoids silently losing edits.

## Install and publish

Install Stat-Tracker-Android-4.0.8.apk on Android, or close the Windows app and run Stat-Tracker-Windows-4.0.8-Setup.exe. Existing app data and account permissions are retained.

For the website, extract Stat-Tracker-4.0.8-Source.zip and upload its contents to GitHub, preserving folders including .github, packages, scripts, server and web-downloads. Wait for the web deployment workflow to succeed, then refresh the site. The web interface is not updated until that deployment completes.

For the download buttons, publish a GitHub release tagged **v4.0.8** and attach both installers with the exact filenames above.

This game-browser update needs no database migration or server deployment. Existing camera, account-management and password-change features remain included. The Windows installer is unsigned; Android keeps the existing signing certificate.

## Checks

44 Python checks passed, including manager-only access, searching, pagination, read-only viewing, selection by match ID, edit saving and stale-editor protection. The actual saved-games list, game preview and edit flow were checked at phone width. Native build outputs are checked against the source before packaging. Camera hardware was not retested for this update.
