# Website downloads and iPhone/iPad build

These changes preserve the existing GitHub Pages deployment and custom domain.
Cloudflare can continue to provide DNS/proxying. The app gains a Get the app link
and the workflow publishes web-downloads/ at https://stattrackerv4.stream/downloads/.

## Publish Android and Windows

1. Test the two 4.0.1 installers on your devices first.
2. In BeastSlaya1/Stat-Tracker, create a GitHub Release tagged `v4.0.1`.
3. Attach `Stat-Tracker-Android-4.0.1.apk` and
   `Stat-Tracker-Windows-4.0.1-Setup.exe` from the delivered files.
4. Publish the release. The download page verifies the release asset names and
   file sizes before enabling the links. Keep these names unchanged.
5. Upload/merge these website changes to main. The existing deployment workflow
   includes the downloads page. Do not upload the installers into the repository
   or the website build; they belong in Release attachments.

A missing release produces Not yet published instead of broken download links.
If GitHub is unavailable or rate-limits the visitor, the page links to Releases.
No access tokens or credentials are used in the public download page.
These are development/test builds: Android uses the original debug certificate;
Windows is not Authenticode-signed. Establish production signing before a broad
public release. Preserve the Android signing key for compatible future updates.

## iPhone / iPad

The `mobile/ios` folder contains the port and its limitations. The manual
**Build iPhone and iPad archive** workflow runs on a hosted Mac and produces an
unsigned archive, not an installable IPA. It has not been run remotely yet.
Apple signing and physical-device validation are still required. Use a registered
bundle ID rather than the example before distribution. See mobile/ios/README.md.

Keep the website button at Coming soon until an actual TestFlight public invite
or App Store URL exists. Then set `appleUrl` in `web-downloads/config.js` to that
URL and deploy. A raw IPA download is not a general iPhone installation method.

## Review / validation

This checkout is a local proposal. No repository changes, releases, or live-site
updates have been published. Run `node --test tests/downloads.test.cjs` for link
validation. The iOS camera source passed 12 Flutter tests and static analysis in
Windows; Xcode compilation and physical-device behavior remain unverified.
