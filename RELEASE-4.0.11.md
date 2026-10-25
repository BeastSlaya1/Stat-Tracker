# Stat Tracker 4.0.11 — accounts and saved matches

- The name popup is removed. The workspace displays the signed-in account name; clicking it opens the account panel.
- Login and page reload leave matches closed until you choose one. Admins and staff can still browse all games; regular users can access only their own.
- **Close match** stops the clock/camera, saves the match and closes the workspace without deleting it. Reopen it using the match selector. Offline changes sync when connected.
- **Delete match** is separate and requires confirmation. Deletion syncs to the shared database when online.
- **Edit Match** and saved-game previews show the creator and last editor/inputter. Viewing or closing a match does not change its editor credit. Older matches use the owner/editor information already recorded in the database.
- Administrators can use **Database → Manage accounts → Delete account**. Type the target account email to confirm. The login/profile is removed and sessions revoked. Matches and their original creator/editor credit are retained; ownership transfers to the acting administrator. You cannot delete your own admin account. Staff and ordinary users cannot delete accounts.

## Install and publish

Install Stat-Tracker-Android-4.0.11.apk over the Android app. Close Windows Stat Tracker and run Stat-Tracker-Windows-4.0.11-Setup.exe.

For the website, extract Stat-Tracker-4.0.11-Source.zip and upload its contents to GitHub, preserving all folders including .github, packages, scripts, server and web-downloads. Wait for the web deployment to finish, then reopen the site. In Edge, use Ctrl+Shift+R if the old page remains. The live website UI is not updated until deployment completes.

For public downloads, publish GitHub release v4.0.11 and attach both installers with their exact filenames above.

The shared service has already been updated. No database migration is required. Camera startup, fullscreen and Full HD improvements remain included. Android uses the existing signing certificate; Windows is unsigned.

## Verification

54 Python checks and 30 server checks passed, covering account separation, safe closing/deletion, author metadata, compatibility with older clients, profile deletion with retained matches, and protection of the last administrator. Browser checks covered the name display, credits, Close match and the phone-sized account-deletion confirmation. Installer contents are verified against source.

The deployment succeeded, but the saved credentials used for an automatic live-account check were not accepted. Sign in with your usual account after installation to check the live flow. No existing user profile or match was deleted during validation.
