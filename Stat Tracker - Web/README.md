# Stat Tracker — v4 (Android Build)

> **This package is for building the Android `.apk`/`.aab`.** The
> codebase is fully cross-platform — the exact same source also builds
> the Windows `.exe` (see the Windows package, or just run
> `flet build windows` from here too; nothing platform-specific has been
> stripped out). This copy is simply labeled/organized for the Android
> build workflow.
>
> **Quick start:**
> ```cmd
> pip install -r requirements-dev.txt
> python main.py
> flet clean
> flet build apk --project "Stat Tracker" --org com.yourname.stattracker --split-per-abi
> ```
> Full walkthrough (prerequisites, troubleshooting, size optimization):
> see `BUILD_INSTRUCTIONS.md`.

---


Real-time football match statistics tracker for **St Charles College only**.
Team-level stats — no individual player tracking, no AI features. Pure
manual logging with a live video feed alongside the action buttons.

## Branding

The app uses the official Stat Tracker shield logo as its window icon
and navbar badge, and a branded splash screen shows on every launch with
a progress bar reflecting real startup steps (loading settings, loading
saved matches, preparing the video system, building the interface) rather
than a fake timed animation. Assets are embedded directly in the app
(`assets_data.py`) so there's nothing extra to install or configure.

## Setup

```bash
pip install -r requirements-dev.txt
python main.py
```

`pyproject.toml` is what actually governs each *built* app (`flet build
windows` / `flet build apk`) — it declares a separate, smaller dependency
set per platform (desktop gets OpenCV, Android/iOS get flet-camera,
neither gets the other). `requirements-dev.txt` installs everything, for
local development only. See BUILD_INSTRUCTIONS.md.

No API keys, no external services — everything runs locally.

## First launch

The app asks for your name the first time it opens. This is remembered
between sessions and included in every exported match report. Change it
anytime via the name pill in the top-left of the navbar.

Right after that, it asks which mode this device should run in:

- **Inputter Mode** — the normal app: log match stats, optionally showing
  a video feed (local camera or from a Camera Mode device).
- **Camera Mode** — a minimal screen that just captures video and streams
  it over the network to whichever device is running Inputter Mode.

Switch between modes anytime via the **Device Mode** navbar button.

## Two-device setup (Camera Mode + Inputter Mode)

If one device is filming the match and another is logging stats:

1. On the **filming** device, choose **Camera Mode**, pick a camera source
   (or scan for one), and press **Start Streaming**. It shows a URL like
   `http://192.168.1.42:8765/video` — and while streaming, it also
   broadcasts itself on the local network so it can be found automatically.
2. On the **logging** device, choose **Inputter Mode**. The camera source
   picker automatically listens for that broadcast the moment it's opened,
   and any Camera Mode device already streaming on the network shows up as
   a tappable entry — tap it to connect, no URL typing needed. If it
   doesn't appear (some networks, notably school WiFi with client/AP
   isolation enabled, block this broadcast traffic between devices), tap
   **Auto-Discover Cameras** to retry, or fall back to pasting the URL into
   the manual field and pressing **Connect**.
3. Both devices need to be on the same network (WiFi or wired LAN — see
   the USB tethering note below for a wired alternative). No internet
   connection or external service is used — it's a direct device-to-device
   HTTP video stream, and auto-discovery is a local broadcast only
   (nothing leaves the local network).

If Windows shows a firewall prompt when Camera Mode starts streaming,
allow access on private networks so the Inputter device can connect.

### Wired (USB cable) instead of WiFi

The two-device setup above needs the devices to share an IP network —
it doesn't have to be WiFi. Connecting two devices with a USB cable and
enabling **USB tethering** on the phone (Android: Settings → Network &
internet → Hotspot & tethering → USB tethering) creates exactly that: a
private wired IP network between the two devices, with no WiFi/router
involved at all. Once that's on, everything above works completely
unchanged — start Camera Mode on the filming phone, copy the URL it
shows, paste it into Inputter Mode's camera source field on the other
device, Connect. No app changes needed; this is the same MJPEG-over-HTTP
streaming the app already does, just carried over a USB link instead of
WiFi (in fact it's more reliable than WiFi for this, since there's no
router/signal dropout in the middle).

This is different from — and much simpler than — making a phone appear
as a native USB webcam a PC recognizes directly (the way commercial apps
like DroidCam do). That requires custom OS-level drivers on both ends and
isn't something achievable from inside a Flet/Python app; if you
specifically need that instead of the URL-based connection above, it'd be
a separate, considerably larger piece of work — let me know if that's
really what's needed and I'll scope it properly rather than guess.

## Core features

- **St Charles College only** — every match is SCC vs an opponent; only
  SCC's own actions are logged in detail (shots, passes, tackles, etc.)
  Opponent score can still be adjusted manually for the final result.
- **Live video on the Logger tab** — turn the camera on and watch the
  match while clicking action buttons, all on one screen. Supports
  multiple local camera devices and external/wireless IP cameras (phone
  IP-camera apps, RTSP/HTTP streams) via the source picker under the
  video panel.
- **Fullscreen video logging mode** — click the fullscreen icon on the
  video panel for a dedicated full-window layout: scores/timer/possession
  on top, incomplete buttons on the left, action buttons on the right,
  cards/undo/sequences on the bottom, video filling the rest. Esc or the
  exit button returns to normal view.
- **Possession tracking** — toggle which team currently has the ball;
  seconds accumulate automatically while the match clock is running.
  Possession switches to the conceding team automatically whenever SCC
  scores (or the opponent's score is bumped up manually). Final
  percentages are calculated from total accumulated seconds.
- **Editable match details** — opponent name, location, date, age group,
  and sport can all be changed after the match is created via the
  **Edit Match** navbar button.
- **Multiple matches** — create, switch between, and delete matches (with
  confirmation) via the navbar.
- **Kit colours** — add/remove colours per team (min 2). SCC is locked to
  Navy `#1E3A8A`, White, and Gold `#FFD700`.
- **Export / Import as TXT** — exports full stats, attack/defence/cards
  sequences, timestamps, and match details to a plain text file (no AI
  content). The file embeds a JSON block so it can be re-imported later
  to restore the match exactly.

## Action logging layout

Actions › Incompletes › Substitution › Turnover › Conversion+Goals/Assists
› Fouls › Cards › Time Controllers — split into Attack / Defence / Cards
tabs. Incomplete buttons only become clickable immediately after their
matching action is logged. Conversion only becomes available after an
Attack action, and increments Goals + Assists + Conversions together.

## Keyboard Shortcuts (Logger tab)

| Key | Action      | Key | Action        |
|-----|-------------|-----|---------------|
| G   | Goal        | P   | Pass          |
| I   | Pass ✗      | C   | Cross         |
| V   | Cross ✗     | L   | Long Pass     |
| S   | Shot        | X   | Shot ✗        |
| K   | Tackle      | E   | Intercept     |
| B   | Block       | D   | Save          |
| U   | Clear       | O   | Offside       |
| W   | Fouls Won   | H   | Fouls Given   |
| M   | Corner      | T   | Throw-in      |
| A   | Assist      | N   | Conversion    |
| Z   | Dribble     | Q   | Turnover      |
| Y   | Yellow Card | R   | Red Card      |
| Esc | Exit fullscreen video mode |     |               |

## Sequence notation

Each action appends a code to the running sequence string for the match:

| Code | Meaning        | Code | Meaning         |
|------|----------------|------|-----------------|
| I    | Pass           | c    | Cross           |
| L    | Long Pass      | s    | Shot            |
| d    | Dribble        | K    | Corner          |
| TH   | Throw-in       | T    | Tackle          |
| B    | Block          | V    | Save            |
| C    | Clear          | F+   | Fouls Won       |
| F-   | Fouls Given    | `^AG`| Conversion (turnover→assist→goal) |
| !    | suffix = incomplete (e.g. `I!` = incomplete pass) |

## Export format

```
=== FULL GAME REPORT: SCC vs Westville ===
Timestamp: 2026-08-01 09:39:33
Logged by: <your name>
Final Score: 2 - 1
Match Duration: 47'23"
...
Possession: 58%
--- ATTACK STATISTICS ---
Passes: 25
...
Incomplete (P!/C!/S!): 8/9/9
Attack Sequence: II!IIc!IIs!c^AGI!I!...
```

The TXT file embeds a JSON block at the bottom which can be re-imported
via the **Import TXT** navbar button to restore the match exactly.
