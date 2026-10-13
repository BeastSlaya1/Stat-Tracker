# Stat Tracker v4.0.32 — setup and release guide

This is the single guide for this release. Existing local notes are not needed in the new source package. Android and Windows use build 35.

## Changes

- Windows has **Enable local sharing** with a USB/Ethernet/Wi-Fi network selector. It supports other devices on that selected local subnet, including USB adapters Windows classifies as Public. Windows asks for administrator approval each time it is enabled.
- Access is restricted to the running app, the selected adapter/subnet, the active match TCP port, and UDP discovery/video. It ends on End sharing, Disable local access, app exit, or helper exit/crash. Windows Filtering Platform dynamic sessions remove the filters automatically; no persistent firewall rule is installed. Existing firewall rules created outside this feature are not changed.
- SMS sign-in and SMS enrollment controls have been removed. Password, authenticator and email sign-in remain in the interface.

### Included from the previous release

- Hockey (outdoor hockey with the spherical ball) has its own Attack, Defense, Cards and Opposition actions. Includes short/long passes, dribbles, crosses, circle entries, shots, goals, assists, free hits, penalty corners, penalty strokes, long corners, side-line restarts, tackles, interceptions, blocks, saves, clears, ball recoveries and green/yellow/red cards.
- Hockey incompletes modify the original action in its own sequence. Shot followed by Conversion adds one goal; Shot against followed by Conversion adds an opponent goal. Conversion does not automatically add an assist. Penalty awards do not add goals. Goals can also be entered directly; do not record both a direct Goal and a conversion for the same goal.
- Hockey counts/rates, comparisons, dictionary and TXT exports use Hockey data. Historical score offsets are preserved when new Hockey actions are added. Match timing remains manually controlled for school competition variations.
- New match and coach choices show Soccer, Hockey and Basketball only. Older saved matches for other sports are retained.
- Basketball dictionary is reduced to twelve short entries describing current controls, scoring and rates. Removed scoring-context/player controls are no longer explained.
- All TXT exports default to the match title, such as `St Charles College vs Hilton.txt`. Invalid filename characters are replaced; the save dialog still permits renaming.
- Offline sharing discovers active USB/Ethernet interfaces as well as Wi-Fi. Local broadcast discovery supplements the bounded address scan, including automatically assigned Ethernet addresses.

## Files and GitHub upload

The release bundle contains the Windows installer, Android APK, source ZIP, this guide and checksums. It contains no account passwords, private service keys or signing keystores.

1. Extract `Stat-Tracker-4.0.32-Source.zip` into your repository checkout. Keep its folders, especially `.github`, `packages`, `assets`, `server` and `web-downloads`. Do not flatten the files.
2. Commit and push through GitHub Desktop or your normal GitHub process.
3. Run **Deploy web build** in GitHub Actions to update the website. Refresh the site after the workflow succeeds.
4. Create release/tag `v4.0.32` and upload `Stat-Tracker-Windows-4.0.32-Setup.exe` and `Stat-Tracker-Android-4.0.32.apk` with those exact names.
5. Update every device taking part in a shared match. This release needs no new account-server migration or server deployment.

The Windows installer supports current-user/all-users installation and app-data cleanup on uninstall. The Android APK uses the existing signing certificate so it can update prior builds; its build number is 35. This is a direct-install APK, not a Play Store production signing setup.

## Offline match and video sharing

Sign in while online before using the app offline. Use installed apps, and keep the host app open in the foreground. Browsers cannot host or join this local sharing service.

1. Put the devices on the same local network (Wi-Fi/hotspot, USB tethering or Ethernet).
2. On the host, open the match in Inputter Mode and choose **Shared match → Host this match**. On Windows, select the connected USB/Ethernet/Wi-Fi network, click **Enable local sharing** and approve the Windows prompt. Turn on the match camera. Windows guests can use the same setup to receive video.
3. On each other device, choose **Shared match → Scan for shared matches → Connect to this match**.
4. The host chooses Attack, Defense, Cards, Opposition or All. Expand individual stats and tick the actions assigned to that device, then approve.
5. The guest joins automatically. All approved devices see all stats and the host video. The host controls camera, clock and possession; guests log only assigned stats. Conversions and incompletes follow their parent action.

Use **Assign controls** to change permissions later. If a device has queued actions when permissions change, restore the relevant permission so those actions can sync. Hidden matches remain undiscoverable and use manual address/code plus approval. Hidden/normal account separation remains enforced.

### Cable setup

- **Android to computer:** connect a data-capable USB cable, enable USB tethering in Android settings, then use the sharing flow above. Phone/driver support varies. Some phones require mobile data enabled to activate tethering even though match traffic is local.
- **iPhone/iPad to computer:** USB Personal Hotspot depends on Apple/cellular-service support. Windows requires Apple Devices or iTunes and device trust. It is not a guaranteed fully offline USB network. Native Stat Tracker for iOS is still preparation only.
- **Ethernet:** supported USB-to-Ethernet adapters can connect devices to a local router/switch. Local IP addresses are required; internet is not. For automatic link-local addresses, use discovery or the exact host address if discovery is blocked.
- A normal USB cable between two computers or two phones generally does not create a network. This release cannot enable unsupported operating-system tethering or turn a charging-only cable into a data connection.
- Use **Enable local sharing** on Windows, including for a USB network labelled Public. Re-enable it after changing networks or starting a host on a different port. The temporary access requires administrator approval; managed-device policy can prevent it. If scanning fails, use **Manual connection** with the displayed host address and join code. Network client isolation can block both discovery and connections.

Local match coordination uses authenticated HTTP on the trusted local network; video uses WebRTC. Cloud sign-in/sync continues to use HTTPS. Do not expose the sharing ports to the internet.

References: [Android USB tethering](https://support.google.com/pixelphone/answer/2812516), [Apple USB hotspot requirements](https://support.apple.com/en-ca/guide/iphone/iph45447ca6/ios), [FIH hockey rules](https://www.fih.hockey/about-fih/official-documents/rules-of-hockey). School competition timing and card decisions follow the applicable competition and umpire.

## Accounts and server maintenance

The existing Cloudflare Worker and D1 database remain configured under `server`. Keep the existing database ID. Routine client releases do not require creating a new database. Account roles, hidden activity separation and coach read-only access remain unchanged.

For server changes, use the existing **Deploy account and sync server** workflow. Keep secrets in GitHub Actions/Cloudflare secrets, never in source or release notes. Password and enrolled authenticator sign-in remain available. Email provider setup remains optional; SMS sign-in has been removed from this client; Auth0 sign-in remains removed from the user interface, and Microsoft sign-in is not included.

## Verification and practical limits

173 automated tests passed, including temporary-access handle cleanup, helper exit detection, selected-network/host-port handling, SMS removal and existing shared-match behavior. The Windows C++ helper compiled successfully. Its public/loopback/invalid-address rejection was exercised without changing the firewall. The v4.0.32 web build started successfully and its sign-in dropdown showed Password, Authenticator app and Email code, with SMS absent. The packaged Windows app also started successfully with isolated empty test data. Earlier browser checks covered Basketball scroll preservation and Hockey layouts.

The new elevated filters and their lifecycle still need a live Windows/Android cable test. The tablet was disconnected during this update, so physical cable-connected multi-device video and phone-specific tethering have not been verified here. iOS builds and physical Apple hardware testing remain pending. Before relying on sharing at a match, test your intended host/guest devices and cable or adapter with internet disconnected: approval, simultaneous logging, clock pause, video and reconnect.

## iOS preparation

The repository includes the unsigned **Build iPhone and iPad archive** workflow. It is preparation for a future Apple Developer account and a macOS build, not an installable iPhone release. Configure your own Apple bundle ID and signing/team details before TestFlight or App Store distribution. Grant Camera and Local Network permissions when testing. The native iOS work targets iOS/iPadOS 17 or later; keep the host foregrounded.

The web app remains usable on Safari with an internet connection, but local native match hosting/joining is not available through the browser.

## Windows helper build

The source package includes `assets/local-sharing.exe` and its source at `installer/local-sharing.cpp`. To rebuild it, run `installer\build-local-sharing.cmd` from a Visual Studio x64 Native Tools prompt before building the Windows app. Keep the helper beside the other packaged assets. The helper requests no elevation until the user selects Enable local sharing.

The dynamic session lifecycle is documented by [Microsoft Windows Filtering Platform object management](https://learn.microsoft.com/en-us/windows/win32/fwp/object-management). A stopped helper cannot leave these dynamic filters behind. This does not remove existing firewall exceptions configured by Windows or an administrator.

## Optional email sign-in

Email delivery remains prepared but disabled until a compatible provider is configured. Password and enrolled authenticator sign-in can be used now. Email code sign-in still requires any enabled authenticator second step. Profile phone fields are retained as contact information. The legacy server SMS endpoints are retained for older clients, but this release exposes no SMS sign-in or enrollment option.

### Apple local-network preparation

The source includes local-network access descriptions and private/link-local IPv4 ATS exceptions. iOS/iPadOS 17 supports these IP ranges. Broadcast discovery additionally requires Apple's multicast networking entitlement in a signed app; request/configure it before distribution. Without it, use the existing unicast scan or manual host address. These settings do not replace signing or physical iOS testing.

References: [Apple local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy), [Apple IP-address exceptions](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsexceptiondomains).
