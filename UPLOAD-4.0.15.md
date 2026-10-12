# Stat Tracker 4.0.15 — GitHub upload guide

## What is included

Basketball now has its own logger for both teams, player rosters, four quarters and overtime selection, and an elapsed-time clock. It includes 2-point, 3-point and free-throw makes/attempts; shooting percentages; offensive/defensive/total rebounds; assists; steals; blocks and shots blocked against; turnovers; personal, technical, unsportsmanlike and disqualifying fouls; fouls/charges drawn; deflections; loose balls; timeouts; tagged paint, fast-break, second-chance and turnover points; bench points; double/triple-doubles; simple efficiency; effective field-goal and estimated true-shooting percentages; assist/turnover ratio; shot mix; free-throw rate; estimated possessions and points per 100 possessions. Definitions and formulas are in the app and exported report.

Add players in the basketball logger. Select five on-court players and apply the lineup for each team before starting the clock; update at substitutions. Minutes and plus/minus cover only recorded lineups and running-clock time. Pause at stoppages. The clock shows elapsed time, not a countdown, and periods are selected manually. Up to ten overtime periods are offered.

Each shot button records one complete attempt. Do not record a made basket twice. Assists, steals, blocks and fouls are entered separately. Shot tags apply to the next entry, then reset. Bench status comes from the player's starter checkbox when points are logged. Team/unassigned events count in team totals but not a player row. Some metrics require complete logging for both teams; estimates are labelled and undefined ratios show a dash. Camera-based movement metrics and proprietary ratings are not inferred.

Older basketball matches keep their existing scores as a historical baseline. Their football-style events remain in the report but cannot reconstruct basketball shooting data. Use Undo or delete an event to correct its stats; score corrections change only the score. Reports include re-importable match data.

This release also includes the previous camera-selection, remote tablet stream, Scan for streams, profile email/phone, and authenticator-app two-factor authentication fixes. Authenticator setup provides a QR code or manual key for Microsoft Authenticator, Google Authenticator and other standard TOTP apps. Email and phone are profile details, not SMS/email verification services.

## Why refreshing did not show the update

The Cloudflare account server and the browser application are separate deployments. The account server was updated previously, but the browser application still needs its GitHub Pages deployment. Attaching a source ZIP to a GitHub Release does not replace repository files and does not publish the website.

## 1. Update repository files to publish the website

1. Extract `Stat-Tracker-4.0.15-Source.zip` on your computer.
2. In your `BeastSlaya1/Stat-Tracker` GitHub repository, replace the repository's app files on `main` with the extracted contents. Keep the existing folder structure. `main.py`, `basketball.py`, `basketball_ui.py`, `pyproject.toml`, `server`, `packages`, `web-downloads`, and `.github` must be at the repository root, not inside another nested folder. Commit the change. GitHub Desktop is convenient for preserving all folders; the website upload UI can also be used.
3. Make sure `.github/workflows/deploy-web.yml`, `.github/workflows/deploy-server.yml` and `.github/workflows/build-ios.yml` were included. Windows may hide `.github`; if it is missing, create/update those exact paths in GitHub's file editor.
4. Open **Actions → Deploy web build to GitHub Pages**. A push to `main` starts it automatically, or choose **Run workflow**. Wait for both build and deploy jobs to succeed.
5. Repository **Settings → Pages → Source** should be **GitHub Actions**. Preserve the existing custom domain `stattrackerv4.stream` and the root `CNAME` file.
6. Open your website. Its title/header should show **Stat Tracker 4.0.15**. If the workflow succeeded but you still see the old app, close its tabs and try a private browser window. Avoid clearing browser data until any locally saved matches have synced or been exported.

The source package includes the files for the existing website workflow. Do not upload the prebuilt web output into the repository source root.

## 2. Upload the native app release

Create a GitHub Release with tag **v4.0.15** and attach these exact files:

- `Stat-Tracker-Android-4.0.15.apk`
- `Stat-Tracker-Windows-4.0.15-Setup.exe`
- `Stat-Tracker-4.0.15-Source.zip`
- `SHA256SUMS-4.0.15.txt`

The website's download page looks for those Android and Windows filenames under that tag. It shows Not yet published until it finds the matching assets. Uploading the release before committing the website files avoids that brief gap. Android package ID remains `com.flet.stat_tracker`, build number 16, signed with the same key as previous releases.

## 3. Publish account-server changes through GitHub

If you already use Cloudflare's connected-repository builds, keep that setup and ensure its working directory is `server` and its deployment command is `npx wrangler deploy`. The new manual GitHub Actions workflow is an alternative; do not run both simultaneously.

For **Actions → Deploy account and sync server → Run workflow**, add these repository Actions secrets if not already configured:

- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token restricted to the relevant account with Workers Scripts edit and D1 edit access.
- `CLOUDFLARE_ACCOUNT_ID`: the ID of the Cloudflare account containing Stat Tracker.

Never paste either into source files. The workflow tests the server, applies the additive account-security migration, retains the existing authenticator encryption key, and deploys the Worker. It does not re-seed accounts or matches. Do not reset the database or replace `MFA_ENCRYPTION_KEY`; enrolled authenticators depend on that key. The security migration and key have already been applied to the live server, so repeating this workflow retains them.

The existing server accepts the new basketball fields; basketball does not need another database table. Publishing the browser update is the step required to see its new screens.

## Validation

74 Python app tests and 37 server tests passed, including scoring/percentages, both teams, player identity, undo, saved-data roundtrips, lineups, minutes/plus-minus, profile and authenticator flows, and existing football behavior. Browser, Android and Windows release builds completed. An isolated Edge browser smoke test reached the 4.0.15 startup screen with no startup errors; local asset requests were served directly from the built files to bypass a local HTTP transfer issue. Android package contents match the tested source, use build number 16, and retain the prior signing certificate. Windows packaged bytecode matches the source. Physical tablet streaming and an installed-device basketball game still need real-device use to verify hardware behavior.
