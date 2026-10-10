# Stat Tracker 4.0.26

## App changes
- Compact fullscreen time controls on one horizontal row. Start/Pause is beside the clock.
- Defence: Layup against (Al) adds 2 opponent points. Incomplete Al! reverses them; undo restores them. SCC shooting statistics are unaffected.
- Owner account type and Hidden account checkbox in account management.
- Owners can see both activity groups and use Account > Match comparisons for all sports.

## Deploy through GitHub
Upload source contents including .github and server. Run Deploy account and sync server BEFORE using Owner/hidden features, then deploy the web build. Publish Windows and Android v4.0.26 (Android build 27).

The additive owner-migration.sql grants primary Owner access to the EXISTING account 4530@sccstudent.co.za. No account or password is created. Sign in again after deployment. If that account does not yet exist, create it first and rerun the workflow. The initial grant runs once; later email changes do not grant ownership.

Only this primary Owner can create/promote other Owners or manage their access. Other Owners can create/edit hidden accounts. The primary Owner cannot be deleted, disabled or demoted in the app.

## Hidden activity
Normal accounts see normal matches/activity, hidden accounts see hidden matches/activity, and Owners see both. Existing role restrictions still apply: Coaches are read-only and team/sport-scoped; Users edit their own matches. Hidden account identities are visible only to Owners; other hidden accounts see their match activity credited as Hidden account.

Setting Hidden hides existing matches created or last edited by that account as well as future activity. Already-private matches remain private if the account is made normal again or deleted, preventing accidental disclosure. Other hidden Users can view those matches; Owners can view/edit them. Hidden non-Owner accounts cannot manage public accounts or the shared reference catalogue. Owners can discover both camera groups; pairing requires both devices to use the same activity group so a hidden account cannot announce itself to a normal account.

Install this update on all devices. Updated clients remove revoked synced matches on their next successful sync. Previously downloaded/exported copies and devices that remain offline cannot be remotely erased.

## Validation
118 app tests and 71 server tests passed, including access boundaries, grant restrictions, hidden cameras, account deletion, cache removal and Al/Al! scoring. Physical Android interaction has not been tested.
