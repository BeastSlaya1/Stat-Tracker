# Stat Tracker 4.0.29

## Changes
- Download page says “Sign-in required”.
- Basketball statistics show currently supported logging metrics and percentage/rate calculations. Retired scoring-context, player-only and opponent totals are omitted. Zero counts remain visible. Historical data is preserved.
- Match comparison checkboxes update results in place, preserving the dialog and statistics selector.
- Scan for shared matches finds discoverable hosts on the same private Wi-Fi/hotspot. Select a result, enter its join code, then request host approval.

## Upload through GitHub
1. Upload the source archive contents to your repository, including .github.
2. Run Deploy web build to update the browser app and download page.
3. Create release v4.0.29 with the Windows installer and Android APK (build 30).

No server migration or server deployment is required for these changes.

## Nearby discovery
Update both host and guest apps. Hosts use TCP ports 8767–8770 when available. If those ports are occupied, the host uses another port and guests must enter its address manually. Scanning checks up to four private /24 networks on the device. Some networks block device-to-device traffic; allow the app on Windows private networks and use manual entry for unusual network layouts. Discovery exposes only match name and sport, never join codes. Hidden sessions do not appear in scans. Joining always requires the code and host approval. Local sharing is available in installed apps, not the browser app.

## Validation
139 Python regression tests passed, plus an additional discovery-selection test. Browser checks passed for retained logging scroll, portrait layout, Opposition scoring and multiple comparison selections without closing or moving the selector. Physical-device discovery and camera sharing still need testing on your Wi-Fi/hotspot. iOS remains source preparation only; see IOS-SETUP.md.
