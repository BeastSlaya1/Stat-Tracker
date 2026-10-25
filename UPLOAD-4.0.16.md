# Stat Tracker 4.0.16 — GitHub upload guide

This release includes the complete app and server source plus the earlier account, authenticator and camera fixes.

## Changes

- Basketball uses soccer's video-first logger, shared action-button styling, Attack / Defence / Fouls categories, missed-shot controls, substitution and turnover sections, and Time Controllers. Basketball retains its own scoring and statistics.
- Basketball Stats uses the same radar comparison and coloured home/away comparison bars as soccer. Additional stats and player summaries remain available.
- All basketball rules, definitions and formulas are under **Dictionary → Rules → Basketball rules**. The selector also includes Soccer rules and does not change the match's sport.
- Windows Setup asks **Install for me only** or **Install for all users**. All-users installation requires administrator permission. Current-user installation uses that user's Programs folder; all-users installation uses Program Files. Upgrading in the same scope preserves local data.
- Windows uninstall removes local saved matches, settings, saved sign-in state, runtime preferences and cache. For a current-user installation it removes that user's app data; for an all-users installation it removes Stat Tracker data in the Windows user profiles. The uninstall confirmation explains this. Synced online matches, accounts and user-exported reports are not deleted.
- Uninstall cleanup is limited to Stat Tracker's own folders. Linked/junction or inaccessible folders are retained with a warning. Redirected AppData is recognised for loaded user profiles; unusual redirected folders in unloaded profiles may need manual cleanup.

## Upload using GitHub

1. Create release **v4.0.16** in `BeastSlaya1/Stat-Tracker`, attaching `Stat-Tracker-Android-4.0.16.apk`, `Stat-Tracker-Windows-4.0.16-Setup.exe`, `Stat-Tracker-4.0.16-Source.zip` and `SHA256SUMS-4.0.16.txt`.
2. Extract the source ZIP. Replace the app's repository files on `main` with the extracted contents, preserving folders. `main.py`, `basketball_ui.py`, `ui_widgets.py`, `installer`, `server`, `packages`, `web-downloads`, and `.github` belong at the repository root.
3. Ensure `.github/workflows/deploy-web.yml` is included. A commit to `main` starts **Actions → Deploy web build to GitHub Pages**; you can also select Run workflow. Wait for both build and deploy to succeed.
4. Open the website and check that its title/header shows **4.0.16**. Attaching a ZIP to a release does not update the repository or website. If needed, check in a private browser window after deployment, without deleting unsynced local matches.
5. Install the new Windows EXE to get the updated installer/uninstaller. Older installed versions retain their older uninstall behavior until upgraded. Use the same installation scope as the previous version when updating it; changing scope can create a separate installation.

The website download page checks for the exact filenames in the v4.0.16 release. The Android app retains its package ID and update-signing key, with build number 17.

## Account server

These changes do not require a database migration or a new server deployment. The included server and manual **Deploy account and sync server** workflow preserve the previous profile/2FA work. If you use that workflow, it requires repository Actions secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Keep the existing `MFA_ENCRYPTION_KEY` unchanged. Do not re-seed accounts or reset the database.

## Verification

76 app tests passed, including dictionary selection, basketball categories, team comparison, scoring, undo, lineups and existing soccer behavior. Isolated Windows cleanup tests cover deleting only app folders, retaining unrelated folders, rejecting parent paths and refusing directory junctions. Build and package checks are completed before release delivery. Actual installation/uninstallation across multiple Windows accounts still needs use on a separate test machine; no existing user data was removed during testing.
