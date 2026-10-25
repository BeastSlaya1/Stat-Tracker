# Stat Tracker v4.1.0 — setup and release guide

This is the single guide for this release. Existing local notes are not needed in the new source package. Android and Windows use build 44.

## Corrected v4.1.0 build 44

The player-statistics panel and basketball export now show only jerseys with recorded activity, assists or tracked lineup participation. Old roster-only jerseys no longer produce empty statistic rows, including in existing saved matches. No player events are deleted. The public version remains 4.1.0; replace the previous builds and redeploy the website from this source. No additional server reset or migration is needed for this correction.

## New in 4.1.0

- Both sides have independent Team / age group selectors in Create Match and Edit Match. For example SCC U15A can play Hilton U16A.
- St Charles College is a preloaded opponent choice, allowing matches between two SCC age groups.
- The server deployment applies `server/rosters-reset-410.sql` once. It deactivates all existing jerseys across every normal and hidden team roster, increments roster versions to reject stale edits, and preserves jersey identities and past match statistics. Later deployments do not reset newly added jerseys.
- The updated client clears its old cached team rosters once. Connect to the updated server, open Team jerseys and add/save the jerseys you need. Existing match snapshots and their statistics are preserved.
- Deploy the server first, then the web app and install v4.1.0 on all devices. The prepared release does not itself change the live database.
- Validation: 217 Python checks, including independent ages surviving editing/serialization and a repeat-safe reset across both account realms.

## Browser support: iPhone/iPad, Android and Windows

The same web build uses JavaScript and WebAssembly across these devices; no separate iOS processor package is required. Use an up-to-date Safari on iPhone/iPad or Chrome/Edge on Android and Windows. On iPhone/iPad, use Share → Add to Home Screen if desired, then save the offline version from that installed web app. Portrait and landscape are enabled.

Sign in and save the app while online before going offline. Camera access requires HTTPS or localhost and permission. Keep the app foregrounded and the screen awake while streaming. Safari may not allow discovery through a local HTTP directory; use Connection codes (fallback) on the same network. Safari does not create a Wi-Fi Direct access point. A native signed iOS application remains a separate future distribution step.

Browser runtime support does not prove physical iPhone/iPad camera or offline-storage behavior. Test these on the intended Apple device before a match.

References: [Flutter web platforms](https://docs.flutter.dev/platform-integration/web), [Safari video requirements](https://developer.apple.com/documentation/webkit/delivering-video-content-for-safari).

## Retained from 4.0.39

- Removed jerseys disappear immediately from the team roster list; press Save to persist the roster. Past match stats retain the jersey identity. Adding the same number again reactivates it.
- Shared match keeps one panel for finding/hosting, connection codes and device assignments. Generated codes remain available when reopened. Copy connection code copies the complete value.
- Installed Windows/Android apps run a temporary local directory when Shared match is opened or the device Wi-Fi link starts. Hosts advertise automatically, and Connect exchanges invitation/reply codes automatically before host approval. No internet is used.
- Browsers can list and advertise matches through that local app directory. They try common hotspot addresses; for other networks enter the app’s displayed Local directory address under Browser / network connection. Permit local-network access when the browser asks. Browsers that block local HTTP from HTTPS must use connection codes; this is not universal browser network scanning. A browser-only offline network still needs manual codes.
- Wi-Fi Direct, Feem, Zapya, USB tethering and Ethernet supply the network. They do not bypass browser permissions. Keep the directory app and match host open. The directory carries pairing information only; approved match stats and video use WebRTC. Hidden matches remain code-only and are not advertised.
- Player attribution is checked for local and shared basketball actions; conversions and incompletes retain the original jersey and assisted conversions credit the selected assisting jersey.

## Retained from 4.0.38

- Jersey numbers now accept 0–9999.
- All devices use **Shared match**, with automatic local pairing when a directory is reachable and invitation/reply codes as a fallback. Host creates an invitation, the joining device creates a reply, and the host accepts it and approves the device. Repeat for each device.
- **Device Wi-Fi link** saves your network name and password on that device. Start/apply changes uses those credentials; editing and applying restarts the link. Stop and app closure do not erase saved settings. Scan its Wi-Fi QR code using the joining device’s camera or Wi-Fi settings, then pair in Shared match.
- Android custom Wi-Fi links require Android 10 or later and a DIRECT-xy prefix; the app adds DIRECT-ST- when needed. Windows support depends on the Wi-Fi adapter and driver. Browsers can join Wi-Fi but cannot create an access point.
- The Cable/offline setup button has been removed. Existing cable network connections can still carry pairing, stats and video.
- Extract source into a short folder such as C:\ST410 to avoid Windows Explorer path-length errors.

## Features retained from 4.0.37

- Basketball records SCC player actions by jersey number. Select **Logging jersey** before recording an action. Conversions and incompletes retain the original jersey. Assisted conversions ask for a different assisting jersey. Opposition and time controls remain team-level.
- **Account → Basketball team jerseys**, or **Team jerseys** beside the selector, lets Owner/admin/user accounts manage teams. Coaches manage only their assigned basketball team and retain read-only match access. Numbers are 0–9999. Remove hides the jersey; adding that number again restores it and preserves history. Player summaries appear in match stats, saved match views and basketball exports.
- Load and save the roster once online. Its saved copy remains usable offline; offline changes are marked pending. Reopen Team jerseys and Save online to upload. A conflicting roster edit must be reloaded before saving. Creating a basketball match uses the roster saved on that device; open Team jerseys and Save to load a newer roster into an existing match.
- Shared-match assignments now include **All jerseys** or specific jerseys, alongside the section and individual-stat choices. The host enforces these assignments. Other devices can still view all match stats. The host manages the active shared-match roster.
- Pass types (including crosses and goalkeeper distributions) and dribbles have been removed from new logging controls and current stat lists. Existing event history remains readable and importable.

### Create the Wi-Fi link inside Stat Tracker

In the installed Windows or Android app, open **Shared match → Device Wi-Fi link**. Enter your network name and password, press Start / apply changes, and grant Android's nearby-device/location permission if requested. Join the displayed network name with its password on the other devices. Then host the match in Shared match, find it on the joining device, press Connect and approve it on the host. Connection codes are the fallback. No internet is required for the local match or video connection.

Use **Device Wi-Fi link → Stop Wi-Fi link** to stop it. The connection is owned by the running app and ends when the app closes. Do not start another hotspot/Feem/Zapya group at the same time. Creating a link can disconnect the current Wi-Fi. Wi-Fi Direct support depends on the adapter, driver and Android device; unsupported hardware shows an error. Browsers and iOS/iPadOS join an existing Wi-Fi network and do not create one through this control. The native code has been compiled and its bridge checked; real-device Wi-Fi connection and video testing is still required.

### Deployment order for this release

1. Deploy the server first. The workflow applies `server/rosters-migration.sql` without replacing existing matches or accounts.
2. Deploy the web app, then install the new Windows/Android builds on participating devices.
3. Refresh saved offline websites to cache this version. All shared-match devices should run the same version.

For a Windows source build, compile both `installer/build-local-sharing.cmd` and `installer/build-wifi-point.cmd` from the Visual Studio x64 Native Tools prompt before packaging. The Wi-Fi helper uses C++20 and the Windows SDK.

## Existing sharing features

Feem and Zapya provide the Wi-Fi network; match sharing runs inside Stat Tracker using invitation/reply pairing. On Windows, Enable local sharing remains available to allow the running app on your selected local network. It ends when sharing or the app closes.

### Offline browser sharing

1. While online, open the HTTPS website. In Shared match, choose **Save website for offline use**, then **Save this version**. Wait for confirmation on each browser. Sign in and open/create the match before disconnecting; keep the app tabs open.
2. Connect devices to the same Wi-Fi, Feem, Zapya or hotspot. Open Shared match in an installed app to provide the local directory. Windows may require Enable local sharing for that network.
3. Choose **Host this match** on the hosting app or browser. On joining devices choose **Find shared matches**, then **Connect**. Allow the browser's local-network permission. Approve the joining device on the host and assign its controls.
4. If a browser cannot find the directory, enter the address displayed by the installed app under **Browser / network connection**. Normal browsers cannot broadcast discovery. Some browsers block local HTTP access; use codes in those browsers.
5. Without a reachable directory, expand **Connection codes (fallback)**. The host chooses **Create invitation** and **Copy**. The joining device pastes it and chooses **Join: create reply**, then returns its reply. The host pastes that reply and chooses **Host: accept reply**. Approve the device as usual.
6. Pair each additional device separately, up to eight. The assigned camera device starts its camera explicitly. Keep tabs visible and devices awake.

The network must allow devices to communicate. If a connection does not recover, leave and pair again. Browser-only offline sessions use codes; automatic pairing requires an installed app directory. No internet is used for the directory or the shared connection.

Saving caches website files, not sign-in responses. Browser storage can be cleared by the device: test loading the saved site without internet before leaving, and save again after updates. Sign in before going offline; this feature does not add offline account authentication. Camera access requires the saved HTTPS site or localhost, not ordinary HTTP on another device. Physical Windows/Android/Apple camera and cross-device testing remains necessary; the automated Chrome video test uses generated frames.

## Stream-only devices

Host a shared match, approve the other device, then choose **Assign controls → Stream only** for that device. This also selects it as the shared camera and removes its stat and timer permissions. The device displays the dedicated camera layout and taps **Start streaming** when ready. All other approved devices receive its feed. The standalone Camera Mode and its separate connection flow have been removed.

Only one device shares video at a time. Selecting another sender takes the old stream-only device back to the match with no stat permissions; assign its sections if it should log stats. A stream-only device cannot control time. Update every participating device to this release.

## Changes

- Device stat assignments now support any combination of Attack, Defense, Cards and Opposition, with individual stats ticked within those sections. A device can also control video and the entire time-control section (including turnover and substitution). Only one device controls time at once.

- The host can independently assign the shared camera and match timer to approved devices from Shared match > Device sharing video / Device controlling time > Save device assignments. Both default to the host. The selected camera device must turn on its camera; all other devices receive its video, including the host. Timer handovers pause the clock so the new controller can start it deliberately. Removing or leaving an assigned device restores that role to the host. If a device disappears without leaving, use these selectors to take back control; the remote clock stops advancing after its heartbeat expires.
- Shared-match video now applies the same 1080p capture target, up-to-8 Mbps sender budget and resolution preference as regular streaming. Hardware and network capacity still determine actual quality; each viewer uses a separate connection.

### Retained from v4.0.33

- Hockey full-screen landscape now uses full-width buttons in a scrollable sidebar for Attack, Defense, Cards and Opposition. The old layout squeezed six buttons into the narrow sidebar and hid their labels. Normal and portrait layouts keep their wider grids.
- Email-code sign-in and email sign-in enrollment controls are removed. The sign-in choices are Password and Authenticator app. Email addresses remain the account identifier and profile contact.

### Retained from v4.0.32

- Windows has **Enable local sharing** with a USB/Ethernet/Wi-Fi network selector. It supports other devices on that selected local subnet, including USB adapters Windows classifies as Public. Windows asks for administrator approval each time it is enabled.
- Access is restricted to the running app, the selected adapter/subnet, the active match TCP port, and UDP discovery/video. It ends on End sharing, Disable local access, app exit, or helper exit/crash. Windows Filtering Platform dynamic sessions remove the filters automatically; no persistent firewall rule is installed. Existing firewall rules created outside this feature are not changed.
- SMS sign-in and SMS enrollment controls have been removed. Password and authenticator sign-in remain in the interface.

### Included from the previous release

- Hockey (outdoor hockey with the spherical ball) has its own Attack, Defense, Cards and Opposition actions. Includes short/long passes, dribbles, crosses, circle entries, shots, goals, assists, free hits, penalty corners, penalty strokes, long corners, side-line restarts, tackles, interceptions, blocks, saves, clears, ball recoveries and green/yellow/red cards.
- Hockey incompletes modify the original action in its own sequence. Shot followed by Conversion adds one goal; Shot against followed by Conversion adds an opponent goal. Conversion does not automatically add an assist. Penalty awards do not add goals. Goals can also be entered directly; do not record both a direct Goal and a conversion for the same goal.
- Hockey counts/rates, comparisons, dictionary and TXT exports use Hockey data. Historical score offsets are preserved when new Hockey actions are added. Match timing remains manually controlled for school competition variations.
- New match and coach choices show Soccer, Hockey and Basketball only. Older saved matches for other sports are retained.
- Basketball dictionary is reduced to twelve short entries describing current controls, scoring and rates. Removed scoring-context/player controls are no longer explained.
- All TXT exports default to the match title, such as `St Charles College vs Hilton.txt`. Invalid filename characters are replaced; the save dialog still permits renaming.
- Browser sharing uses local-network permission where the browser supports it. Automatic discovery requires a Stat Tracker directory service on the Wi-Fi network; browser-hosted matches can be paired with invitation/reply codes.

## Web release

Stat Tracker is distributed as a browser app. There are no Windows or Android download links in the release page. Commit and push the source, then run **Deploy web build** in GitHub Actions and refresh the website after the workflow succeeds. Deploy the server first only when a server change is part of the release.

## Offline match and video sharing

Sign in while online first. Save the website for offline use before disconnecting the internet. Keep each browser tab open during the match.

1. Connect every device to the same local network (Wi-Fi, Feem, Zapya or a hotspot).
2. On the host, open the match and choose **Shared match → Host this match**.
3. Transfer the entire invitation to one joining device through a local messenger/file transfer or shared clipboard. Paste it into Shared match and press **Join: create reply**.
4. Return that reply to the host, paste it, and press **Host: accept reply**. Approve the joining device and assign its sections, stats and jerseys.
5. Repeat with a fresh invitation for each additional device. The host can assign video, time and stream-only roles through Match controls.

All approved devices receive the shared stats and selected video. Changes to permissions are enforced by the host. Hidden/normal account separation remains enforced. Wi-Fi QR codes join the network; they do not replace match approval or the invitation/reply exchange.

### Cable setup

- **Android to computer:** connect a data-capable USB cable, enable USB tethering in Android settings, then use the sharing flow above. Phone/driver support varies. Some phones require mobile data enabled to activate tethering even though match traffic is local.
- **iPhone/iPad to computer:** USB Personal Hotspot depends on Apple/cellular-service support. Windows requires Apple Devices or iTunes and device trust. It is not a guaranteed fully offline USB network. Native Stat Tracker for iOS is still preparation only.
- **Ethernet:** supported USB-to-Ethernet adapters can connect devices to a local router/switch. Local IP addresses are required; internet is not. The same invitation/reply pairing is used over Ethernet.
- A normal USB cable between two computers or two phones generally does not create a network. This release cannot enable unsupported operating-system tethering or turn a charging-only cable into a data connection.
- Network client isolation or operating-system firewalls can block peer connections. Allow the app/browser on your trusted local network if Windows prompts. The app’s older HTTP discovery interface is no longer the normal connection flow.

Shared-match data and video use local WebRTC connections. Cloud sign-in and sync still require internet. Browser support and camera access depend on the browser’s secure-context permissions and offline site preparation.

References: [Android USB tethering](https://support.google.com/pixelphone/answer/2812516), [Apple USB hotspot requirements](https://support.apple.com/en-ca/guide/iphone/iph45447ca6/ios), [FIH hockey rules](https://www.fih.hockey/about-fih/official-documents/rules-of-hockey). School competition timing and card decisions follow the applicable competition and umpire.

## Accounts and server maintenance

The existing Cloudflare Worker and D1 database remain configured under `server`. Keep the existing database ID. Routine client releases do not require creating a new database. Account roles, hidden activity separation and coach read-only access remain unchanged.

For server changes, use the existing **Deploy account and sync server** workflow. Keep secrets in GitHub Actions/Cloudflare secrets, never in source or release notes. Password and enrolled authenticator sign-in remain available. Email-code and SMS sign-in have been removed from this client; Auth0 sign-in remains removed from the user interface, and Microsoft sign-in is not included.

## Verification and practical limits

213 Python checks passed for 4.0.39. The unchanged server and native transport had 75 server and 13 Flutter checks pass in 4.0.38. Browser checks verified clipboard copying, the unified sharing panel, browser host advertisement through the local directory, and jersey attribution with an incomplete. The saved website also launched as v4.0.39 in Chrome with network access disabled. A previous Chrome transport test passed offer/reply pairing, fragmented match transfer and synthetic video delivery without a signaling server. Automated checks cover role assignment, unauthorized commands, camera signalling to the host and guests, timer handovers, disconnect handling, and existing app behavior. Physical multi-device camera quality and handovers must still be checked on your Windows and Android devices.

Physical cable-connected multi-device video and phone-specific tethering have not been verified for this release. iOS builds and physical Apple hardware testing remain pending. Before relying on sharing at a match, test your intended host/guest devices and cable or adapter with internet disconnected: approval, simultaneous logging, clock pause, video and reconnect.

## iOS and iPadOS preparation

In GitHub Actions, run **Prepare iPhone and iPad build**. Choose `ios-simulator` to build an unsigned simulator app without an Apple Developer account, or `ipa` to prepare an unsigned device archive for later signing. This workflow runs on a GitHub macOS runner; Windows cannot compile the Apple app. The workflow is prepared but has not been run from this workspace.

- Upload the source with its `.github`, `scripts` and `packages` folders. Choose your own reverse-domain bundle ID; `com.example.stattracker` is only a testing placeholder.
- Download the resulting workflow artifact. For the simulator, extract its tar archive on a Mac with Xcode, start an iPhone or iPad simulator, and run `xcrun simctl install booted /absolute/path/Runner.app` (use the actual app name). Test portrait, landscape, match creation, logging and comparisons.
- The workflow checks Camera and Local Network descriptions, private-IP transport exceptions, and support for both device families and orientations. It preserves bundle symbolic links when packaging.
- An unsigned `.xcarchive` is not installable on a physical device. When ready, enroll in the Apple Developer Program, register the same bundle ID, configure a signing certificate/profile in Xcode, and distribute through TestFlight. Do not send signing keys or passwords in chat.
- Test camera capture, shared-match approvals, timer/video assignments and offline reconnect on physical iPhone/iPad hardware. Keep the host and video sender foregrounded and grant Camera and Local Network permissions. Simulator checks do not prove hardware streaming works.
- Broadcast discovery on iOS needs Apple's multicast entitlement. Until approved and configured for a signed build, use the unicast scan or manual host address. The source already limits local HTTP to private/link-local addresses; cloud sign-in remains HTTPS.
- A Feem-created hotspot is simply a local network for Stat Tracker. Apple USB Personal Hotspot is not guaranteed to work without cellular support; a local Wi-Fi network or supported Ethernet adapters are the reliable preparation targets.

The web app remains available in Safari, but the native local host/join feature requires the installed Apple build. No iOS installer or successful macOS build is claimed in this preparation package.

References: [Flet Apple builds](https://flet.dev/docs/publish/ios/), [Apple local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy).

## Windows helper build

The source package includes `assets/local-sharing.exe` and its source at `installer/local-sharing.cpp`. To rebuild it, run `installer\build-local-sharing.cmd` from a Visual Studio x64 Native Tools prompt before building the Windows app. Keep the helper beside the other packaged assets. The helper requests no elevation until the user selects Enable local sharing.

The dynamic session lifecycle is documented by [Microsoft Windows Filtering Platform object management](https://learn.microsoft.com/en-us/windows/win32/fwp/object-management). A stopped helper cannot leave these dynamic filters behind. This does not remove existing firewall exceptions configured by Windows or an administrator.

## Sign-in options

This release offers Password and Authenticator app sign-in. Email addresses remain account identifiers and profile contacts. Email-code and SMS sign-in/enrollment are removed from the client. Legacy server delivery endpoints remain for older clients; the 4.1.0 roster reset requires deploying the server migration described above.

### Apple local-network preparation

The source includes local-network access descriptions and private/link-local IPv4 ATS exceptions. iOS/iPadOS 17 supports these IP ranges. Broadcast discovery additionally requires Apple's multicast networking entitlement in a signed app; request/configure it before distribution. Without it, use the existing unicast scan or manual host address. These settings do not replace signing or physical iOS testing.

References: [Apple local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy), [Apple IP-address exceptions](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsexceptiondomains).
