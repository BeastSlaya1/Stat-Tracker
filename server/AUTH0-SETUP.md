# Auth0 setup for Stat Tracker 4.0.18

Your three Auth0 applications are wired into this release. No Auth0 client secret is required or included.

## Settings already supplied

Tenant: `dev-oh5h8875qsfq7eja.us.auth0.com`

| Application | Type | Client ID |
| --- | --- | --- |
| Stat Tracker Website | Single Page Application | `u8NnDj8nN6Vo8aGMR3JCA0PaoVqvaVgu` |
| Stat Tracker Windows | Native | `NfWZEcFXPqaBdKG453NTD0EeAeRLyERh` |
| Stat Tracker Android | Native | `yC7iKrieD91ASJvl0kiyMsYGWLfzED2D` |

Allowed Callback URLs for all three:
`https://stat-tracker-sync.joshuapieterse1.workers.dev/auth0/callback`

Website Allowed Web Origins:
`https://stattrackerv4.stream, https://www.stattrackerv4.stream`

Keep Token Endpoint Authentication Method set to **None** for these public applications and enable the Authorization Code grant. Under each application's Connections tab, enable the connection you want users to use (for example Username-Password-Authentication). The app uses Auth0's browser login screen; available social, email or SMS options are controlled by your Auth0 connections and sending-service settings. Creating an application alone does not configure those services.

Reference: [Auth0's Authorization Code with PKCE setup](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce/add-login-using-the-authorization-code-flow-with-pkce).

## Publish through GitHub

Upload the extracted 4.0.18 source to the repository's main branch, including `.github` and `server`. Run **Actions → Deploy account and sync server → Run workflow**. This adds the Auth0 tables and updates the Worker. Keep the existing authenticator encryption key. Wait for **Deploy web build to GitHub Pages**, and install the new Windows or Android release as needed.

Uploading a ZIP only to a GitHub release does not update the website or the server.

## Connect your existing account once

1. Sign in to Stat Tracker with your existing Stat Tracker email and password.
2. Open **Profile and security → Connect Auth0**.
3. Enter your current Stat Tracker password and a fresh authenticator or recovery code if Stat Tracker 2FA is enabled.
4. Choose **Open Auth0 sign-in**. In the browser, sign in or create an Auth0 account using the same email as your Stat Tracker account. Complete its email verification first.
5. Return to Stat Tracker and choose **Finish sign-in**. If your browser blocks the automatic opening, use **Open Auth0 in browser**.
6. On later visits choose **Sign in with Auth0**. After browser sign-in, return to the app, enter a fresh Stat Tracker authenticator/recovery code if your account has 2FA, and choose **Finish sign-in**.

A linked Auth0 identity uses your existing Stat Tracker account, matches and permissions. Auth0 sign-up alone does not create a Stat Tracker account. For a new Stat Tracker user, an administrator first creates the account through the existing account controls.

The browser and app must remain open during this ten-minute sign-in process. Cancelled, expired or failed attempts can be restarted. An authenticator code already used for another operation cannot be reused.

## Authenticator-only sign-in

This is a separate Stat Tracker option. Set up a compatible authenticator in **Profile and security**, then use **Manage sign-in methods → Enable authenticator sign-in**. At sign-in select **Authenticator app**, enter your Stat Tracker email and a fresh six-digit code. Recovery codes require password or linked Auth0 sign-in. This feature needs the updated server workflow too.

## Validation and limits

The public tenant discovery endpoint and all three client IDs were checked. Automated tests simulate Auth0 token responses and check token validation, account linking, existing 2FA, cancellation, expiry and replay protection. A real account's complete browser sign-in must be checked after you deploy the Worker. This release does not silently change your Auth0 dashboard connections, billing plan, MFA policy or delivery providers.
