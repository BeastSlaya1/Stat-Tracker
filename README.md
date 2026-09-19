# Stat Tracker 4.0.2 — shared database update

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

The service is deployed in your Cloudflare account:
`https://stat-tracker-sync.joshuapieterse1.workers.dev`

The app prefills this address. Open **Database** and sign in. Joshua Pieterse's
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

In the app, open **Database**, enter the deployed HTTPS worker address, and
sign in with the staff account. The server permits requests from
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

The accompanying Android APK and Windows installer are version 4.0.2. The
earlier 4.0.1 installers do not contain database synchronization. To rebuild
from this project root:

    python -m flet.cli build apk --project "Stat Tracker" --product "Stat Tracker" --org com.flet --permissions camera --build-version 4.0.2 --build-number 3 --yes
    python -m flet.cli build windows --project "Stat Tracker" --product "Stat Tracker" --build-version 4.0.2 --build-number 3 --yes

The iPhone/iPad workflow runs manually on a cloud Mac and creates an unsigned
archive. Apple signing and physical-device testing are still required for
installation and TestFlight distribution.

## Checks

    python scripts/check_layout.py
    python -m unittest discover -s tests -v
    node --test server/worker.test.mjs

The Node tests require a recent Node version with `node:sqlite`. They use an
isolated SQLite database; production uses Cloudflare D1. Tests cover staff
authentication, revoked sessions, retry/idempotency, stale revisions, deletion,
offline persistence and preserving conflicting work. The live service has also passed an end-to-end check using the app transport.
Physical-device camera tests and a newly published website remain to be checked.
