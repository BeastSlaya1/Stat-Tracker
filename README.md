# Stat Tracker v4.0.31 — setup and release guide

This is the single guide for this release. Existing local notes are not needed in the new source package. Android and Windows use build 34.

## Changes

- Hockey (outdoor hockey with the spherical ball) has its own Attack, Defense, Cards and Opposition actions. Includes short/long passes, dribbles, crosses, circle entries, shots, goals, assists, free hits, penalty corners, penalty strokes, long corners, side-line restarts, tackles, interceptions, blocks, saves, clears, ball recoveries and green/yellow/red cards.
- Hockey incompletes modify the original action in its own sequence. Shot followed by Conversion adds one goal; Shot against followed by Conversion adds an opponent goal. Conversion does not automatically add an assist. Penalty awards do not add goals. Goals can also be entered directly; do not record both a direct Goal and a conversion for the same goal.
- Hockey counts/rates, comparisons, dictionary and TXT exports use Hockey data. Historical score offsets are preserved when new Hockey actions are added. Match timing remains manually controlled for school competition variations.
- New match and coach choices show Soccer, Hockey and Basketball only. Older saved matches for other sports are retained.
- Basketball dictionary is reduced to twelve short entries describing current controls, scoring and rates. Removed scoring-context/player controls are no longer explained.
- All TXT exports default to the match title, such as `St Charles College vs Hilton.txt`. Invalid filename characters are replaced; the save dialog still permits renaming.
- Offline sharing discovers active USB/Ethernet interfaces as well as Wi-Fi. Local broadcast discovery supplements the bounded address scan, including automatically assigned Ethernet addresses.

## Files and GitHub upload

The release bundle contains the Windows installer, Android APK, source ZIP, this guide and checksums. It contains no account passwords, private service keys or signing keystores.

1. Extract `Stat-Tracker-4.0.31-Source.zip` into your repository checkout. Keep its folders, especially `.github`, `packages`, `assets`, `server` and `web-downloads`. Do not flatten the files.
2. Commit and push through GitHub Desktop or your normal GitHub process.
3. Run **Deploy web build** in GitHub Actions to update the website. Refresh the site after the workflow succeeds.
4. Create release/tag `v4.0.31` and upload `Stat-Tracker-Windows-4.0.31-Setup.exe` and `Stat-Tracker-Android-4.0.31.apk` with those exact names.
5. Update every device taking part in a shared match. This release needs no new account-server migration or server deployment.

The Windows installer supports current-user/all-users installation and app-data cleanup on uninstall. The Android APK uses the existing signing certificate so it can update prior builds; its build number is 34. This is a direct-install APK, not a Play Store production signing setup.

## Offline match and video sharing

Sign in while online before using the app offline. Use installed apps, and keep the host app open in the foreground. Browsers cannot host or join this local sharing service.

1. Put the devices on the same local network (Wi-Fi/hotspot, USB tethering or Ethernet).
2. On the host, open the match in Inputter Mode and choose **Shared match → Host this match**. Turn on the match camera.
3. On each other device, choose **Shared match → Scan for shared matches → Connect to this match**.
4. The host chooses Attack, Defense, Cards, Opposition or All. Expand individual stats and tick the actions assigned to that device, then approve.
5. The guest joins automatically. All approved devices see all stats and the host video. The host controls camera, clock and possession; guests log only assigned stats. Conversions and incompletes follow their parent action.

Use **Assign controls** to change permissions later. If a device has queued actions when permissions change, restore the relevant permission so those actions can sync. Hidden matches remain undiscoverable and use manual address/code plus approval. Hidden/normal account separation remains enforced.

### Cable setup

- **Android to computer:** connect a data-capable USB cable, enable USB tethering in Android settings, then use the sharing flow above. Phone/driver support varies. Some phones require mobile data enabled to activate tethering even though match traffic is local.
- **iPhone/iPad to computer:** USB Personal Hotspot depends on Apple/cellular-service support. Windows requires Apple Devices or iTunes and device trust. It is not a guaranteed fully offline USB network. Native Stat Tracker for iOS is still preparation only.
- **Ethernet:** supported USB-to-Ethernet adapters can connect devices to a local router/switch. Local IP addresses are required; internet is not. For automatic link-local addresses, use discovery or the exact host address if discovery is blocked.
- A normal USB cable between two computers or two phones generally does not create a network. This release cannot enable unsupported operating-system tethering or turn a charging-only cable into a data connection.
- Allow private-network access if the firewall prompts. If scanning fails, use **Manual connection** with the displayed host address and join code. Network client isolation can block both discovery and connections.

Local match coordination uses authenticated HTTP on the trusted local network; video uses WebRTC. Cloud sign-in/sync continues to use HTTPS. Do not expose the sharing ports to the internet.

References: [Android USB tethering](https://support.google.com/pixelphone/answer/2812516), [Apple USB hotspot requirements](https://support.apple.com/en-ca/guide/iphone/iph45447ca6/ios), [FIH hockey rules](https://www.fih.hockey/about-fih/official-documents/rules-of-hockey). School competition timing and card decisions follow the applicable competition and umpire.

## Accounts and server maintenance

The existing Cloudflare Worker and D1 database remain configured under `server`. Keep the existing database ID. Routine client releases do not require creating a new database. Account roles, hidden activity separation and coach read-only access remain unchanged.

For server changes, use the existing **Deploy account and sync server** workflow. Keep secrets in GitHub Actions/Cloudflare secrets, never in source or release notes. Password and enrolled authenticator sign-in remain available. Email/SMS provider setup is optional; Auth0 sign-in remains removed from the user interface, and Microsoft sign-in is not included.

## Verification and practical limits

164 automated tests passed, covering Hockey scoring, corrections, exports/imports, shared permissions, local discovery privacy, export filenames and existing behavior. Browser checks passed for Basketball scroll preservation and Hockey normal/landscape/portrait layouts, cards, penalties, conversions and defense incompletes. Local adapter enumeration and HTTP/broadcast behavior were checked on Windows.

Physical cable-connected multi-device video and phone-specific tethering have not been verified here. iOS builds and physical Apple hardware testing remain pending. Before relying on sharing at a match, test your intended host/guest devices and cable or adapter with internet disconnected: approval, simultaneous logging, clock pause, video and reconnect.

## iOS preparation

The repository includes the unsigned **Build iPhone and iPad archive** workflow. It is preparation for a future Apple Developer account and a macOS build, not an installable iPhone release. Configure your own Apple bundle ID and signing/team details before TestFlight or App Store distribution. Grant Camera and Local Network permissions when testing. The native iOS work targets iOS/iPadOS 17 or later; keep the host foregrounded.

The web app remains usable on Safari with an internet connection, but local native match hosting/joining is not available through the browser.

## Optional email/SMS provider configuration

# Optional email and SMS sign-in

Password sign-in continues to work. After deploying the new server, users with an enrolled Microsoft/Google/other TOTP authenticator can enable password-free authenticator sign-in in Profile and security → Manage sign-in methods. Enabling it requires their current password and a fresh authenticator or recovery code. Signing in uses their account email and a fresh six-digit authenticator code. This is an optional single-factor alternative; recovery-code sign-in still requires a password.

Email/SMS delivery is prepared but OFF by default. No provider credentials are included and no real messages were sent during testing.

## Activate later through GitHub

1. Set up a Twilio Verify service. Enable SMS for the countries you need. For email, connect a verified SendGrid sender and email template to that Verify service, following [Twilio's email setup](https://www.twilio.com/docs/verify/email).
2. In repository Settings → Secrets and variables → Actions, add secrets `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID`. Keep them in secrets, never in source files or release descriptions.
3. Add repository variables `SIGNIN_EMAIL` and `SIGNIN_SMS`, each exactly `true` or `false`. Enable only channels configured in your Verify service.
4. Run Actions → Deploy account and sync server. The workflow applies the additive `signin-migration.sql`, preserves the authenticator encryption key, saves optional delivery configuration and deploys the Worker. If all three Twilio secrets are absent, it skips delivery setup and preserves existing Worker settings.
5. Sign in with a password. Save your email/phone in Profile and security, then open Manage sign-in methods and verify the saved contact using its received code. Phone numbers must include the country code, for example +27821234567.
6. Sign out and choose Email code or SMS code. Enter your account email, choose Send code, then enter the received code. If 2FA is enabled, also enter a fresh authenticator or recovery code.

Use a test account and your own approved destinations to verify delivery before enabling it for everyone. Provider billing and sending limits are managed in Twilio. No provider account or subscription has been created for you.

## Behavior

- Codes are bound to an account, saved contact, purpose and ten-minute challenge. Contact enrollment is also bound to the signed-in session.
- Unverified profile details cannot be used for code sign-in. Changing a contact invalidates that contact's verification. Password changes clear optional sign-in enrollments, which must then be enabled again.
- Requests and guesses are rate-limited by IP and account. Only one check can consume a challenge. Expired codes, disabled accounts, revoked challenges and reused codes are rejected.
- Email/SMS sign-in does not bypass existing authenticator 2FA. Authenticator-only sign-in must be explicitly enabled per account and requires a TOTP code, not a recovery code.
- Disabling/replacing the authenticator also disables authenticator-only sign-in.
- To turn off delivery later, set the relevant repository variable to `false` and rerun the server workflow with the three secrets still present. Individual users can disable their code sign-in in Manage sign-in methods.

Integration references: [Start a verification](https://www.twilio.com/docs/verify/api/verification), [Check a verification](https://www.twilio.com/docs/verify/api/verification-check).

### Apple local-network preparation

The source includes local-network access descriptions and private/link-local IPv4 ATS exceptions. iOS/iPadOS 17 supports these IP ranges. Broadcast discovery additionally requires Apple's multicast networking entitlement in a signed app; request/configure it before distribution. Without it, use the existing unicast scan or manual host address. These settings do not replace signing or physical iOS testing.

References: [Apple local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy), [Apple IP-address exceptions](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsexceptiondomains).
