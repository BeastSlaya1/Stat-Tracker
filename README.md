# Stat Tracker 4.0.3 — shared database update

This source update adds Home/Away venue selection, individual staff sign-in,
shared match synchronization, and the supplied logo/splash artwork. It restores
the app's camera dependencies for the browser build. The Access file is unchanged.

## Shared data and offline use

The Access reference lists have been imported into `reference_data.json` and
`server/seed.sql`. The source database contained no users, matches, tracking rows,
or login records. Schools, sports, age groups, team codes, teams and stat/action
definitions are preserved. The app uses the imported school list in match creation.

The online service stores match documents, including teams, events, scores and
timestamps. Staff accounts are separate from the empty Access Users table.
Every signed-in staff member has access to the same matches. Changes are queued
locally, then retried every 15 seconds while the app is open. Internet access
does not wake a closed app. Browser data must not be cleared while unsynced work
is pending. Native apps use a writable per-user/app data folder.

If two devices edit the same match, the Database screen offers **Keep both
versions**. This preserves the server version and creates a separate offline
copy of local edits. It does not silently overwrite another person's work.

## Live shared database

The service is deployed in your Cloudflare account. Its connection address is
configured internally and is not shown on the staff sign-in screen.

The app configures this address internally. Open **Database** and sign in. Joshua Pieterse's
first staff account has been created; its generated password was supplied in
an access-restricted local file, separate from this source package. No password
or administrator key is included in the app or repository.

The database contains the imported Access reference lists. Live verification
passed for staff login, shared match upload/download, deletion, and logout.
The verification match was deleted. The live website and GitHub repository
have not been updated yet.

To maintain the existing service, from the `server` folder:

    npm ci
    npx wrangler login
    npm test
    npm run check
    npm run deploy

The existing database ID is configured in `wrangler.toml`. Do not create a new
database for routine app updates. For a separate installation, create a D1
database, change that ID, apply `schema.sql` and `seed.sql`, set a private
`ADMIN_SETUP_KEY` with `npx wrangler secret put ADMIN_SETUP_KEY`, then deploy.

Create each staff account with:

    python manage_staff.py

This prompts privately for the administrator key and initial staff password.
There is no public registration endpoint. Passwords are salted and hashed;
sessions expire after seven days. To disable an account, set its `enabled`
column to `0` in the Cloudflare D1 console; subsequent requests are rejected.

In the app, open **Database** and sign in with the staff account. The service
address is configured internally and is not shown in the login dialog. The server permits requests from
`https://stattrackerv4.stream` and `https://www.stattrackerv4.stream`; adjust
`ALLOWED_ORIGINS` if your website uses another address.

## Upload the app source without losing directories

Keep `.github`, `packages`, `assets`, `scripts`, `server` and `web-downloads` as
folders. The root `pyproject.toml` describes **stat-tracker**. The one inside
`packages/stc_camera_preview` describes **stc-camera-preview**. Never replace
one with the other. This was the cause of the website's missing camera support.
Use a local Git checkout/GitHub Desktop to copy, commit and push this directory
if browser uploads flatten folders or add `(1)` to duplicate filenames.

The web workflow validates required paths before building. Once updated on
GitHub, rebuild the website. Browser camera permission must be allowed on HTTPS.

## Installed app builds

The accompanying Android APK and Windows installer are version 4.0.4. The
earlier 4.0.1 installers do not contain database synchronization. To rebuild
from this project root:

    python -m flet.cli build apk --project "Stat Tracker" --product "Stat Tracker" --org com.flet --permissions camera --build-version 4.0.4 --build-number 4 --yes
    python -m flet.cli build windows --project "Stat Tracker" --product "Stat Tracker" --build-version 4.0.4 --build-number 4 --yes

The iPhone/iPad workflow runs manually on a cloud Mac and creates an unsigned
archive. Apple signing and physical-device testing are still required for
installation and TestFlight distribution.

## Checks

    python scripts/check_layout.py
    python -m unittest discover -s tests -v
    node --test server/camera.test.mjs

The Node tests require a recent Node version with `node:sqlite`. They use an
isolated SQLite database; production uses Cloudflare D1. Tests cover staff
authentication, revoked sessions, retry/idempotency, stale revisions, deletion,
offline persistence and preserving conflicting work. The live service has also passed an end-to-end check using the app transport.
Physical-device camera tests and a newly published website remain to be checked.


## Version 4.0.4: camera and workspace update

- Installed apps use the same compact header and 60% workspace allocation as
  the web app. The download button is shown only in the browser.
- Returning browser users finish loading their saved name before a welcome
  prompt is considered. Failed storage reads do not overwrite saved data.
- Android preview uses the camera plugin's own orientation. Raw broadcast
  frames compensate for device orientation separately.
- The Windows MJPEG reader displays small frames immediately, instead of
  waiting for its network buffer to fill.

### Browser camera (iPhone/iPad, Android or desktop browser)

Open https://stat-tracker-sync.joshuapieterse1.workers.dev/camera on both
devices. Sign in with a staff account on each device. Choose **Send this
camera** on the phone, allow camera access, then enter its 12-character code
under **Receive a camera** on the other device. Approve the receiving device
on the sender. Stop the connection before changing cameras or pairing again.

The installed Windows app's **Receive iPhone / browser camera** button opens
this companion page. Browser video is displayed there, not embedded in the
installed match workspace. Keep the pages visible and the sender unlocked.
Safari on iPhone/iPad is the intended browser, but physical Apple hardware has
not been tested here. Android-to-Windows installed-app streaming still uses
the existing Camera Mode / Auto-Discover / number approval flow.

The service stores temporary signaling metadata, not video. Both participants
must sign in, only one receiver can claim a code, and the sender must approve
before the receiver gets connection details. Codes expire in ten minutes;
established video continues directly between devices. One sending room per
staff account is allowed. Signaling stops polling once connected.

Cloudflare STUN assists direct WebRTC connections. No paid TURN relay is
configured, so use the same Wi-Fi; restrictive guest/school/mobile networks
may prevent video even after pairing. This is not a universal cross-network
streaming service. Video only; audio is not captured.

### Deploying the camera service

From `server`, run `npm ci`, then:

    npx wrangler d1 execute stat-tracker --remote --file camera-schema.sql
    npx wrangler deploy

The additive camera schema does not change matches, staff or reference data.
The live camera service was deployed and tested for this release. Upload the
updated source to GitHub to publish the web-app buttons and downloads page.
The page references versioned CSS/JS URLs to avoid mixing older styles with
new markup. Publish both installers under release tag **v4.0.4** with the exact
filenames shown in `web-downloads/downloads.js`.

### Rotate the video view

Use **Rotate view** in Camera Mode, the match video panel, or full-screen
logging to turn the displayed video clockwise by 90 degrees. Four taps return
to the original orientation. The browser camera page has the same button on
the video. Rotation changes this device's view and keeps the stream connected;
the receiving device can rotate its own view independently.

Use **Mirror view** beside Rotate view to invert the displayed video
left-to-right. Press it again to restore the normal view. Mirroring and
rotation work together without changing the outgoing feed or pairing.
