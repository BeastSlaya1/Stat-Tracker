# Building Stat Tracker as .apk and .exe

> ⚠️ **If you've built before and things seemed missing or broken** (e.g.
> a Windows build reporting "opencv-python not installed"): a file named
> exactly `requirements.txt` used to sit in this project. Flet's own docs
> confirm that if that file exists, `flet build` reads dependencies from
> it *instead of* `pyproject.toml`, on every platform — silently
> defeating the per-platform dependency split described below. That file
> is gone now (renamed to `requirements-dev.txt`, which `flet build`
> ignores). **Run `flet clean` once, then rebuild both platforms** — this
> single fix likely affected every build so far, Android included (that
> file also unconditionally listed `opencv-python`, which has no Android
> wheel at all, so an in-progress/hung Android build may be a symptom of
> this too).

Building native installers requires the Flutter SDK, an Android SDK/toolchain,
and (for Windows) a Windows machine or the Windows build tooling — none of
which are available in this chat environment, so I can't produce the actual
`.apk`/`.exe` files here. What I *have* done is update the app itself so it's
fully ready to build: new logo, new animated splash screen, and everything
else identical between platforms since it's the same Flet codebase (this is
what gives you automatic Android/Windows parity — one UI, two targets).

Run the commands below on your own machine (or ask me to do it via Claude
Code / Claude Desktop, which does have full computer + toolchain access).

## 1. One-time setup

```bash
pip install flet==0.86.5 opencv-python matplotlib numpy
```

**For the Android build**, also install:
- [Flutter SDK](https://docs.flutter.dev/get-started/install) (`flutter doctor` should pass)
- Android SDK + a platform + build-tools (Android Studio's SDK Manager is the
  easiest way to get these)
- A JDK (17 is a safe choice)

**For the Windows build**, run it on Windows with:
- [Flutter SDK](https://docs.flutter.dev/get-started/install) for Windows
- Visual Studio 2022 with the "Desktop development with C++" workload

`flet build` downloads and drives Flutter under the hood, so most of the
heavy lifting is automatic once those prerequisites are in place.

## 2. Build Windows (.exe)

From the `stat_tracker_v4` folder, on a Windows machine:

```cmd
flet clean
flet build windows --project "Stat Tracker"
installer\fix_opencv_config.bat
```

That third command is **required, every time** — see below for why. Skip
it and the camera will fail with a confusing "opencv-python not
installed" error even though it genuinely is installed.

Output lands in `build/windows/Stat Tracker.exe`.

### Root cause, finally confirmed: OpenCV's own config-file loader

`cv2/__init__.py` doesn't use Python's normal import system for two tiny
internal config files (`config.py`, `config-3.py`) — it manually checks
for those literal filenames on disk and executes their raw source text.
`flet build` compiles every `.py` file in the app to `.pyc` and deletes
the original `.py` source (completely invisible for regular application
code, which imports normally either way) — but it breaks this one
specific OpenCV loading mechanism, which needs the actual `.py` text
files physically present. Without them, `import cv2` raises:
```
OpenCV loader: missing configuration file: ['config.py']. Check OpenCV installation.
```
— even though the real OpenCV binary (`cv2.pyd`, ~86MB) is completely
intact. This was confirmed by fetching OpenCV's actual loader source and
matching it exactly against the real error message once diagnostic
messages stopped hiding it.

`installer\fix_opencv_config.bat` copies just those two small text files
(a few lines each — not any actual binary/DLL) from your local working
`opencv-python` install into the build output after every build. It's a
one-time annoyance per build, not a deep problem — but it must be run
every single time `flet build windows` runs, since a fresh build always
recreates the same missing-`.py`-file situation.

### Resolved: "opencv-python not installed" in the built `.exe`

This turned out to be the `requirements.txt`-overrides-`pyproject.toml`
issue explained in the warning at the top of this file, confirmed by the
exact on-screen error text once it stopped being silently swallowed:
`opencv-python not installed. Run: pip install opencv-python`. Not a DLL
bundling problem, not a Windows camera-privacy problem — `opencv-python`
genuinely wasn't part of that build's dependency list at all, because a
`requirements.txt` file's mere presence was making `flet build` skip
`pyproject.toml`'s per-platform dependencies entirely. Fixed by removing
that file (see the warning banner up top). If you still see this exact
error after a `flet clean` + rebuild with the current project files,
that would point at something new — send me the message and I'll dig in.

## 3. Build Android (.apk)

From the `stat_tracker_v4` folder:

```bash
flet build apk
```

Output lands in `build/apk/app-release.apk`.

### Camera parity — now implemented natively (no OpenCV on mobile)

The app no longer needs OpenCV on Android/iOS at all:

- **Desktop (Windows/macOS/Linux)**: local webcam capture still uses
  `cv2.VideoCapture` (unchanged) — OpenCV installs fine there.
- **Android/iOS**: local on-device camera capture now uses the
  [`flet-camera`](https://pypi.org/project/flet-camera/) package (added to
  `requirements-dev.txt`), which talks to the native camera APIs directly.
  There's a front/back toggle on the Logger tab's camera source picker in
  place of the desktop's device-index chips. No OpenCV involved.
- **Wireless/IP camera & paired Camera Mode devices (any platform)**: this
  path was quietly re-implemented as a small pure-Python MJPEG reader
  (`_mjpeg_url_pull_loop` in `main.py`, using only `urllib`) instead of
  `cv2.VideoCapture(url)`. It behaves identically but now also works on
  Android, since it never touches OpenCV.

`opencv-python` is still listed in `requirements-dev.txt` because the desktop
build needs it; it simply won't be importable/used on an Android build,
which is fine since that code path is never reached there.

**One thing to verify on a real device once you have the APK built:**
`flet-camera`'s `on_stream_image` streaming path (used so the same device
can also broadcast to another Inputter device in Camera Mode) hasn't been
exercised on real Android/iOS hardware in this environment — I don't have
a phone or emulator here to test against. The desktop OpenCV path and the
MJPEG pure-Python reader were both testable and are unchanged/robust; the
native-camera code is new and worth a first real-device smoke test (turn
camera on, confirm the Logger tab shows a live feed, then try Camera Mode
→ Start Streaming → connect from a second device).

## 4. Give the app a name/identifier (optional but recommended)
```bash
flet build apk --project "Stat Tracker" --org com.yourname.stattracker
flet build windows --project "Stat Tracker"
```

## 4a. Real Windows installer (new) — instead of handing out a zip

Android already behaves like a normal app the moment the `.apk` is
installed — it shows up in Settings → Apps and uninstalls the regular
way, nothing more to do there. Windows was the one that needed this:
`build\windows\` is just a loose folder (the `.exe` plus a pile of DLLs
it depends on) with no installer, no Start Menu entry, and no proper
uninstall — this section turns that into a real installer using
[Inno Setup](https://jrsoftware.org/isdl.php) (free).

1. **Build the app first**, same as always:
   ```cmd
   flet clean
   flet build windows --project "Stat Tracker"
   installer\fix_opencv_config.bat
   ```
   That third command matters here too — the installer just packages
   whatever's in `build\windows\`, so the camera config-file fix (see
   section 2 above) needs to happen before compiling the installer, not
   just before testing the raw `.exe`.
2. **Install Inno Setup** (one-time): download and run the installer from
   the link above. Inno Setup 7 ships as separate 32-bit and 64-bit
   editions — either is fine, they both produce the same kind of installer.
3. **Compile the installer script** — either open
   `installer\StatTracker.iss` in the Inno Setup Compiler (the IDE it
   installs) and press Compile (Ctrl+F9), or from the command line. The
   exact path to `ISCC.exe` varies depending on how Inno Setup was
   installed — a per-user install (no admin needed) lands somewhere like:
   ```cmd
   "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" installer\StatTracker.iss
   ```
   while a per-machine install lands under Program Files instead:
   ```cmd
   "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" installer\StatTracker.iss
   ```
   If neither works, find it directly: `where /r C:\ ISCC.exe`.
4. **The result**: `installer\Output\StatTracker-Setup.exe`. *That single
   file* is what you hand to someone — this is the actual deliverable now,
   not a zip. Running it gives a normal Windows install wizard: license/
   next/next, an optional desktop shortcut checkbox, a Start Menu entry,
   and — the actual point of all this — it shows up properly in
   **Settings → Apps → Installed apps**, with a real Uninstall button,
   exactly like Teams or any other installed application.

The script (`installer\StatTracker.iss`) is fully commented — the only
line you'd realistically ever need to touch is `MyAppVersion` when you
cut a new release. It packages everything from `build\windows\` as-is
(the `.exe`, its DLLs, `Lib`, `site-packages` — the works), installs into
Program Files, and registers a proper uninstaller automatically.

**One important related fix**: match data now saves to
`%LOCALAPPDATA%\Stat Tracker\` instead of next to the app's own files.
That had to change for this to work at all — a properly-installed app
lives in Program Files, which normal (non-admin) use can't write to, so
saving next to the exe would have silently failed every time under a real
install. This also means an uninstall never touches saved match history,
and reinstalling/updating the app picks the same data back up
automatically. See `_data_dir()` in `storage.py` if you want to change
this behavior.

## 4b. Web build (new)

The app now runs as a web app too — either for quick local testing:

```bash
flet run --web main.py
```
which opens it in your browser at a local address (Flet prints the URL,
usually `http://localhost:8550`), or as a real static/hosted build:

```bash
flet build web --project "Stat Tracker"
```
which produces a static site in `build/web/` that you deploy to any static
web host (Netlify, Vercel, GitHub Pages, an S3 bucket, your own server,
etc.) or serve directly with `flet build web`'s own dev server for testing.

### Opening the web build on a phone (iOS/Android) — on its own, no PC needed

A web app always needs *something* serving it over http(s) — that's just
how browsers work, not a limitation of this app specifically. But that
something doesn't have to be a computer you keep turned on and running a
script: it can be a free, always-on host instead, and then a phone opens
the URL directly, like any other website, with nothing else involved.

**The easiest way: GitHub Pages (free, automatic, persistent HTTPS)**

This project now includes `.github/workflows/deploy-web.yml`, which
builds the web app and publishes it automatically. One-time setup:

1. Push this project to a GitHub repository (if it isn't already).
2. Repo **Settings → Pages → Source** → set to **"GitHub Actions"**.
3. Push to the `main` branch (or open the **Actions** tab and run
   "Deploy web build to GitHub Pages" manually).
4. Wait for the workflow to finish (a couple of minutes — it installs
   Flutter and runs `flet build web` the same way a local build would).
   The **Actions** tab or **Settings → Pages** will then show the live
   URL: `https://<your-username>.github.io/<repo-name>/`.

Open that URL directly in Safari (iPhone) or Chrome (Android) — that's
it. No PC needs to be on, no WiFi restriction, works from anywhere with
internet. Every future push to `main` re-deploys automatically. It's a
real `https://` address too, so the browser camera ("This Device's
Camera") works there without the self-signed-certificate warning the LAN
HTTPS option below still needs.

**Simpler alternative, no GitHub required: Netlify/Cloudflare Pages
drag-and-drop**

Run `flet build web --project "Stat Tracker" --base-url ""` locally
(empty base-url since these hosts serve from the domain root, not a
subpath), then drag the resulting `build/web` folder onto
[app.netlify.com/drop](https://app.netlify.com/drop) (no account needed
for a one-off) or a Cloudflare Pages project. You get a permanent
`https://something.netlify.app` URL immediately — open that on the
phone. Re-drag the folder any time you rebuild with changes.

**Still on the same WiFi as a PC and don't want to deploy anywhere?**
See "Still on the same WiFi as a PC" below for the local/LAN option.

### Running the built web output locally without typing commands

A built web app's `index.html` **cannot** just be double-clicked or opened
via `file://` — browsers block it from loading its own JS/wasm assets that
way (a security restriction, not a bug). It genuinely needs to be served
over `http://`, even just for local testing on your own machine.

`installer\run_web.bat` gives you a real double-click option instead:
copy that file directly into the `web` folder produced by `flet build web`
(the one containing `index.html`), then double-click it — it starts a
local server and opens your browser automatically, no commands needed.
Requires Python installed (any recent version; `python -m http.server` is
part of the standard library, nothing extra to install).

### Still on the same WiFi as a PC and don't want to deploy anywhere?

`installer\run_web_lan.bat` serves the app to other devices on the same
WiFi, not just this PC — it prints a second address like
`http://192.168.1.42:8000` that a phone on the same network can open
directly in Safari/Chrome. `is_mobile` detection (via `page.platform`)
works the same in-browser as it does in the native mobile app, so the
compact mobile layout kicks in automatically there too. This is the
PC-must-be-running, same-network option — not the "open it anywhere,
anytime" option above, but useful for quick local testing.

**Camera access needs HTTPS, though.** iOS Safari and Android Chrome both
refuse `getUserMedia` (camera) access on any page that isn't a "secure
context" — `https://`, or `http://localhost` specifically. A phone
opening `http://<LAN-IP>:8000` doesn't qualify, even on your own trusted
WiFi, so "This Device's Camera" would fail there. Use
`installer\run_web_lan_https.bat` instead for that case — same idea as
the plain LAN script, but serves over `https://<LAN-IP>:8443` using a
self-signed certificate it generates once (needs
`py -m pip install cryptography`, one time). Every browser will show a
"connection isn't private" warning the first time since the certificate
isn't from a recognized authority — that's expected; tap Advanced /
Details → proceed anyway, once per device.

### Downloads/exports and imports now work on the web build

The TXT export ("Export Report") and re-import buttons previously used
`tkinter.filedialog` — a native OS dialog that only makes sense for a
desktop app running directly on your machine. For a web deployment that
dialog would try to pop up on the *server*, not the visitor's browser,
which made it silently broken there. Both now go through `ft.FilePicker`
instead, which is Flet's actual cross-platform mechanism for this: a
native save/open dialog on desktop, a share/save sheet on Android, and —
what makes this work on web — a real browser download/upload on the web
build. No other change to what gets exported or how re-import works.

### Camera on the web build

The camera source picker on web now offers **"This Device's Camera"** —
real in-browser webcam access via the browser's own `getUserMedia` API,
using the same `flet-camera` control (and the same `"native:"` source
string) as the Android/iOS native camera path, since that control
supports `page.web` directly. It'll prompt for the browser's own camera
permission the first time. The wireless/IP-camera URL field is still
there too, for the two-device filming setup (point a phone running Camera
Mode, or any IP-camera app, at it) — useful when you'd rather film with a
phone's better camera than whatever's built into the machine running the
browser.

### Match data on the web build — no longer a shared-file concern

`flet build web` runs the whole Python app *inside the visitor's own
browser tab* (compiled to WASM via Pyodide) — there's no server-side
Python process handling multiple visitors' data through one shared file
the way that sentence implies. Match data, logger name, and app mode are
now saved into that specific browser's own `localStorage` (via
`ft.SharedPreferences`) and reloaded from there automatically next time
the same browser opens the app — private to that browser/device, the same
way desktop/mobile's file-based storage is private to that install. Two
people opening the same hosted web app won't see or overwrite each
other's data; they also won't automatically share it with each other —
each browser has its own separate copy.

## 5. Reducing app size

Two kinds of savings apply here: what's now baked into the app's own code
(done, no action needed from you), and build-command flags you can use to
shrink what Flutter packages on top of that.

### Already done in this update

- **Removed `matplotlib` + `numpy`.** They were pulled in solely to
  rasterize the Stats-tab radar chart into a PNG image. That chart is now
  drawn natively with `flet.canvas` (vector lines/shapes, no image encoding
  at all), so both dependencies are gone from `requirements-dev.txt` entirely.
  These two are easily the single biggest size win available — matplotlib
  alone drags in its own font/data files and, bundled for a mobile build,
  the pair of them can add well over 50–80MB for a feature that was one
  static chart.
- **Removed a redundant ~1.5MB asset copy.** `assets_data.py` was carrying
  a full 1024×1024 base64 copy of the app icon that nothing at runtime
  actually reads (the real `assets/icon.png` file is what
  `flutter_launcher_icons` uses at *build* time; only the small 64px badge
  and the splash image are read from `assets_data.py` while the app is
  running). Dropped the dead copy.
- **Split dependencies per platform via `pyproject.toml`.** Previously
  every build — Windows, Android, everything — read the same
  `requirements-dev.txt`, which listed both `opencv-python` (desktop-only) and
  `flet-camera` (mobile-only). Every build was pulling in a dependency it
  had no use for. `flet build` actually supports declaring dependencies
  per target platform in `pyproject.toml` (`[tool.flet.<platform>]`), so
  the app now does exactly that: Android/iOS builds get `flet` +
  `flet-camera` only, desktop builds get `flet` + `opencv-python` only.
  Neither carries dead weight (or, on Android's side, a package with no
  Android wheel in the first place) from the other platform.
  `requirements-dev.txt` still exists, but now purely for local development —
  `pip install -r requirements-dev.txt` + `python main.py` on your own
  machine — and isn't what `flet build` actually packages anymore.

### Flags worth using at build time

```cmd
:: Android — split into one APK per CPU architecture instead of one
:: universal APK containing all of them. Typically cuts the per-download
:: size roughly to a third. Good for sideloading/testing; for Play Store
:: distribution, build an .aab instead (below) and Google splits it for you.
flet build apk --project "Stat Tracker" --org com.yourname.stattracker --split-per-abi

:: Android, for Play Store — .aab lets Google Play generate an optimized,
:: per-device APK automatically (smallest possible download for each user).
flet build aab --project "Stat Tracker" --org com.yourname.stattracker
```

If you use `--split-per-abi`, you'll get several APKs in `build/apk/` (one
each for `arm64-v8a`, `armeabi-v7a`, `x86_64`). `arm64-v8a` covers virtually
every phone made in the last several years — that's the one to hand
someone for manual sideload testing unless they specifically have an older
32-bit or x86 Android device.

Flutter's release builds already enable code shrinking/minification (R8)
and don't include debug symbols by default, so there's no separate "enable
optimization" step needed beyond these flags — `flet build` always builds
in release mode.

### Windows

There's no equivalent multi-arch split for the desktop build — the `.exe`
bundles the Flutter engine plus your Python app and dependencies as one
package regardless. The dependency cleanup above still helps here too
(smaller `.exe` — matplotlib/numpy were dragging weight into the Windows
build as well, not just Android). Beyond that there isn't much more to
trim without cutting a real feature — `opencv-python` (needed for the
desktop webcam path) and `flet` itself are the two unavoidable large
pieces.

### One important step: clear the build cache once

`flet build` caches the generated Flutter project (in `build/flutter`) and
the packaged Python app to speed up repeat builds. Since the dependency
list itself changed, that cache needs to be invalidated once so the new,
smaller per-platform dependency set actually gets used — otherwise you may
still be looking at the old bundled dependencies. Run `flet clean` once
before your next build for each platform (the old `--clear-cache` flag on
`flet build` still works but is deprecated as of Flet 0.86 and will be
removed in 0.89):

```cmd
flet clean
flet build apk --project "Stat Tracker" --org com.yourname.stattracker --split-per-abi
flet build windows --project "Stat Tracker"
```

After that first clean rebuild, normal iterative builds don't need
`flet clean` — just run `flet build` directly.

## What I changed in this update

- **Fixed Camera Mode's "Control must be added to the page first" error**:
  a real regression from an earlier refactor. `_video_display_widget()`
  deliberately shows `self.camera_image` (not the native control) in
  Camera Mode, since that mode needs frame *bytes* to serve over HTTP —
  but that meant the native camera control object was never actually
  placed anywhere in the page for that mode at all, and Flet requires a
  control to be mounted before platform-channel calls work on it.
  Inputter Mode already got this for free via being placed in the visible
  tree; Camera Mode now explicitly mounts it into `page.overlay` instead
  (invisible, since Camera Mode doesn't display it directly, but present
  in the tree so the actual camera calls succeed). Verified directly:
  Camera Mode mounts into overlay, Inputter Mode does not double-mount.
- **Fixed `run_web.bat`/`run_web_lan.bat` launching Windows Script Host
  instead of Python** (`"JavaScript compilation error"` referencing a
  `python.js` file): Windows' command resolution can match a bare
  `python`/`py` against *any* extension in `PATHEXT` (`.EXE`, `.BAT`,
  `.JS`, etc.) — if a stray `python.js` exists anywhere on PATH (e.g. a
  leftover from a since-removed tool), a bare name lookup can find and
  run that instead of a real Python install, silently handing off to
  Windows Script Host. Both scripts now check for `py.exe`/`python.exe`
  explicitly, which can't match a non-executable file by name alone.

- **Fixed a real race condition causing `ConcurrentModificationError`
  during iteration: Instance(length:0) of '_GrowableList'`** (a Dart/
  Flutter runtime error, not a Python one). Root cause: switching camera
  lens (Front/Back) while the camera was already on called
  `_stop_camera()` then `_start_camera()` back to back — but
  `_stop_camera()`'s native cleanup only *schedules* an async task rather
  than waiting for it to finish, so the very next line could schedule a
  brand new start on the same native camera object while the previous
  stop was still mid-flight. Two operations racing on the same native
  object is exactly what corrupts the plugin's internal Dart list state.
  Added a proper busy-guard that both the start and stop paths wait on
  symmetrically — verified directly with a simulated concurrent
  start/stop that the stop now correctly waits for an in-progress start
  to fully finish before touching the camera at all, rather than barging
  in.

- **Fixed the actual root cause of the Android camera failure**, now that
  the previous round's self-test finally surfaced a real error:
  `"Camera is not initialized. Call initialize() first."` — a classic
  Flutter platform-channel race condition. `page.update()` tells the
  client to mount the native camera view but returns as soon as the
  message is sent, not once the device has actually finished building
  that view; the async init code was calling straight into
  `initialize()`/`start_image_stream()` without waiting for that to
  genuinely finish. Added a short settling delay before `initialize()`,
  and — since a single fixed delay is still a guess about timing that
  varies by device — a retry loop specifically around
  `start_image_stream()` (up to 3 attempts with a short backoff).
  Verified directly with a mocked camera: a transient failure that
  resolves on the 3rd attempt now succeeds cleanly with no error, while a
  genuinely persistent failure still surfaces a clear error after
  exhausting retries rather than hanging or retrying forever.

- **Fixed "Android camera fails silently, no error message"**: the
  4-second no-frames watchdog only ever ran in Camera Mode (the only path
  that streams frame bytes through Python) — the Logger tab's native
  preview had no equivalent check at all, so if it failed silently, there
  was genuinely no mechanism that could catch it. Now every camera start,
  regardless of mode, briefly runs the frame stream as a self-test to
  confirm the camera pipeline actually works end to end. In Camera Mode
  the stream stays running afterward (it's needed continuously, to serve
  over the MJPEG server); in Inputter Mode it stops right after the
  self-test, handing continuous display back to the native preview
  surface at full frame rate. Tested all three outcomes directly with a
  mocked flet-camera: no frames arriving (shows the diagnostic error),
  frames arriving successfully (clears any error, hands back to preview),
  and confirmed Camera Mode correctly keeps streaming while Inputter Mode
  correctly stops it.

- **Stopped hiding the real cv2 import error**: every place that caught
  `ImportError` for cv2 was replacing the actual exception with a generic
  hardcoded "opencv-python not installed" message — including in exactly
  the situation now being debugged, where `cv2.pyd` genuinely exists on
  disk (confirmed via direct file inspection of your build) but
  `import cv2` still fails. That contradiction can only be explained by
  the real underlying exception text, which was never visible before.
  Now shows it directly: `cv2 import failed: <ExceptionType>: <message>`.
- **Added `numpy` back explicitly for Windows** in `pyproject.toml`. My
  leading hypothesis for what the above will likely reveal: opencv-python
  imports numpy as part of its own startup, not just for numpy-array APIs
  this app happens to use — and numpy was deliberately removed from this
  project's own dependencies a while back (once the radar chart no longer
  needed it), so if `flet build`'s dependency installation doesn't
  automatically resolve packages' own transitive dependencies the way a
  plain `pip install opencv-python` would, numpy could be silently
  missing at runtime even though nothing in this app's own code imports
  it directly. Low-risk to include either way — this is worth having
  rebuilt in either case, to see the real error with fresh eyes.

- **Reverted the prevent_close-based save-on-close feature entirely** — it
  caused two real regressions in a row (first no fallback if close
  failed, then apparently not reliably firing/syncing at all in the
  actual built app, leaving it unclosable outside Task Manager both
  times). Verified via byte-search that the fix code genuinely was
  present in your build, so this is a real mechanism failure, not a
  stale-build issue. Given the risk (a completely unclosable app) far
  outweighs the benefit (the app already saves after nearly every action
  — 23+ call sites — plus a 60s autosave loop), replaced it with
  `page.on_disconnect` instead: a passive, best-effort save attempt that
  fires on disconnect but has no mechanism to block or interfere with the
  window actually closing. The app should close normally again — X
  button, Alt+F4, all of it — exactly as it did before this feature was
  ever introduced.
- **Fixed a real silent-failure bug in camera detection**: the scan's
  outer call (`await asyncio.to_thread(_scan_blocking)` and its sync
  equivalent) had no try/except around it. Any unexpected exception —
  plausibly from the newly-added `ctypes`/`GetLastError` diagnostic code —
  would vanish with no message, `camera_scanning` would stay stuck `True`
  forever, and the screen would just show the initial "scanning" refresh
  and then go silent. This matches exactly what was reported ("reloads
  the page and sends no error message"). Now guaranteed to always reach a
  real, visible result — success, a specific camera-open failure, or (new)
  an "unexpected error during scan" message with the real exception text,
  rather than silently going nowhere. Also fixed `_finish()`'s error path,
  which only showed a disappearing toast rather than the persistent
  on-screen text every other failure path uses.

- **Verified against your actual build**: extracted and byte-searched the
  compiled `main.pyc` from your uploaded zip — confirmed the COM-init fix
  genuinely was in that build (not a stale-cache issue this time), and
  `cv2.pyd` (86MB) plus its FFmpeg DLL are both fully intact. Packaging
  isn't the problem here.
- **New camera diagnostic**: capture the raw Windows error code
  (`GetLastError()`) immediately after any failed camera-open attempt, on
  both Detect Cameras and actually turning the camera on. OpenCV itself
  was swallowing the real reason a backend failed to open (no exception,
  `isOpened()` just cleanly False) — this is exactly the case that gave
  zero diagnostic signal so far. If Windows has any underlying error code
  at all for the failure, this should now surface it on screen.

- **Fixed a regression from the save-on-close feature (urgent)**: the
  previous version set `prevent_close=True` (needed so a save-before-close
  handler gets a chance to run at all) but had no fallback if
  `window.destroy()` itself failed for any reason — which made the app
  completely unclosable via the X button, Alt+F4, anything, except Task
  Manager. Now tries `window.destroy()`, then `window.close()`, then
  unconditionally calls `os._exit(0)` as a last resort — tested all four
  scenarios directly (normal close, destroy() failing, both destroy() and
  close() failing, and even the save step itself throwing) and confirmed
  the window always actually closes in every case.

- **Windows camera fix attempt (COM initialization)**: added `_win32_com_init()`,
  called at the top of every function that touches `cv2.VideoCapture` on a
  background thread (camera detection scan, the frame-capture loop, and
  opening the camera itself). MSMF and DirectShow — the Windows camera
  backends OpenCV uses — both depend on COM being explicitly initialized
  on whichever thread calls into them; a plain script's main thread gets
  this implicitly, but this app's camera code always runs on background
  worker threads (by design, so it doesn't block the UI), which never do.
  This matches everything observed while debugging this: works via a
  simple `python -c "..."` script (single main thread), fails from every
  background thread in the actual app, with zero exceptions and no entry
  in Windows' own camera-privacy tracking (consistent with the COM call
  never actually completing). This is my best remaining diagnosis after
  ruling out packaging/DLL and permission causes — rebuild and test.
- **Save-on-close**: the app already saves immediately after nearly every
  logging action (23 separate call sites), so data-loss risk was already
  low, but there was no explicit handling of the window actually closing
  (the X button, Alt+F4, Windows shutting down) — closing shortly after
  an action but before the next 60s autosave tick could still lose that
  last bit. Now intercepts the window close event, forces an immediate
  save, then lets the window actually close. Verified with both a close
  event (triggers save) and a non-close window event like resize
  (correctly ignored). Match data already loaded on startup as before —
  this closes the other half of "save on close, load on open."

- **Real Windows installer** (this round): added `installer\StatTracker.iss`
  (Inno Setup) — compiles into a proper `StatTracker-Setup.exe` that
  installs to Program Files, adds a Start Menu entry, and registers a
  real uninstaller in Settings → Apps, instead of handing out a zip of
  loose files. See "4a" above for the full walkthrough.
- **Fixed a real bug this surfaced**: match data was saving next to the
  app's own files, which silently breaks once properly installed to
  Program Files (not writable by normal use without admin rights). Now
  saves to `%LOCALAPPDATA%\Stat Tracker\` on Windows instead — see
  `_data_dir()` in `storage.py`. Every other platform's behavior is
  unchanged.

- **Automatic camera detection/pairing** (this round): opening the
  camera source picker now automatically kicks off two scans in the
  background instead of requiring a manual tap first — a local-device
  scan on desktop (mobile already lists front/back with no scan needed),
  and a wireless auto-discovery listen on every platform. Camera Mode now
  broadcasts a small UDP announcement every 2s while streaming; Inputter
  Mode's picker listens for ~4s and lists whatever answers as a tappable
  entry — no stream URL typing needed when both devices are on the same
  network. The manual URL field is still there as a fallback for networks
  that block broadcast traffic (common on school WiFi with client/AP
  isolation). True USB-cable device pairing (without tethering) was
  considered and intentionally not built — it would require OS-level
  drivers (ADB port-forwarding for Android, something else entirely for
  other platforms) outside what a cross-platform Flet/Python app can do;
  USB tethering (documented in README.md) is the practical wired option.

- **New branding**: the shield logo and splash artwork you uploaded are now
  embedded in `assets_data.py` (base64, resized/compressed for a small app
  bundle) and used for the window icon, navbar badge, and splash screen.
- **Animated startup sequence**: the splash logo now fades and scales in
  (an "ease-out-back" pop) on first paint instead of appearing instantly,
  the progress bar fades in alongside it, and the status label cross-fades
  between each real startup step (loading settings → matches → profile →
  video system → interface) instead of just swapping text.
- **Native Android/iOS camera** (this round): local camera capture on
  mobile now goes through `flet-camera` instead of OpenCV, with a
  front/back lens picker replacing the desktop device-index chips. The
  wireless/IP-camera and Camera-Mode-pairing path was rewritten as a
  dependency-free Python MJPEG reader so it also works on mobile. Desktop
  behavior is unchanged.
- **Size optimization** (this round): the Stats-tab radar chart now draws
  natively via `flet.canvas` instead of matplotlib/numpy rendering a PNG —
  both dependencies removed. Also dropped a redundant full-size icon copy
  that was baked into `assets_data.py` but never read at runtime. The chart
  looks the same; it's just vector-drawn instead of a raster image now.
- **Per-platform dependency split** (this round): added `pyproject.toml`
  with `[tool.flet.<platform>]` dependency tables, so Android/iOS builds
  only get `flet-camera` and desktop builds only get `opencv-python` —
  neither ships the other's camera dependency anymore.
- **Web build support** (this round): the app now runs as a web app
  (`flet run --web` / `flet build web`). Export/import switched from
  `tkinter.filedialog` (desktop-only, silently broken on web) to
  `ft.FilePicker`, which works correctly as a real save/open dialog on
  desktop, a share sheet on mobile, and an actual browser
  download/upload on web. The camera source picker now has a web-specific
  variant (wireless/IP-camera URL only — no local device access makes
  sense for a hosted web app). See BUILD_INSTRUCTIONS.md for an important
  caveat about match data being stored in one shared file across all web
  visitors.
- No other functional/logic changes — Logger, Timeline, Stats, exports,
  etc. all work exactly as before.
