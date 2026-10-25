# Stat Tracker 4.0.22 - GitHub upload and Coach setup

## Changes

- Sentence-case action labels. Two-word symbols use uppercase/lowercase initials, e.g. Sp, Lp, Or, Dr. Single-word symbols use one capital letter. Explicit symbols: [TURN], [SUB], [STOP], [TIME], [FT]. Incomplete results append !. Shot against retains As and conversion point/assist notation.
- Basketball has Substitution and End of quarter controls in normal and fullscreen views. End of quarter stops the clock and records [TIME]; choose the next period when ready. Full time records [FT].
- The current Stats page, radar and saved-game statistics show SCC values only. Opponent scores remain on the scoreboard and in saved history.
- Admins can create Coach accounts with a name, email, password, team age/type (e.g. U15A or U17 1st) and sport. Coaches have server-enforced read-only access to matches for that SCC team and sport.
- The Coach page lets the coach select any number of available matches (at least two to compare) and choose which statistics to show. Choices are saved per account on the device. Each metric compares SCC performance across the selected matches.

## Deploy through GitHub

1. Extract the source ZIP and upload its contents to main, keeping .github, packages, server, tests and installer directories.
2. Run **Actions > Deploy account and sync server**. This applies the additive coach-migration.sql and deploys the access rules. Existing accounts and matches are preserved. Deploy the server before creating Coach accounts.
3. Wait for **Deploy web build to GitHub Pages** to succeed.
4. Publish release v4.0.22 with the Windows installer, Android APK (build 23), source ZIP and checksums.

## Assign teams

As an Admin, open Create account, select Coach and enter the required details, team code and sport. Use Manage accounts to change an assignment; doing so signs that coach out.

In New match or Edit match, set **SCC team age and type** to the same team code and select the same sport. This field belongs to SCC; the opponent Team / Age Group remains separate. Existing matches with no SCC team assignment are not guessed or automatically exposed to coaches. Add their SCC team codes as needed.

Coaches sign in normally. Their landing page shows their assigned matches, View match and customizable comparisons, without editing tools.

## Validation

106 app tests and 64 server tests passed, including coach scope isolation, rejected writes, reassignment/session revocation, SCC-only metrics and requested symbols. Physical Android interaction has not been tested.
