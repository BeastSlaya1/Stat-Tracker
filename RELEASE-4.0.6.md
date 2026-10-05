# Stat Tracker 4.0.6 — accounts and database management

Your existing Joshua Pieterse account is now an admin / creator account. Keep using your existing login.

## Account permissions

| Account | Create accounts | Matches | Shared reference database |
|---|---|---|---|
| Admin / creator | Admin, staff and user | All matches | View, add, edit and delete rows |
| Staff | User accounts only | All matches | View, add, edit and delete rows |
| User | None | Create, view, edit and delete their own matches only | Uses shared choices in match forms; no management access |

Only admins can change account types, disable accounts or reset passwords. Those changes sign the affected account out. An admin cannot remove their own admin access.

## Use the new controls

1. Install the 4.0.6 Android or Windows update. Update all devices that will switch between accounts.
2. Open Database and sign in. Your account name and role appear there.
3. Choose Manage accounts → Create account. Enter the name, email, password and permitted account type. Passwords need at least 12 characters. Give the new person their details privately.
4. Choose Manage shared database to manage schools, sports, age groups, team codes, teams and statistics reference rows. Edit or add rows, then choose Save changes. Discard / close leaves the shared table unchanged.
5. Staff/admins manage matches from the normal match selector and Edit Match/Delete controls. Users only receive matches they created.

The Create New Match popup scrolls on smaller screens; its Cancel and Create Match buttons stay accessible.

Saved match queues are separated by account and role. Signing out hides that account's matches while preserving its offline work. Internet is required for creating accounts and managing shared reference tables; match changes still retry when connectivity returns. Existing accounts other than the creator retain staff access. Existing matches were assigned to their recorded updating account because earlier versions did not record a separate creator.

## Update the website and downloads

The database migration and server permission checks are already deployed. Do not rerun roles-migration.sql on the existing database.

1. Extract Stat-Tracker-4.0.6-Source.zip and upload its contents to the GitHub repository, preserving all folders, including packages, server, scripts, web-downloads and .github. Keep main.py and pyproject.toml at the repository root.
2. Wait for Deploy web build to GitHub Pages to succeed. Refresh the website; Edge users can use Ctrl+Shift+R if needed.
3. Create a GitHub release tagged v4.0.6 and attach Stat-Tracker-Android-4.0.6.apk and Stat-Tracker-Windows-4.0.6-Setup.exe with these exact filenames.

The website does not gain the new interface until the source is published through GitHub. iPhone/iPad users continue to use the website; native Apple signing is not included.

## Checks

Both native builds completed. 35 Python app checks and 16 server checks passed, including account creation permissions, match ownership, rejected access attempts, account switching and stale database edits. The actual Flet dialogs were rendered at phone width. Live admin login, database management access and existing match owners were verified. Physical-device camera behavior was not retested for this account update.

A private database backup was saved before migration, outside the source package. No passwords, setup keys or database backup are included in this ZIP. Android retains the existing signing certificate; the Windows installer is unsigned.
