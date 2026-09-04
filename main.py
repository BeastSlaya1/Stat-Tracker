"""
Stat Tracker — Python / Flet  (v4)
Requirements 7-25 implemented
"""
from __future__ import annotations

import base64, io, json, os, re, socket, sys, threading, time, urllib.request, uuid
import http.server, socketserver
from datetime import datetime
from typing import List, Optional

import flet as ft
import flet.canvas as cv

from models import Match, StatEvent, Player, Team, MatchStats, PERIOD_LABELS, SCC_COLORS
from engine import (recalculate_stats, advance_period, make_event,
                    build_scc_team, tally_action, generate_sequences)
from storage import (save_matches, load_matches, get_logger_name, set_logger_name,
                     get_app_mode, set_app_mode)
from assets_data import ICON_SMALL_PNG_B64, SPLASH_JPG_B64

# Native on-device camera (Android/iOS/Web) — no OpenCV dependency. Optional
# import: the app still runs on desktop (where this package isn't needed)
# if it isn't installed, and _start_camera() reports a clear error if a
# mobile build somehow shipped without it.
try:
    import flet_camera as ftc
    HAS_FLET_CAMERA = True
except ImportError:
    ftc = None
    HAS_FLET_CAMERA = False

# This project's own custom Flet extension (packages/stc_camera_preview)
# — a smooth live camera preview built entirely in Dart, with only a
# single plain-string property crossing into Python. Built specifically
# to sidestep a confirmed bug in Flet's own core SDK's marshaling of
# complex types (Enums, dataclasses) — see
# packages/stc_camera_preview/stc_camera_preview/camera_preview.py for
# the full story. Also optional-import for the same reason as
# flet_camera above (desktop doesn't need or ship it).
try:
    import stc_camera_preview as stcam
    HAS_STC_CAMERA_PREVIEW = True
except ImportError:
    stcam = None
    HAS_STC_CAMERA_PREVIEW = False

# Built-in/browser camera (the "This Device's Camera" button) now splits
# across two mechanisms doing two different jobs:
#   - Inputter Mode's local live view: stc_camera_preview (this project's
#     own custom extension, above) — genuine native/browser frame rate,
#     nothing routed through flet-camera's continuous-event pipeline at
#     all.
#   - Camera Mode's broadcast frames (needs actual bytes, to serve over
#     MJPEG to another device): flet-camera's take_picture(), polled
#     repeatedly — see _native_camera_takepicture_poll_loop. Confirmed
#     working on its own (a previous version of this app used it
#     successfully) since it sends zero arguments and returns plain
#     bytes, unlike the continuous-preview/streaming paths that hit the
#     bug described above.
# NATIVE_CAMERA_ENABLED is kept as a single kill-switch in case a
# specific device/browser still can't get either working — flip to
# False to fall back to wireless/IP camera only, which is unaffected
# either way.
NATIVE_CAMERA_ENABLED = True

BG       = "#020617"
SURFACE  = "#0f172a"
SURFACE2 = "#0a0f1e"
BORDER   = "#1e293b"
BORDER2  = "#334155"
TEXT     = "#f1f5f9"
TEXT2    = "#cbd5e1"
MUTED    = "#94a3b8"
MUTED2   = "#64748b"
INDIGO   = "#6366f1"
INDIGO6  = "#4f46e5"
INDIGO4  = "#818cf8"
INDIGO3  = "#a5b4fc"
EMERALD  = "#34d399"
EMERALD5 = "#10b981"
EMERALD6 = "#059669"
AMBER    = "#fbbf24"
AMBER3   = "#fcd34d"
ROSE     = "#f43f5e"
RED4     = "#f87171"
SKY      = "#38bdf8"
CYAN4    = "#22d3ee"
PURPLE4  = "#c084fc"
TEAL4    = "#2dd4bf"
GOLD     = "#FFD700"

EVENT_EMOJI = {
    "GOAL": "⚽", "CONVERSION": "✅", "SHOT": "🥅",
    "SHOT_INCOMPLETE": "❌", "PASS": "👟", "PASS_INCOMPLETE": "❌",
    "LONG_PASS": "🎯", "LONG_PASS_INCOMPLETE": "❌",
    "CROSS": "📐", "CROSS_INCOMPLETE": "❌",
    "THROW_IN": "🤾", "THROW_IN_INCOMPLETE": "❌",
    "INTERCEPT": "✋", "INTERCEPT_INCOMPLETE": "❌",
    "BLOCK": "🧱", "BLOCK_INCOMPLETE": "❌",
    "OFFSIDE_GIVEN": "🚩", "OFFSIDE_GIVEN_INCOMPLETE": "❌",
    "CLEAR": "🧹", "CLEAR_INCOMPLETE": "❌",
    "FOULS_WON": "🙌", "FOULS_GIVEN": "⚠️",
    "PENALTY": "🎯", "DRIBBLE": "⚡", "TURNOVER": "🔁",
    "YELLOW_CARD": "🟨", "RED_CARD": "🟥",
    "CORNER": "⛳", "OFFSIDE": "🚩", "OFFSIDE_INCOMPLETE": "❌",
    "SUBSTITUTION": "🔄", "SAVE": "🧤", "SAVE_INCOMPLETE": "❌",
    "TACKLE": "🛡", "TACKLE_INCOMPLETE": "❌", "ASSIST": "🅰️",
    "GK_KICK": "🦵", "GK_THROW": "🤲",
}

ACTION_RULES = [
    ("Long Pass",     "LONG_PASS",     True,  "A kick above players heads across half a field or more."),
    ("Cross",         "CROSS",         True,  "A kick above heads directed toward the goal."),
    ("Pass",          "PASS",          True,  "A short kick to another player, not above head height."),
    ("Shot",          "SHOT",          True,  "A kick directly at goal to score."),
    ("Throw In",      "THROW_IN",      True,  "Ball thrown in from the touchline."),
    ("Tackle",        "TACKLE",        True,  "Getting the ball from an opponent who has full control."),
    ("Intercept",     "INTERCEPT",     True,  "Getting the ball when the opponent does not have full control."),
    ("Block",         "BLOCK",         True,  "An outfield player stops the ball from entering goal."),
    ("Save",          "SAVE",          True,  "The goalkeeper stops the ball from going into goal."),
    ("Offside",       "OFFSIDE",       True,  "Our player was offside."),
    ("Offside Given", "OFFSIDE_GIVEN", True,  "The opposition was offside."),
    ("Clear",         "CLEAR",         True,  "Deliberately clearing the ball out of play."),
    ("Fouls Won",     "FOULS_WON",     False, "The opposition fouls one of our players."),
    ("Penalty",       "PENALTY",       False, "A free kick from the penalty spot."),
    ("Corner",        "CORNER",        False, "Ball kicked from the corner."),
    ("Assist",        "ASSIST",        False, "A player who helps another player score."),
    ("Conversion",    "CONVERSION",    False, "Pressed after an attack action that leads to a goal."),
    ("Goal",          "GOAL",          False, "The ball goes into the goal."),
    ("Fouls Given",   "FOULS_GIVEN",   False, "Our player fouls an opposition player."),
    ("Dribble",       "DRIBBLE",       False, "A series of short kicks by one player."),
    ("Turnover",      "TURNOVER",      False, "Control of the ball lost to the opposition."),
]

DICTIONARY_ONLY_ENTRIES = [
    ("Incompletes", "When the ball is not received by a teammate, goes off target, or is blocked."),
    ("Half Time",   "When the game is halfway to completion."),
    ("Full Time",   "When the game is complete."),
    ("Overtime",    "When neither team has won after full/half time."),
]

_NATIVELY_TALLIED = {"CROSS","PASS","SHOT","TACKLE","SAVE","CORNER","ASSIST","CONVERSION","GOAL","LONG_PASS"}
GENERIC_TALLY_ACTIONS = [
    (name, etype, has_inc)
    for name, etype, has_inc, _ in ACTION_RULES
    if etype not in _NATIVELY_TALLIED
]

_ACTION_NAME_TO_TYPE = {name: etype for name, etype, _, __ in ACTION_RULES}
_ACTION_NAME_TO_TYPE.update({
    "Yellow Card": "YELLOW_CARD",
    "Red Card": "RED_CARD",
    "Substitution": "SUBSTITUTION",
})

VALID_EVENT_TYPES_LIST = ", ".join(sorted(
    {etype for _, etype, __, ___ in ACTION_RULES}
    | {f"{etype}_INCOMPLETE" for _, etype, has_inc, __ in ACTION_RULES if has_inc}
    | {"YELLOW_CARD", "RED_CARD", "SUBSTITUTION"}
))

_PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

# req 22 — Attack buttons
ATTACK_BUTTONS = [
    ("Longpass",      "LONG_PASS",     "🎯", INDIGO4),
    ("Pass",          "PASS",          "👟", SKY),
    ("Cross",         "CROSS",         "📐", CYAN4),
    ("Shot",          "SHOT",          "🥅", EMERALD),
    ("Corner",        "CORNER",        "⛳", PURPLE4),
    ("Throw-in",      "THROW_IN",      "🤾", TEAL4),
    ("Dribble",       "DRIBBLE",       "⚡", AMBER),
    ("Fouls Won",     "FOULS_WON",     "🙌", AMBER3),
    ("GK Kick",       "GK_KICK",       "🦵", SKY),
    ("GK Throw",      "GK_THROW",      "🤲", INDIGO4),
    ("Offside Given", "OFFSIDE_GIVEN", "🚩", ROSE),
]

# req 22 — Defence buttons
DEFENCE_BUTTONS = [
    ("Tackle",        "TACKLE",        "🛡",  INDIGO4),
    ("Save",          "SAVE",          "🧤",  EMERALD),
    ("Block",         "BLOCK",         "🧱",  CYAN4),
    ("Clear",         "CLEAR",         "🧹",  SKY),
    ("Penalty Rec.",  "PENALTY",       "🎯",  AMBER),
    ("Offside Rec.",  "OFFSIDE",       "🚩",  ROSE),
    ("Intercept",     "INTERCEPT",     "✋",  PURPLE4),
    ("Fouls Given",   "FOULS_GIVEN",   "⚠️", RED4),
]

# Actions that can have an incomplete (req 21)
INCOMPLETE_PARENTS = {
    "PASS", "LONG_PASS", "CROSS", "SHOT", "THROW_IN",
    "TACKLE", "INTERCEPT", "BLOCK", "SAVE", "CLEAR", "OFFSIDE", "OFFSIDE_GIVEN",
}
ATTACK_PARENTS  = {b[1] for b in ATTACK_BUTTONS}
DEFENCE_PARENTS = {b[1] for b in DEFENCE_BUTTONS}

# All choosable kit colours (req 13)
COLOUR_PALETTE = [
    "#1E3A8A","#FFFFFF","#FFD700","#000000","#FF0000","#008000",
    "#FFA500","#800080","#00BFFF","#FF69B4","#8B4513","#C0C0C0",
    "#2196F3","#4CAF50","#F44336","#9C27B0","#FF9800","#00BCD4",
    "#607D8B","#795548","#FFEB3B","#E91E63","#009688","#3F51B5",
]


# ── Camera Mode ↔ Inputter Mode: MJPEG streaming over HTTP ───────────────────
# Camera Mode devices capture video and serve it as an MJPEG HTTP stream.
# Inputter Mode devices connect to that stream URL the exact same way they'd
# connect to any external/wireless IP camera (cv2.VideoCapture can open an
# MJPEG stream URL directly) — no special protocol needed on the receiving
# end, which lets this reuse all the existing camera-source code.
MJPEG_PORT = 8765
_STREAM_BOUNDARY = b"--frame"
# UDP broadcast port used for auto-discovering wireless Camera Mode
# devices on the same local network — a Camera Mode device periodically
# announces itself here while streaming; an Inputter Mode device listens
# for a few seconds and lists whatever answers, instead of requiring the
# stream URL to be typed in by hand.
DISCOVERY_PORT = 8766
DISCOVERY_MAGIC = "STAT_TRACKER_CAMERA_ANNOUNCE"


def _win32_com_init():
    """MSMF and DirectShow — Windows' own native camera backends, which is
    what cv2.VideoCapture ultimately calls into on Windows — both depend
    on COM, which Windows requires to be explicitly initialized on
    whichever thread actually calls into them. A normal Python script's
    main thread effectively gets this for free; background worker threads
    (threading.Thread, asyncio.to_thread's executor threads) never do.

    This app's camera scanning and frame-capture loop always run on
    exactly those kinds of background threads (by design — so they don't
    block the UI). That's consistent with everything observed while
    debugging the Windows "camera detects nothing, no error, works fine
    via a plain `python -c` script" issue: a simple script runs on a
    single main thread; this app's actual camera calls never do.

    Cheap and safe to call repeatedly/redundantly — CoInitializeEx just
    returns a harmless "already initialized" result if called again on a
    thread that's already set up, so every function that touches
    cv2.VideoCapture calls this at its own top rather than relying on
    some shared call-once guarantee across different threads."""
    if sys.platform == "win32":
        try:
            import ctypes
            # COINIT_APARTMENTTHREADED (0x2) — the threading model
            # Windows' media/camera capture APIs are documented to expect.
            ctypes.windll.ole32.CoInitializeEx(None, 0x2)
        except Exception as ex:
            print(f"[COM] CoInitializeEx failed: {type(ex).__name__}: {ex}")


def get_local_ip() -> str:
    """Best-effort LAN IP so the Camera Mode device can show a URL that's
    actually reachable from another device on the same network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class _MJPEGRequestHandler(http.server.BaseHTTPRequestHandler):
    """Serves whatever JPEG frame is currently in app._latest_jpeg_frame as
    a multipart/x-mixed-replace stream — the standard MJPEG-over-HTTP format
    that both browsers and cv2.VideoCapture(url) can consume directly.

    Also handles the pairing handshake: a connecting device (Inputter Mode)
    shows a code on its own screen and sends it here via /pair/request; the
    receiving device (Camera Mode) picks the matching number from 4 choices
    on its own screen to approve. /video refuses to stream until approved.
    This only applies to devices going through this handshake — a cable
    connection or a third-party camera/drone never calls these endpoints at
    all, so they're unaffected."""

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        app = self.server.app_ref

        if path == "/pair/request":
            try:
                code = int(qs.get("code", [""])[0])
            except (ValueError, IndexError):
                self._send_json({"error": "missing/invalid code"}, 400); return
            app.pair_start_request(code)
            self._send_json({"status": "pending"})
            return

        if path == "/pair/status":
            self._send_json({"status": app.pair_status})
            return

        if path not in ("/video", "/"):
            self.send_response(404); self.end_headers(); return

        if app.pair_status != "approved":
            # Not paired yet — refuse to stream. The connecting device is
            # expected to complete /pair/request + wait for approval first.
            self._send_json({"error": "not paired — complete pairing handshake first"}, 403)
            return

        try:
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            last_sent_frame = None
            while app.camera_mode_streaming and app.pair_status == "approved":
                # The check-and-wait has to happen while holding
                # app._new_frame_cond's lock, atomically — checking for a
                # new frame, then separately entering wait() afterward,
                # would leave a real (if narrow) gap where a
                # notify_all() landing exactly in between the two gets
                # missed entirely, silently falling back to the 1s safety
                # timeout below instead of waking immediately. Holding
                # the lock across both closes that gap — this is the
                # standard, textbook-correct way to use a Condition, not
                # an extra precaution layered on top of it.
                with app._new_frame_cond:
                    frame = app._latest_jpeg_frame
                    if not frame or frame is last_sent_frame:
                        # Blocks here instead of the tight sleep(0.001)
                        # polling loop this used to be — that busy-wait
                        # woke up ~1000x/second, and in CPython every one
                        # of those wakeups means reacquiring the GIL,
                        # competing with the actual capture loop's own
                        # thread for it. That's precisely why the local
                        # preview only slowed down once a device
                        # connected here specifically — this loop only
                        # runs at all while a client is connected.
                        # Condition.wait() consumes no GIL time while
                        # genuinely blocked and wakes up exactly when a
                        # new frame is ready (see the notify_all() calls
                        # alongside every _latest_jpeg_frame assignment),
                        # rather than however long the next 1ms tick
                        # happens to take — a strict improvement in both
                        # responsiveness and overhead, not a trade-off
                        # between them. The 1.0s timeout is just a safety
                        # net so this loop still re-checks
                        # camera_mode_streaming/pair_status periodically
                        # even if a frame genuinely never arrives (e.g.
                        # the camera stalled) — it does not add delay to
                        # the normal case, since notify_all() wakes it
                        # immediately regardless of the timeout value.
                        app._new_frame_cond.wait(timeout=1.0)
                        continue
                # Only send when a genuinely new frame has arrived — avoids
                # re-transmitting the same JPEG bytes on every loop tick and
                # lets this run at whatever speed new frames actually show
                # up, i.e. the camera's real max rate, instead of a fixed
                # 30fps cap.
                self.wfile.write(_STREAM_BOUNDARY + b"\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()   # see setup() below for why this matters here
                last_sent_frame = frame
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass   # receiving device disconnected — not an error
        except Exception:
            pass

    def setup(self):
        """Runs once per connection, before handle(). Two latency fixes
        for the streaming delay reported between a frame being captured
        and it actually appearing on the receiving device:

        1. TCP_NODELAY disables Nagle's algorithm on this socket. Nagle's
           algorithm exists to batch up several *small* writes into one
           network packet rather than sending each individually — great
           for chatty protocols sending lots of tiny messages, but actively
           harmful here: each MJPEG frame is written across several
           separate wfile.write() calls (boundary marker, headers, then
           the actual JPEG bytes), and without this, the OS can genuinely
           sit on the first few of those for up to ~200ms waiting to see
           if more data is coming before actually sending the packet —
           adding real, measurable end-to-end delay to every single
           frame, compounding over a live stream.
        2. self.wfile.flush() (added at the end of the write sequence
           above) makes sure Python's own BufferedWriter actually hands
           the bytes to the OS socket right away rather than potentially
           holding them until its internal buffer fills up — the second
           half of the same "don't let anything sit around waiting"
           fix TCP_NODELAY handles on the OS side.
        Both are standard, well-established fixes for exactly this
        symptom in any Python HTTP-based low-latency streaming server,
        not something specific to this app."""
        super().setup()
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass   # not fatal if the platform/socket type doesn't support it

    def log_message(self, fmt, *args):
        pass   # silence default per-request console spam


class _ThreadingMJPEGServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _build_rulebook_prompt_block() -> str:
    lines = ["OFFICIAL ACTION RULEBOOK:"]
    for name, etype, has_inc, defn in ACTION_RULES:
        inc = f" (also {etype}_INCOMPLETE)" if has_inc else ""
        lines.append(f"- {etype}{inc}: {name} — {defn}")
    lines.append("- YELLOW_CARD / RED_CARD / SUBSTITUTION: standard events.")
    return "\n".join(lines)


# ── Widget helpers ─────────────────────────────────────────────────────────────

def card(content, padding=16, radius=16, border_color=None):
    bc = border_color or "#1e293b"
    return ft.Container(content=content, bgcolor="#0f172a",
                        border=ft.Border.all(1, bc),
                        border_radius=radius, padding=padding)

def txt(s, size=11, color=None, weight=ft.FontWeight.NORMAL, mono=False, selectable=False):
    c = color or "#94a3b8"
    return ft.Text(s, size=size, color=c, weight=weight,
                   font_family="monospace" if mono else None,
                   selectable=selectable)

def pill(text, bg="#6366f1", size=10):
    return ft.Container(
        content=ft.Text(text, size=size, color="#f1f5f9", weight=ft.FontWeight.BOLD),
        bgcolor=bg+"33", border=ft.Border.all(1, bg+"88"),
        border_radius=20, padding=ft.Padding.symmetric(horizontal=8, vertical=2))

def section_header(icon_name, title, icon_color="#818cf8"):
    return ft.Row([ft.Icon(icon_name, size=14, color=icon_color),
                   ft.Text(title, size=13, color="#f1f5f9", weight=ft.FontWeight.BOLD)], spacing=6)

def dual_stat_bar(label_str, home_val, away_val, home_ratio, away_ratio, home_color, away_color):
    total = home_ratio + away_ratio
    home_pct = max(2, min(98, round(home_ratio / total * 100))) if total > 0 else 50
    away_pct = 100 - home_pct
    return ft.Column([
        ft.Row([
            ft.Text(str(home_val), size=12, color="#f1f5f9", weight=ft.FontWeight.W_600, font_family="monospace"),
            ft.Text(label_str, size=10, color="#94a3b8", expand=True, text_align=ft.TextAlign.CENTER),
            ft.Text(str(away_val), size=12, color="#f1f5f9", weight=ft.FontWeight.W_600, font_family="monospace"),
        ]),
        ft.Container(
            content=ft.Row([
                ft.Container(height=10, bgcolor=home_color,
                             border_radius=ft.BorderRadius.only(top_left=5, bottom_left=5), expand=home_pct),
                ft.Container(height=10, bgcolor=away_color,
                             border_radius=ft.BorderRadius.only(top_right=5, bottom_right=5), expand=away_pct),
            ], spacing=0),
            bgcolor="#0f172a", border=ft.Border.all(1, "#1e293b"), border_radius=5,
            padding=ft.Padding.all(2)),
    ], spacing=4)

def colored_badge_text(short_name, color, size=52, logo_b64=None):
    """req 19: short_name as default badge; show image if imported."""
    if logo_b64:
        return ft.Container(
            content=ft.Image(src=f"data:image/png;base64,{logo_b64}", fit=ft.BoxFit.COVER, border_radius=12),
            width=size, height=size, border_radius=12,
            border=ft.Border.all(1, "#ffffff22"))
    text_size = max(9, size // max(len(short_name), 1))
    return ft.Container(
        content=ft.Text(short_name, size=text_size, color="#FFFFFF",
                        weight=ft.FontWeight.W_900, text_align=ft.TextAlign.CENTER),
        width=size, height=size, bgcolor=color, border_radius=12,
        border=ft.Border.all(1, "#ffffff22"), alignment=ft.Alignment.CENTER)

def kit_dot(color):
    return ft.Container(width=10, height=10, bgcolor=color, border_radius=5,
                        border=ft.Border.all(1, "#334155"))

def action_btn(label, emoji, color, on_click, disabled=False, width=None):
    opacity = 0.35 if disabled else 1.0
    btn_color = color if not disabled else "#64748b"
    # A raw text emoji (e.g. "❌") depends on the OS/font providing a
    # color-emoji glyph, which packaged Flutter release builds don't
    # always have — it silently falls back to a "missing glyph"
    # placeholder there, which is what showed up as a bare "!" on the
    # Mark Incomplete buttons. ft.Icons are bundled directly inside every
    # Flet app's own icon font, so they always render identically
    # regardless of platform/OS font availability. Pass an ft.Icons value
    # instead of a string to use one.
    # A raw text emoji (e.g. "❌") depends on the OS/font providing a
    # color-emoji glyph, which packaged Flutter release builds don't
    # always have — it silently falls back to a "missing glyph"
    # placeholder there, which is what showed up as a bare "!" on the
    # Mark Incomplete buttons. ft.Icons are bundled directly inside every
    # Flet app's own icon font, so they always render identically
    # regardless of platform/OS font availability. Pass an ft.Icons value
    # instead of a string to use one. (Checked via "not a string" rather
    # than isinstance(emoji, ft.Icons) — ft.Icons is a proxy wrapper, not
    # the actual enum class, so isinstance() against it raises a TypeError.)
    icon_widget = (ft.Text(emoji, size=16) if isinstance(emoji, str)
                   else ft.Icon(emoji, size=16, color=btn_color))
    return ft.Container(
        content=ft.Row([
            icon_widget,
            ft.Text(label, size=11, color=btn_color, weight=ft.FontWeight.BOLD),
        ], spacing=6),
        bgcolor=(color+"14" if not disabled else "#0a0f1e"),
        border=ft.Border.all(1, color+"44" if not disabled else "#1e293b"),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        on_click=(None if disabled else on_click),
        ink=not disabled, opacity=opacity, width=width,
    )


# ═══════════════════════════════════════════════════════════════════════════════
class StatTrackerApp:

    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_page()
        # First paint: render the logo invisible/small, then immediately
        # trigger the fade+scale-in transition on the next tick so the
        # animation actually plays instead of snapping straight to place.
        self.page.controls = [self._build_splash_screen(0.02, "Starting up…", first_paint=True)]
        self.page.update()
        self._splash_tick(0.04, "Starting up…", delay=0.05)

        # Web build only: storage.py's file-based persistence writes into
        # Pyodide's in-memory virtual filesystem (flet build web runs the
        # whole app as a Python-compiled-to-WASM interpreter inside the
        # visitor's browser tab) — it survives fine *within* a session but
        # is thrown away completely the moment the tab reloads or closes,
        # which is why the web build previously always "opened with no
        # matches" even for a returning user. is_web is computed here
        # (rather than further down, where it used to live) specifically
        # so it's available before the load below needs it.
        self.is_web = bool(getattr(self.page, "web", False))
        self._web_prefs = None
        if self.is_web:
            try:
                self._web_prefs = ft.SharedPreferences()
                self.page.services.append(self._web_prefs)
            except Exception as ex:
                print(f"[Storage-Web] Could not create SharedPreferences service: {ex}")
            else:
                if hasattr(self.page, "run_task"):
                    try:
                        self.page.run_task(self._load_web_data_async)
                    except Exception as ex:
                        print(f"[Storage-Web] Could not schedule initial load: {ex}")

        self.matches: List[Match] = [] if self.is_web else load_matches()   # req 16: no sample match
        self._splash_tick(0.28, "Loading saved matches…")

        self.active_match_idx: int = 0
        self.active_tab: str = "LOGGER"
        self.log_team: str = "home"   # always SCC — team stats only, no player selection
        # req 20-23 action tracking
        self.action_category: str = "Attack"
        self.last_logged_action: Optional[str] = None
        self.can_convert: bool = False
        # Defensive "Goals Given" conversion — only clickable once Save or
        # Block (the defensive interrupt actions) has just been logged.
        self.can_defence_convert: bool = False
        self.fullscreen_video: bool = False   # fullscreen video logging layout
        # Logger identity (asked on first launch, changeable later, included in exports)
        # — same Pyodide-virtual-FS caveat as matches above: on web these
        # start blank/default here and get filled in (if previously saved)
        # by _load_web_data_async, scheduled a little further down.
        self.logger_name: str = "" if self.is_web else (get_logger_name() or "")
        # App mode: "inputter" (log stats, optionally receive a remote video
        # feed) or "camera" (capture + stream video to an Inputter device).
        # Two devices on the same network/cable can run one each.
        _stored_mode = None if self.is_web else get_app_mode()
        self.app_mode: str = _stored_mode or "inputter"
        self._app_mode_ever_chosen: bool = _stored_mode is not None
        self._splash_tick(0.45, "Loading your profile…")

        self.camera_mode_streaming: bool = False
        self._mjpeg_server: Optional[_ThreadingMJPEGServer] = None
        self._mjpeg_server_thread: Optional[threading.Thread] = None
        self._latest_jpeg_frame: Optional[bytes] = None
        # Notified every time a new frame is written to
        # _latest_jpeg_frame (see the 4 assignment sites — cv2's
        # _encode_frame, the take_picture() poll loop, and the two
        # wireless-camera receive paths). _MJPEGRequestHandler's serving
        # loop waits on this instead of busy-polling — see its comment
        # for why that distinction genuinely matters (measurable GIL
        # contention from a tight sleep(0.001) loop, confirmed by "Camera
        # Mode's local preview only slows down once another device
        # connects" — a Condition-based wait consumes no GIL time whilst
        # actually waiting, unlike a sleep loop that wakes up ~1000x/sec).
        self._new_frame_cond = threading.Condition()
        # Pairing handshake (Camera Mode = server/receiver of the request,
        # Inputter Mode = the connecting device that shows the code):
        #   idle → pending (code + 4 choices generated) → approved/rejected
        self.pair_status: str = "idle"
        self.pair_pending_code: Optional[int] = None
        self.pair_choices: list = []
        self._camera_mode_poll_stop = threading.Event()
        # Possession tracking — accumulates real seconds per side while the
        # match timer is running; percentages are computed from these.
        # Auto-switches to the conceding team whenever a goal is logged.
        # (Match.possession_team defaults to None on the model itself.)
        # Camera source (supports multiple / external / wireless cameras).
        # On Android/iOS this is "native:back" or "native:front" (the
        # on-device camera via flet-camera — no OpenCV involved); on
        # desktop it's an int device index; on any platform it can also be
        # an "http(s)://" URL for a wireless/IP camera or a paired Camera
        # Mode device, pulled with a pure-Python MJPEG reader either way.
        self.is_mobile = self.page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
        # (self.is_web is now set earlier, right before matches are loaded
        # — see the comment there.) page.platform on web reports the
        # *visitor's OS*, not "web" — so is_mobile above could otherwise
        # misclassify e.g. a web visitor on Windows as a desktop client
        # and try to open a server-side OpenCV camera, which makes no
        # sense for a hosted web app (there's no camera attached to the
        # server, and opencv-python isn't even installed for the web
        # build — see pyproject.toml's [tool.flet.web] section).
        # flet-camera *is* now installed there instead, since it supports
        # browser camera access (getUserMedia) the same way it supports
        # Android/iOS — see the native: branch in _start_camera.
        # "native:back" (browser/on-device camera via flet-camera) is
        # DISABLED as a default for now — see the long comment on
        # HAS_FLET_CAMERA / _build_web_camera_source_picker below for
        # why: a systemic bug in flet-camera 0.86.5's own compiled event
        # handling (confirmed via browser DevTools showing it break on
        # initialize, pause_preview, AND frame streaming — not just one
        # isolated call) makes the whole plugin currently unreliable on
        # both Android and web. Wireless/IP camera (0, meaning "no local
        # source, use the URL field") is the one path that's been solid
        # throughout, so it's the default everywhere now, same as
        # desktop always was.
        self.camera_source = 0
        self.mobile_camera_lens = "back"  # "back" or "front" — mirrors camera_source on mobile
        self.detected_cameras: list = []  # list of confirmed-working device indices, filled by _detect_cameras
        self.camera_scanning = False
        self._camera_scan_ran_once = False  # distinguishes "never scanned" from "scanned, found nothing"
        self.wireless_discovering = False   # True while listening for Camera Mode broadcasts
        self.discovered_cameras: list = []  # [{"name": str, "url": str}, ...] found via UDP discovery
        self._auto_camera_scan_done = False     # ensures the local-device auto-scan below only fires once per session
        self._auto_wireless_scan_done = False   # same, for the wireless auto-discovery listen
        self._native_camera_ctrl = None   # lazily-created flet_camera.Camera instance
        self._stc_preview_ctrl = None     # lazily-created stc_camera_preview.StcCameraPreview instance
        self._native_camera_ready = False
        self._native_camera_busy = False  # guards against overlapping start/stop
                                           # operations on the same native camera
                                           # control racing each other — the actual
                                           # cause of a Dart "Concurrent modification
                                           # during iteration" error seen when
                                           # switching camera lens while a previous
                                           # start was still in flight: the old
                                           # lens-switch handler fired an unawaited
                                           # stop immediately followed by a new
                                           # start, so both ran concurrently against
                                           # the same underlying native object.
        self._native_frame_count = 0   # bumped by _on_native_camera_frame — used to detect "stream started but no frames ever arrived"
        self._file_picker = None          # lazily-created ft.FilePicker Service, shared by export/import
        self.camera_source_url_field = ft.TextField(
            hint_text="Or enter IP camera URL e.g. http://192.168.1.5:8080/video",
            dense=True, text_size=11, color=TEXT, hint_style=ft.TextStyle(color=MUTED2),
            bgcolor=SURFACE, border_color=BORDER, focused_border_color=INDIGO, expand=True,
            on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        # Camera (live video feed shown on Logger tab — manual logging only)
        self.camera_on = False
        self.camera_error = None
        self.camera_error_text = ft.Text("", size=11, color=ROSE)   # persistent ref — updated in place
        # Persistent clock text for fullscreen mode — updated in place each
        # timer tick instead of via full_refresh, which would tear down and
        # freeze the live video (same issue the video freeze fix addressed).
        self.fs_clock_text = ft.Text("0'00\"", size=14, color=TEXT2,
                                     weight=ft.FontWeight.BOLD, font_family="monospace")
        # Same reasoning, extended to the whole fullscreen layout: every stat
        # button press calls _full_refresh(), which used to rebuild
        # _build_fullscreen_logger()'s entire ~200-line widget tree from
        # scratch and reassign page.controls to a brand new top-level object
        # every single time — even though the camera control itself
        # (self._stc_preview_ctrl) is a cached, reused Python object deeper
        # in that tree, wrapping it in an entirely new parent chain on every
        # refresh was enough to make the client tear down and remount it
        # (visible as the whole fullscreen view "reloading" on every button
        # press). These 5 slots are created once and kept for the life of
        # the app; _build_fullscreen_logger() now only ever updates each
        # slot's own .content in place and returns the same stable
        # self._fs_skeleton object every time, rather than building a new
        # top-level tree per call — page.controls ends up being reassigned
        # to a list containing that same object reference on every refresh,
        # which is a structural no-op for Flet's diffing, leaving the real
        # work scoped to each slot's own (much smaller) subtree instead.
        self._fs_skeleton = None
        self.fs_left_slot = ft.Container(expand=False)
        self.fs_top_slot = ft.Container(expand=False)
        self.fs_video_slot = ft.Container(expand=True)
        self.fs_bottom_slot = ft.Container(expand=False)
        self.fs_right_slot = ft.Container(expand=False)
        self._cv2_cap = None
        self._camera_capture_stop = threading.Event()
        self.camera_image = ft.Image(
            src=f"data:image/png;base64,{_PLACEHOLDER_PNG_B64}",
            fit=ft.BoxFit.COVER, border_radius=16, width=640, height=360,
            # Without this, Flutter briefly shows nothing every time `src`
            # changes (each new video frame) while it decodes the new image —
            # that's exactly the blinking/flicker effect. gapless_playback
            # keeps the previous frame visible until the new one is ready.
            gapless_playback=True)
        self._splash_tick(0.68, "Preparing video system…")

        # Timer (req 10)
        self._timer_running = False
        self._timer_lock = threading.Lock()
        # Shared controls
        self.scoreboard_ref  = ft.Container()
        self.tab_bar_ref     = ft.Row(spacing=2)
        self.tab_content_ref = ft.Container(expand=True)
        # Tracks whether any text field in the app currently has focus, so
        # the global keyboard-shortcut handler below can ignore keystrokes
        # while someone is actually typing into a box. Every ft.TextField
        # in the app wires on_focus/on_blur to _mark_input_focused /
        # _mark_input_blurred for this reason.
        self._text_input_focused = False
        self.page.on_keyboard_event = self._on_keyboard
        self.page.snack_bar = ft.SnackBar(content=ft.Text("", color=TEXT), bgcolor=SURFACE)
        self._launch_autosave_loop()
        self._splash_tick(0.90, "Building interface…")

        self._build_ui()
        self._splash_tick(1.0, "Ready!")
        time.sleep(0.35)   # let 100% register on screen before switching over
        self._full_refresh()
        if not self.logger_name:
            self._open_name_dialog(first_launch=True)
        elif not self._app_mode_ever_chosen:
            self._open_mode_dialog(first_launch=True)

    def _setup_page(self):
        p = self.page
        p.title = "Stat Tracker v4"
        p.bgcolor = BG
        p.theme_mode = ft.ThemeMode.DARK
        p.padding = 0
        p.window.width = 1280
        p.window.height = 900
        p.window.min_width = 900
        p.window.min_height = 620
        # Passive best-effort save on disconnect — see _on_disconnect for
        # why this replaced the earlier prevent_close-based approach.
        p.on_disconnect = self._on_disconnect
        # Window icons need a real file on disk (not a data URI) — the
        # asset was saved alongside main.py at build time.
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
            if os.path.exists(icon_path):
                p.window.icon = icon_path
        except Exception as ex:
            print(f"[Splash] Could not set window icon: {ex}")
        p.theme = ft.Theme(color_scheme=ft.ColorScheme(
            primary=INDIGO6, surface=SURFACE, on_primary=TEXT))

    def _on_disconnect(self, e=None):
        """Passive best-effort save when the client disconnects (window
        closing is one of several things that can trigger this — network
        drop is another, on a web build). Unlike the previous
        prevent_close-based approach, this CANNOT block or interfere with
        the window actually closing — it's purely a notification that
        fires as/after the disconnect happens, with no way to prevent it.
        That safety property is exactly why this replaced the earlier
        approach: prevent_close required a Python handler to explicitly
        grant permission to close, and that mechanism failed to reliably
        fire in practice, making the app completely unclosable outside of
        Task Manager — a far worse outcome than occasionally missing the
        very last few seconds of unsaved changes, which is already well
        covered by saving after nearly every action plus the 60s autosave
        loop regardless of whether this fires at all."""
        try:
            self._save()
            print("[Disconnect] Match data saved.")
        except Exception as ex:
            print(f"[Disconnect] Save failed: {type(ex).__name__}: {ex}")

    def _build_splash_screen(self, pct: float, label: str, first_paint: bool = False):
        """Branded loading screen shown while the app initializes. Progress
        reflects real startup steps (loading settings, loading saved
        matches, preparing the video system, building the UI) rather than
        an arbitrary timed animation.

        The logo/badge fades and scales in on first paint, and gently
        "breathes" (subtle scale pulse) for the remainder of startup so the
        screen never feels static while real work is happening in the
        background.
        """
        logo = ft.Image(
            src=f"data:image/jpeg;base64,{SPLASH_JPG_B64}",
            width=300, height=300, fit=ft.BoxFit.CONTAIN, border_radius=20,
        )
        logo_wrap = ft.Container(
            content=logo,
            scale=ft.Scale(0.82 if first_paint else (1.0 if pct < 1.0 else 1.04)),
            opacity=0.0 if first_paint else 1.0,
            animate_scale=ft.Animation(650, ft.AnimationCurve.EASE_OUT_BACK),
            animate_opacity=ft.Animation(550, ft.AnimationCurve.EASE_OUT),
        )

        bar = ft.Container(
            content=ft.ProgressBar(value=max(0.02, pct), width=320, height=8,
                                    color=INDIGO4, bgcolor=SURFACE2, border_radius=4),
            width=320,
            opacity=0.0 if first_paint else 1.0,
            animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        )

        pct_text = ft.Text(f"{int(pct * 100)}%", size=12, color=INDIGO4,
                            weight=ft.FontWeight.BOLD, font_family="monospace")

        return ft.Container(
            content=ft.Column([
                ft.Container(expand=True),
                logo_wrap,
                ft.Container(height=28),
                bar,
                ft.Container(height=10),
                ft.Row([
                    ft.AnimatedSwitcher(
                        content=ft.Text(label, key=label, size=12, color=MUTED,
                                        weight=ft.FontWeight.W_500),
                        transition=ft.AnimatedSwitcherTransition.FADE,
                        duration=250,
                    ),
                    ft.Container(expand=True),
                    pct_text,
                ], width=320),
                ft.Container(expand=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, expand=True),
            bgcolor=BG, alignment=ft.Alignment.CENTER, expand=True)

    def _splash_tick(self, pct: float, label: str, delay: float = 0.0):
        """Push one splash-screen progress update to the client, animating
        the transition in from the previous state."""
        try:
            self.page.controls = [self._build_splash_screen(pct, label)]
            self.page.update()
            if delay:
                time.sleep(delay)
        except Exception as ex:
            print(f"[Splash] tick failed: {ex}")

    @property
    def match(self) -> Optional[Match]:
        if not self.matches:
            return None
        idx = min(self.active_match_idx, len(self.matches)-1)
        return self.matches[idx]

    def _snack(self, msg, color=EMERALD):
        self.page.snack_bar.content = ft.Text(msg, color=color)
        self.page.snack_bar.open = True
        try: self.page.update()
        except Exception: pass

    _WEB_DATA_KEY = "stattracker_web_data_v1"

    def _save(self):
        save_matches(self.matches)   # harmless on web (writes into
                                      # Pyodide's throwaway virtual FS,
                                      # same as always) — actual web
                                      # persistence is _save_web() below.
        if self.is_web:
            self._save_web()

    def _save_web(self):
        """Mirror matches + settings into browser localStorage (via
        ft.SharedPreferences) so the web build survives a reload. Fires
        on every normal save — autosave every 60s, plus every explicit
        _save() call elsewhere (goal logged, match edited, etc.) — the
        same way save_matches() already does for desktop/mobile."""
        if not self._web_prefs or not hasattr(self.page, "run_task"):
            return
        try:
            self.page.run_task(self._save_web_async)
        except Exception as ex:
            print(f"[Storage-Web] Could not schedule save: {ex}")

    async def _save_web_async(self):
        try:
            payload = json.dumps({
                "matches": [m.to_dict() for m in self.matches],
                "settings": {"logger_name": self.logger_name, "app_mode": self.app_mode},
            })
            await self._web_prefs.set(self._WEB_DATA_KEY, payload)
        except Exception as ex:
            print(f"[Storage-Web] Save failed: {ex}")

    async def _load_web_data_async(self):
        """Web build only — scheduled once from __init__, right after the
        SharedPreferences service is created. Runs concurrently with the
        rest of (synchronous) __init__ and finishes shortly after it, so
        the app briefly shows "no matches" / a blank logger name before
        this fills them in and refreshes — same brief-then-corrects
        pattern already used for the native camera's async init."""
        if not self._web_prefs:
            return
        try:
            raw = await self._web_prefs.get(self._WEB_DATA_KEY)
            if not raw:
                return
            data = json.loads(raw)
            loaded_matches = [Match.from_dict(d) for d in data.get("matches", [])]
            if loaded_matches:
                self.matches = loaded_matches
                if self.active_match_idx >= len(self.matches):
                    self.active_match_idx = 0
            settings = data.get("settings", {})
            if settings.get("logger_name"):
                self.logger_name = settings["logger_name"]
            if settings.get("app_mode"):
                self.app_mode = settings["app_mode"]
                self._app_mode_ever_chosen = True
            self._full_refresh()
        except Exception as ex:
            print(f"[Storage-Web] Load failed: {ex}")

    def _launch_autosave_loop(self):
        """Launch the 60s autosave loop using the same 3-tier strategy as
        _launch_timer_thread: a raw threading.Thread here was crashing the
        web build outright with "RuntimeError: can't start new thread" —
        Pyodide/WASM (flet build web) doesn't support spawning real OS
        threads the way desktop/mobile do, and this ran unconditionally
        from __init__ on every session, so every web session crashed on
        load. page.run_task schedules the async twin on Flet's own event
        loop instead, which works the same on web, desktop, and mobile —
        raw threading.Thread is now only a last-resort fallback."""
        started_via = None
        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(self._autosave_loop_async)
                started_via = "page.run_task (async)"
            except Exception as ex:
                print(f"[Autosave] page.run_task failed: {type(ex).__name__}: {ex}")
        if not started_via and hasattr(self.page, "run_thread"):
            try:
                self.page.run_thread(self._autosave_loop)
                started_via = "page.run_thread (sync)"
            except Exception as ex:
                print(f"[Autosave] page.run_thread failed: {type(ex).__name__}: {ex}")
        if not started_via:
            if self.is_web:
                # A raw OS thread is the one thing that genuinely cannot
                # work on web — if both async and page.run_thread are
                # unavailable there's nothing safe left to fall back to,
                # so skip autosave entirely rather than crashing the
                # session. Manual saves (Export TXT, on_disconnect, etc.)
                # still work normally.
                print("[Autosave] No web-safe scheduling mechanism available — autosave disabled for this session.")
                return
            threading.Thread(target=self._autosave_loop, daemon=True).start()
            started_via = "raw threading.Thread (fallback)"
        print(f"[Autosave] Started via: {started_via}")

    async def _autosave_loop_async(self):
        """Async twin of _autosave_loop — identical save logic, scheduled
        on Flet's own event loop via page.run_task so it works under
        Pyodide (web) as well as desktop/mobile."""
        import asyncio
        while True:
            await asyncio.sleep(60)
            try: self._save()
            except Exception: pass

    def _autosave_loop(self):
        while True:
            time.sleep(60)
            try: self._save()
            except Exception: pass

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        self.page.controls = [
            ft.Column([
                self._build_navbar(),
                self.scoreboard_ref,
                ft.Container(
                    content=self.tab_bar_ref,
                    bgcolor=SURFACE,
                    border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=6)),
                ft.Container(content=self.tab_content_ref, expand=True, bgcolor=BG,
                             padding=ft.Padding.symmetric(horizontal=16, vertical=12)),
            ], spacing=0, expand=True),
        ]
        self.page.update()

    def _logger_name_pill(self):
        name = self.logger_name or "Set your name"
        color = INDIGO if self.logger_name else AMBER
        return ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.PERSON, size=10, color=color),
                            ft.Text(name, size=9, color=TEXT, weight=ft.FontWeight.BOLD)], spacing=3),
            bgcolor=color+"33", border=ft.Border.all(1, color+"88"),
            border_radius=20, padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            on_click=self._open_name_dialog, ink=True, tooltip="Click to change your name")

    def _build_navbar(self):
        brand = ft.Row([
            ft.Container(
                content=ft.Image(src=f"data:image/png;base64,{ICON_SMALL_PNG_B64}",
                                 fit=ft.BoxFit.COVER, border_radius=10),
                width=36, height=36, border_radius=10,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
            ft.Column([
                ft.Row([ft.Text("STAT TRACKER", size=15, color=TEXT, weight=ft.FontWeight.W_900),
                        pill("v4 Live", INDIGO),
                        self._logger_name_pill()], spacing=4),
                txt("Real-Time Tactical Logging & Analytics", size=9, color=MUTED2, mono=True),
            ], spacing=1),
        ], spacing=8)

        self.match_dd = ft.Dropdown(
            dense=True, text_size=11, color=TEXT, bgcolor=SURFACE,
            border_color=BORDER, focused_border_color=INDIGO,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            on_select=self._on_match_select, width=270)
        self._refresh_match_dd()

        def nav_btn(icon, label, color, tooltip, on_click, bg=None):
            return ft.Button(
                content=ft.Row([ft.Icon(icon, size=13, color=color),
                                ft.Text(label, size=11, color=color, weight=ft.FontWeight.BOLD)], spacing=5),
                bgcolor=bg or SURFACE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                     side=ft.BorderSide(1, color+"44"),
                                     padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                on_click=on_click, tooltip=tooltip)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    brand, ft.Container(expand=True),
                    txt("Fixture:", size=10, color=MUTED2),
                    self.match_dd,
                    ft.Button(
                        content=ft.Row([ft.Icon(ft.Icons.ADD, size=13, color="#fff"),
                                        ft.Text("New Match", size=11, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
                        bgcolor=INDIGO6,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                             padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                        on_click=self._open_new_match_dialog),
                ], spacing=8),
                # Secondary actions in their own horizontally-scrollable strip
                # so they can never get clipped off the edge of the window,
                # regardless of window width.
                ft.Row([
                    nav_btn(ft.Icons.MENU_BOOK, "Dictionary", AMBER,
                            "Action dictionary", self._open_dictionary_dialog),
                    nav_btn(ft.Icons.PALETTE, "Kit Colours", PURPLE4,
                            "Manage kit colours (req 13-15)", self._open_kit_colours_dialog),
                    nav_btn(ft.Icons.EDIT, "Edit Match", INDIGO4,
                            "Edit match details after creation", self._open_edit_match_dialog),
                    nav_btn(ft.Icons.DOWNLOAD, "Export TXT", EMERALD,
                            "Export stats, sequences & timestamps to TXT", lambda _: self._export_txt()),
                    nav_btn(ft.Icons.UPLOAD, "Import TXT", SKY,
                            "Re-import a previously exported TXT match file", lambda _: self._import_txt()),
                    nav_btn(ft.Icons.DEVICES, "Device Mode", EMERALD,
                            "Switch between Inputter Mode and Camera Mode",
                            lambda _: self._open_mode_dialog()),
                    nav_btn(ft.Icons.DELETE_OUTLINE, "Delete", ROSE,
                            "Delete current match (req 24)", self._confirm_delete_match),
                ], spacing=8, scroll=ft.ScrollMode.AUTO),
            ], spacing=10),
            bgcolor=SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.Padding.symmetric(horizontal=20, vertical=10))

    def _full_refresh(self):
        # camera_error_text is a persistent Text ref placed in the video
        # panel, but nothing was ever writing self.camera_error into its
        # .value — every camera failure (including whatever the actual
        # exception is on a given device) was being silently swallowed,
        # with the camera just appearing to "not work" and no visible
        # explanation anywhere. Syncing it here, once, at the top of every
        # refresh guarantees it's always current regardless of which of
        # the many code paths set self.camera_error.
        self.camera_error_text.value = self.camera_error or ""
        m = self.match

        if self.app_mode == "camera":
            # Camera Mode is a completely different, minimal screen — no
            # stat logging UI at all, just capture + stream controls. It
            # takes priority over every other mode.
            if not getattr(self, "_camera_mode_poller_running", False):
                self._camera_mode_poller_running = True
                self._launch_camera_mode_poller()
            self.page.controls = [self._build_camera_mode_screen()]
            self.page.padding = 0
            try: self.page.update()
            except Exception: pass
            return

        if self.fullscreen_video and m:
            # True fullscreen: replace the ENTIRE page content with just the
            # video logging layout — no navbar, scoreboard, or tab bar. Before
            # this fix, fullscreen mode only swapped the tab's inner content,
            # so the navbar/scoreboard/tabbar stayed visible above it and the
            # video never actually took up the whole screen.
            self.page.controls = [self._build_fullscreen_logger(m)]
            self.page.padding = 0
            try: self.page.update()
            except Exception: pass
            return

        self.page.padding = 0
        self._refresh_match_dd()
        self.scoreboard_ref.content = self._build_scoreboard(m) if m else self._build_empty_scoreboard()
        self.tab_bar_ref.controls = self._build_tab_buttons()
        self.tab_content_ref.content = self._build_active_tab(m)
        # Rebuild the whole normal-mode wrapper fresh each time so we can
        # reliably switch back from fullscreen mode (which replaces
        # page.controls entirely) to the normal layout.
        self.page.controls = [
            ft.Column([
                self._build_navbar(),
                self.scoreboard_ref,
                ft.Container(
                    content=self.tab_bar_ref,
                    bgcolor=SURFACE,
                    border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=6)),
                ft.Container(content=self.tab_content_ref, expand=True, bgcolor=BG,
                             padding=ft.Padding.symmetric(horizontal=16, vertical=12)),
            ], spacing=0, expand=True),
        ]
        try: self.page.update()
        except Exception: pass

    def _build_tab_buttons(self):
        tabs = [
            (ft.Icons.GRID_VIEW,           "Logger",    "LOGGER"),
            (ft.Icons.FORMAT_LIST_BULLETED, "Timeline",  "TIMELINE"),
            (ft.Icons.BAR_CHART,           "Stats",     "STATS"),
        ]
        btns = []
        for icon, lbl, tid in tabs:
            active = self.active_tab == tid
            def _click(_, t=tid):
                self.active_tab = t
                self._full_refresh()
            btns.append(ft.TextButton(
                content=ft.Row([
                    ft.Icon(icon, size=13, color=INDIGO4 if active else MUTED2),
                    ft.Text(lbl, size=11, color=INDIGO4 if active else MUTED,
                            weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL),
                ], spacing=5),
                style=ft.ButtonStyle(
                    bgcolor=INDIGO+"22" if active else "transparent",
                    overlay_color=INDIGO+"22",
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
                on_click=_click))
        return btns

    def _build_active_tab(self, m):
        if not m:
            return self._build_no_match_placeholder()
        if self.active_tab == "LOGGER":    return self._build_logger_tab(m)
        if self.active_tab == "TIMELINE":  return self._build_timeline_tab(m)
        if self.active_tab == "STATS":     return self._build_stats_tab(m)
        return ft.Container()

    def _build_no_match_placeholder(self):
        return card(ft.Column([
            ft.Icon(ft.Icons.SPORTS_SOCCER, size=56, color=BORDER2),
            ft.Text("No Matches Yet", size=18, color=TEXT, weight=ft.FontWeight.BOLD),
            txt("Create a new match above, or load SCC fixtures automatically.", size=12, color=MUTED),
            ft.Button(
                content=ft.Row([ft.Icon(ft.Icons.ADD, size=14, color="#fff"),
                                ft.Text("Create Match", size=12, color="#fff")], spacing=6),
                bgcolor=INDIGO6,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                     padding=ft.Padding.symmetric(horizontal=18, vertical=10)),
                on_click=self._open_new_match_dialog),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16), padding=60)

    # ── Scoreboard ────────────────────────────────────────────────────────────
    def _build_empty_scoreboard(self):
        return ft.Container(
            content=txt("No fixture loaded — create or load a match to begin.", size=11, color=MUTED2),
            bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=12,
            padding=ft.Padding.symmetric(horizontal=20, vertical=10),
            margin=ft.Margin.symmetric(horizontal=16, vertical=4))

    def _build_scoreboard_compact(self, m: Match):
        """Mobile scoreboard. The desktop version's team-name / kit-dots /
        xG rows wrap onto several lines once squeezed into a phone-width
        column, which was ballooning the (fixed, non-scrolling) header to
        roughly half the screen and leaving barely any room for the
        scrollable Logger content below it — this is a deliberately
        shorter layout instead: single-line team short names (no wrap),
        no kit dots / school name / per-team xG row, smaller score digits.
        Full team details are still one tap away via the team-name pill in
        the Logger tab and the Stats tab."""
        live_label = "LIVE" if m.is_live else ("SCHEDULED" if m.period == "SCHEDULED" else "ENDED")
        live_color = EMERALD if m.is_live else (INDIGO if m.period == "SCHEDULED" else MUTED2)
        is_running = self._timer_running

        def _score_adj_btn(team, delta, icon, color):
            return ft.IconButton(icon=icon, icon_size=11, icon_color=color,
                                 on_click=lambda _: self._update_score(team, delta),
                                 style=ft.ButtonStyle(padding=ft.Padding.all(2), bgcolor=SURFACE,
                                                      shape=ft.RoundedRectangleBorder(radius=5),
                                                      side=ft.BorderSide(1, BORDER)))

        def team_chip(team, color, align_end=False):
            row_children = [
                colored_badge_text(team.short_name, color, size=32),
                ft.Text(team.short_name, size=13, color=TEXT, weight=ft.FontWeight.W_800,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ]
            if align_end: row_children.reverse()
            return ft.Row(row_children, spacing=6,
                          alignment=ft.MainAxisAlignment.END if align_end else ft.MainAxisAlignment.START)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Row([ft.Icon(ft.Icons.PLACE, size=11, color=MUTED2),
                            ft.Text(m.location or m.date, size=10, color=MUTED2,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=3, expand=True),
                    ft.Container(
                        content=ft.Row([ft.Container(width=6, height=6, bgcolor=live_color, border_radius=3),
                                        ft.Text(live_label, size=9, color=live_color, weight=ft.FontWeight.BOLD)], spacing=4),
                        bgcolor=live_color+"22", border=ft.Border.all(1, live_color+"44"),
                        border_radius=7, padding=ft.Padding.symmetric(horizontal=6, vertical=2)),
                ], spacing=8),
                ft.Row([
                    ft.Container(content=team_chip(m.home_team, m.home_team.logo_color), expand=True),
                    ft.Row([
                        ft.Text(str(m.home_score), size=30, color=INDIGO4, weight=ft.FontWeight.W_900, font_family="monospace"),
                        ft.Text(":", size=18, color=BORDER2, font_family="monospace"),
                        ft.Text(str(m.away_score), size=30, color=INDIGO4, weight=ft.FontWeight.W_900, font_family="monospace"),
                    ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(content=team_chip(m.away_team, m.away_team.logo_color, align_end=True), expand=True),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                ft.Row([
                    _score_adj_btn("home", -1, ft.Icons.REMOVE, MUTED2),
                    _score_adj_btn("home", 1, ft.Icons.ADD, INDIGO4),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Icon(ft.Icons.PAUSE if is_running else ft.Icons.PLAY_ARROW,
                                        size=13, color=AMBER if is_running else TEXT),
                        width=26, height=26, bgcolor=AMBER+"22" if is_running else INDIGO6,
                        border_radius=7, border=ft.Border.all(1, AMBER+"44" if is_running else INDIGO3+"44"),
                        on_click=self._toggle_timer, ink=True, alignment=ft.Alignment.CENTER),
                    ft.Text(f"{m.minute}'{getattr(m,'second',0):02d}\"", size=12, color=TEXT2,
                            weight=ft.FontWeight.BOLD, font_family="monospace"),
                    ft.Container(expand=True),
                    _score_adj_btn("away", 1, ft.Icons.ADD, EMERALD),
                    _score_adj_btn("away", -1, ft.Icons.REMOVE, MUTED2),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=2),
            ], spacing=6),
            bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=14,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            margin=ft.Margin.symmetric(horizontal=10, vertical=5))

    def _build_scoreboard(self, m: Match):
        if self.is_mobile:
            return self._build_scoreboard_compact(m)
        period_color = AMBER if m.period == "OVERTIME" else INDIGO if m.period == "SCHEDULED" else MUTED2
        live_label   = "LIVE" if m.is_live else ("SCHEDULED" if m.period == "SCHEDULED" else "ENDED")
        live_color   = EMERALD if m.is_live else (INDIGO if m.period == "SCHEDULED" else MUTED2)

        meta_row = ft.Row([
            ft.Row([ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=MUTED2),
                    txt(m.date, size=11),
                    ft.Container(width=6),
                    ft.Icon(ft.Icons.PLACE, size=12, color=MUTED2),
                    txt(m.location, size=11),
                    ], spacing=4),
            ft.Row([
                ft.Container(
                    content=ft.Text(PERIOD_LABELS.get(m.period, m.period),
                                    size=10, color=period_color, weight=ft.FontWeight.BOLD, font_family="monospace"),
                    bgcolor=period_color+"22", border=ft.Border.all(1, period_color+"55"),
                    border_radius=8, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    on_click=lambda _: (advance_period(m), self._save(), self._full_refresh()), ink=True),
                ft.Container(
                    content=ft.Row([ft.Container(width=7, height=7, bgcolor=live_color, border_radius=4),
                                    txt(live_label, size=10, color=live_color, weight=ft.FontWeight.BOLD)], spacing=4),
                    bgcolor=live_color+"22", border=ft.Border.all(1, live_color+"44"),
                    border_radius=8, padding=ft.Padding.symmetric(horizontal=8, vertical=3)),
            ], spacing=6),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        def _kit_dots(team: Team):
            cols = team.kit_colors or [team.kit_color_primary, team.kit_color_secondary]
            return ft.Row([kit_dot(c) for c in cols[:6]], spacing=3)

        def _score_adj_btn(team, delta, icon, color):
            return ft.IconButton(icon=icon, icon_size=12, icon_color=color,
                                 on_click=lambda _: self._update_score(team, delta),
                                 style=ft.ButtonStyle(padding=ft.Padding.all(3), bgcolor=SURFACE,
                                                      shape=ft.RoundedRectangleBorder(radius=6),
                                                      side=ft.BorderSide(1, BORDER)))

        home = m.home_team; away = m.away_team
        home_col = ft.Row([
            colored_badge_text(home.short_name, home.logo_color, logo_b64=home.logo_base64),
            ft.Column([
                ft.Text(home.name, size=14, color=TEXT, weight=ft.FontWeight.W_800),
                txt(f"{home.short_name} • Home • {home.team_rank}", size=10, color=MUTED, mono=True),
                txt(f"🏫 {home.school_name}", size=10, color=INDIGO3) if home.school_name else ft.Container(),
                _kit_dots(home),
                ft.Row([txt(f"xG {m.stats.home_xg:.2f}", size=11, color=INDIGO4, mono=True, weight=ft.FontWeight.BOLD),
                        _score_adj_btn("home", 1, ft.Icons.ADD, INDIGO4),
                        _score_adj_btn("home", -1, ft.Icons.REMOVE, MUTED2)], spacing=2),
            ], spacing=3),
        ], spacing=12)

        is_running = self._timer_running
        timer_btn = ft.Container(
            content=ft.Icon(ft.Icons.PAUSE if is_running else ft.Icons.PLAY_ARROW,
                            size=15, color=AMBER if is_running else TEXT),
            width=32, height=32,
            bgcolor=AMBER+"22" if is_running else INDIGO6,
            border_radius=8, border=ft.Border.all(1, AMBER+"44" if is_running else INDIGO3+"44"),
            on_click=self._toggle_timer, ink=True,
            alignment=ft.Alignment.CENTER)

        centre_col = ft.Column([
            ft.Row([
                ft.Text(str(m.home_score), size=52, color=INDIGO4, weight=ft.FontWeight.W_900, font_family="monospace"),
                ft.Text(":", size=28, color=BORDER2, font_family="monospace"),
                ft.Text(str(m.away_score), size=52, color=INDIGO4, weight=ft.FontWeight.W_900, font_family="monospace"),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(
                content=ft.Row([
                    timer_btn,
                    ft.Icon(ft.Icons.SCHEDULE, size=13, color=INDIGO4),
                    ft.Text(f"{m.minute}'{getattr(m,'second',0):02d}\"",
                            size=14, color=TEXT2, weight=ft.FontWeight.BOLD, font_family="monospace"),
                    ft.IconButton(icon=ft.Icons.REMOVE, icon_size=11, icon_color=MUTED2,
                                  on_click=lambda _: self._set_minute(max(0, self.match.minute - 1)),
                                  style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                    ft.IconButton(icon=ft.Icons.ADD, icon_size=11, icon_color=MUTED2,
                                  on_click=lambda _: self._set_minute(min(120, self.match.minute + 1)),
                                  style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=12,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)

        away_col = ft.Row([
            ft.Column([
                ft.Text(away.name, size=14, color=TEXT, weight=ft.FontWeight.W_800, text_align=ft.TextAlign.RIGHT),
                txt(f"{away.short_name} • Away • {away.team_rank}", size=10, color=MUTED, mono=True),
                txt(f"🏫 {away.school_name}", size=10, color=INDIGO3) if away.school_name else ft.Container(),
                _kit_dots(away),
                ft.Row([txt(f"xG {m.stats.away_xg:.2f}", size=11, color=EMERALD, mono=True, weight=ft.FontWeight.BOLD),
                        _score_adj_btn("away", 1, ft.Icons.ADD, EMERALD),
                        _score_adj_btn("away", -1, ft.Icons.REMOVE, MUTED2)], spacing=2),
            ], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.END),
            colored_badge_text(away.short_name, away.logo_color, logo_b64=away.logo_base64),
        ], spacing=12)

        return ft.Container(
            content=ft.Column([
                meta_row,
                ft.Row([
                    ft.Container(home_col, expand=4),
                    ft.Container(centre_col, expand=3,
                                 border=ft.Border.symmetric(vertical=ft.BorderSide(1, BORDER+"88")),
                                 padding=ft.Padding.symmetric(horizontal=12)),
                    ft.Container(away_col, expand=4, alignment=ft.Alignment.CENTER_RIGHT),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=12),
            bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=16,
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            margin=ft.Margin.symmetric(horizontal=16, vertical=6))

    # ══════════════════════════════════════════════════════════════════════════
    # Tab 1 — Logger  (req 20-23)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_logger_tab(self, m: Match):
        if self.fullscreen_video:
            return self._build_fullscreen_logger(m)

        team_row = ft.Row([
            ft.Icon(ft.Icons.SHIELD, size=13, color=m.home_team.logo_color),
            txt("Logging for:", size=10, color=MUTED2),
            ft.Container(
                content=ft.Text(m.home_team.short_name, size=11, color=TEXT, weight=ft.FontWeight.BOLD),
                bgcolor=m.home_team.logo_color, border_radius=8,
                padding=ft.Padding.symmetric(horizontal=14, vertical=7)),
            txt(f"({m.home_team.name})", size=10, color=MUTED2),
        ], spacing=8)

        # ① Actions (Attack / Defence / Cards tabs)  req 22
        cat_tabs = ft.Row([
            self._cat_tab("Attack",  EMERALD),
            self._cat_tab("Defence", INDIGO4),
            self._cat_tab("Cards",   AMBER),
        ], spacing=6)

        actions_section = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.GRID_VIEW, size=14, color=INDIGO4),
                    ft.Text("Actions", size=13, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True), cat_tabs], spacing=8),
            ft.Divider(height=1, color=BORDER),
            self._build_category_grid(m),
        ], spacing=10), padding=14)

        # ② Incompletes  req 21
        inc_section = self._build_incompletes_row()

        # ③ Substitution
        sub_section = self._quick_row("Substitution", "🔄", SKY,
                                      lambda _: self._quick_action("SUBSTITUTION", "Substitution"))

        # ④ Turnover
        turn_section = self._quick_row("Turnover", "🔁", ROSE, self._log_turnover)

        # ⑤ Conversion + Goals / Assists  req 23
        conv_disabled = not self.can_convert
        conv_hint = ("✓ Attack action logged — Conversion available"
                     if not conv_disabled else "Press an attack action first")
        hint_col  = EMERALD if not conv_disabled else AMBER
        conv_section = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=EMERALD),
                    ft.Text("Conversions & Goals / Assists", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(content=txt(conv_hint, size=9, color=hint_col),
                                 bgcolor=hint_col+"22", border=ft.Border.all(1, hint_col+"44"),
                                 border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2))], spacing=8),
            ft.Row([
                action_btn("Conversion ✅", "✅", EMERALD, self._log_conversion, disabled=conv_disabled),
                action_btn("+ Goal ⚽",     "⚽", INDIGO4, lambda _: self._quick_action("GOAL","Goal",0.65)),
                action_btn("+ Assist 🅰️",  "🅰️", SKY,    lambda _: self._quick_action("ASSIST","Assist")),
            ], spacing=8),
        ], spacing=8), padding=14)

        # ⑤b Goals Given (opponent scores) + gated defensive Conversion
        defconv_disabled = not self.can_defence_convert
        defconv_hint = ("✓ Save/Block logged — Conversion available"
                        if not defconv_disabled else "Press Save or Block first")
        defconv_col = ROSE if not defconv_disabled else MUTED2
        goals_given_section = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.SPORTS_SOCCER, size=14, color=ROSE),
                    ft.Text("Goals Given (Opponent Scores)", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(content=txt(defconv_hint, size=9, color=defconv_col),
                                 bgcolor=defconv_col+"22", border=ft.Border.all(1, defconv_col+"44"),
                                 border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2))], spacing=8),
            ft.Row([
                action_btn("Goals Given 🥅", "🥅", ROSE, self._log_goals_given),
                action_btn("Conversion (Given) ✅", "✅", ROSE, self._log_defence_conversion, disabled=defconv_disabled),
            ], spacing=8),
        ], spacing=8), padding=14)

        # ⑥ Fouls
        fouls_section = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER, size=14, color=AMBER),
                txt("Fouls", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                action_btn("Fouls Won 🙌",  "🙌", AMBER, lambda _: self._quick_action("FOULS_WON", "Fouls Won")),
                action_btn("Fouls Given ⚠️","⚠️", RED4,  lambda _: self._quick_action("FOULS_GIVEN","Fouls Given")),
            ], spacing=8),
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10))

        # ⑦ Cards
        cards_section = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.STYLE, size=14, color=AMBER3),
                txt("Cards", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                action_btn("Yellow 🟨", "🟨", AMBER, lambda _: self._quick_action("YELLOW_CARD","Yellow Card")),
                action_btn("Red 🟥",    "🟥", ROSE,  lambda _: self._quick_action("RED_CARD","Red Card")),
            ], spacing=8),
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10))

        # ⑧ Time Controllers  req 10
        is_running = self._timer_running
        time_section = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.TIMER, size=14, color=INDIGO4),
                    ft.Text("Time Controllers", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                    txt("(1 minute = 60 seconds)", size=9, color=MUTED2)], spacing=8),
            ft.Row([
                ft.Button(
                    content=ft.Row([ft.Icon(ft.Icons.PAUSE if is_running else ft.Icons.PLAY_ARROW, size=14, color="#fff"),
                                    ft.Text("Pause" if is_running else "Start", size=11, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
                    bgcolor=AMBER if is_running else EMERALD6,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                         padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=self._toggle_timer),
                ft.Button(
                    content=ft.Row([ft.Icon(ft.Icons.SPORTS, size=14, color="#fff"),
                                    ft.Text("Half Time", size=11, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
                    bgcolor=INDIGO6,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                         padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=lambda _: self._mark_halftime()),
                ft.Button(
                    content=ft.Row([ft.Icon(ft.Icons.FLAG, size=14, color="#fff"),
                                    ft.Text("Full Time", size=11, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
                    bgcolor=ROSE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                         padding=ft.Padding.symmetric(horizontal=14, vertical=8)),
                    on_click=lambda _: self._mark_fulltime()),
                ft.Container(width=8),
                ft.IconButton(icon=ft.Icons.REMOVE, icon_size=14, icon_color=MUTED2,
                              on_click=lambda _: self._set_minute(max(0, self.match.minute - 1)),
                              style=ft.ButtonStyle(bgcolor=SURFACE, shape=ft.RoundedRectangleBorder(radius=8),
                                                   side=ft.BorderSide(1, BORDER), padding=ft.Padding.all(4))),
                ft.Container(content=ft.Text(f"{m.minute}'", size=14, color=INDIGO4,
                                              weight=ft.FontWeight.BOLD, font_family="monospace"),
                             bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=8,
                             padding=ft.Padding.symmetric(horizontal=12, vertical=6)),
                ft.IconButton(icon=ft.Icons.ADD, icon_size=14, icon_color=MUTED2,
                              on_click=lambda _: self._set_minute(min(120, self.match.minute + 1)),
                              style=ft.ButtonStyle(bgcolor=SURFACE, shape=ft.RoundedRectangleBorder(radius=8),
                                                   side=ft.BorderSide(1, BORDER), padding=ft.Padding.all(4))),
            ], spacing=8),
            ft.Divider(height=1, color=BORDER),
            self._build_possession_row(m),
        ], spacing=10), padding=14)

        video_section = self._build_live_video_panel()

        return ft.Container(
            content=ft.Column([
                video_section,     # 🎥 live video — same screen as action buttons
                team_row, ft.Divider(height=1, color=BORDER),
                actions_section,   # ①
                inc_section,       # ②
                sub_section,       # ③
                turn_section,      # ④
                conv_section,      # ⑤
                goals_given_section, # ⑤b
                fouls_section,     # ⑥
                cards_section,     # ⑦
                time_section,      # ⑧
            ], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True),
            # ft.Column has no bgcolor of its own — when its content is
            # shorter than the available height, the leftover space below
            # the last card (here: below Time Controllers) sometimes shows
            # Flutter's own default canvas color instead of the app's dark
            # background, since a scrolling Column renders internally as a
            # ListView and doesn't reliably inherit its parent Container's
            # bgcolor into that overflow area. Wrapping it in a Container
            # with an explicit bgcolor pins the background everywhere,
            # including past the end of the content.
            bgcolor=BG, expand=True)

    def _build_camera_mode_screen(self):
        """Minimal standalone screen for a device acting as the camera —
        captures video and streams it over HTTP (MJPEG) to whichever device
        on the same network/cable is running Inputter Mode and has entered
        this device's stream URL as its camera source."""
        local_ip = get_local_ip()
        stream_url = f"http://{local_ip}:{MJPEG_PORT}/video"

        switch_btn = ft.Button(
            content=ft.Row([ft.Icon(ft.Icons.KEYBOARD, size=14, color="#fff"),
                            ft.Text("Switch to Inputter Mode", size=12, color="#fff", weight=ft.FontWeight.BOLD)], spacing=6),
            bgcolor=INDIGO6,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                 padding=ft.Padding.symmetric(horizontal=14, vertical=10)),
            on_click=self._switch_to_inputter_mode)

        stream_btn = (
            ft.Button(
                content=ft.Row([ft.Icon(ft.Icons.WIFI_TETHERING, size=15, color="#fff"),
                                ft.Text("Start Streaming", size=12, color="#fff", weight=ft.FontWeight.BOLD)], spacing=6),
                bgcolor=EMERALD6,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                     padding=ft.Padding.symmetric(horizontal=16, vertical=12)),
                on_click=self._toggle_camera_mode_stream)
            if not self.camera_mode_streaming else
            ft.Button(
                content=ft.Row([ft.Icon(ft.Icons.WIFI_TETHERING_OFF, size=15, color="#fff"),
                                ft.Text("Stop Streaming", size=12, color="#fff", weight=ft.FontWeight.BOLD)], spacing=6),
                bgcolor=ROSE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                     padding=ft.Padding.symmetric(horizontal=16, vertical=12)),
                on_click=self._toggle_camera_mode_stream))

        live_badge = ft.Container(
            content=ft.Row([ft.Container(width=8, height=8, bgcolor="#fff" if self.camera_mode_streaming else MUTED2, border_radius=4),
                            ft.Text("STREAMING" if self.camera_mode_streaming else "NOT STREAMING", size=11,
                                    color="#fff" if self.camera_mode_streaming else MUTED, weight=ft.FontWeight.BOLD)], spacing=6),
            bgcolor=EMERALD+"e6" if self.camera_mode_streaming else SURFACE2+"e6",
            border_radius=18, padding=ft.Padding.symmetric(horizontal=12, vertical=5))

        url_field = ft.TextField(
            value=stream_url, read_only=True, dense=True, text_size=13,
            color=EMERALD, bgcolor=SURFACE2, border_color=BORDER,
            text_style=ft.TextStyle(font_family="monospace", weight=ft.FontWeight.BOLD))

        url_section = (ft.Container(
            content=ft.Column([
                txt("Stream URL — enter this on the Inputter Mode device's camera source field:", size=11, color=MUTED),
                url_field,
            ], spacing=6),
            bgcolor=SURFACE, border=ft.Border.all(1, EMERALD+"44"), border_radius=12,
            padding=14) if self.camera_mode_streaming else ft.Container(
            content=txt("Press Start Streaming to generate a connectable URL.", size=11, color=MUTED2),
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=12, padding=14))

        # ── Pairing panel: shows the current handshake state, and — while a
        # connecting device is waiting — 4 number choices to pick from.
        def _choice_btn(n):
            return ft.Button(
                content=ft.Text(str(n), size=20, color="#fff", weight=ft.FontWeight.W_900),
                bgcolor=INDIGO6,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10),
                                     padding=ft.Padding.symmetric(horizontal=22, vertical=16)),
                on_click=lambda _, num=n: self._pair_select(num))

        if self.pair_status == "pending":
            pairing_panel = ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.SECURITY, size=16, color=AMBER),
                            ft.Text("Pairing Request", size=13, color=TEXT, weight=ft.FontWeight.BOLD)], spacing=6),
                    txt("A device wants to connect. Check the number shown on ITS screen, "
                        "then tap the matching number below.", size=11, color=MUTED),
                    ft.Row([_choice_btn(n) for n in self.pair_choices], spacing=10,
                          alignment=ft.MainAxisAlignment.CENTER, wrap=True),
                ], spacing=10),
                bgcolor=AMBER+"14", border=ft.Border.all(2, AMBER+"66"), border_radius=14, padding=16)
        elif self.pair_status == "approved":
            pairing_panel = ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=15, color=EMERALD),
                                txt("Device paired and connected.", size=11, color=EMERALD, weight=ft.FontWeight.BOLD)], spacing=6),
                bgcolor=EMERALD+"14", border=ft.Border.all(1, EMERALD+"44"), border_radius=10, padding=10)
        elif self.pair_status == "rejected":
            pairing_panel = ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.CANCEL, size=15, color=ROSE),
                                txt("Wrong number selected — connection refused. Ask the other device to try again.",
                                    size=11, color=ROSE, weight=ft.FontWeight.BOLD)], spacing=6),
                bgcolor=ROSE+"14", border=ft.Border.all(1, ROSE+"44"), border_radius=10, padding=10)
        else:
            pairing_panel = ft.Container(
                content=txt("Waiting for a device to connect. When one does, a pairing "
                            "request will appear here for you to confirm.", size=10, color=MUTED2),
                bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=10, padding=10)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.VIDEOCAM, size=20, color=EMERALD),
                    ft.Column([
                        ft.Text("Camera Mode", size=18, color=TEXT, weight=ft.FontWeight.W_900),
                        txt("This device captures & streams video only — no stat logging here.", size=10, color=MUTED),
                    ], spacing=1),
                    ft.Container(expand=True),
                    switch_btn,
                ], spacing=10),
                ft.Divider(height=1, color=BORDER),
                ft.Stack([
                    ft.Container(content=self._video_display_widget(), bgcolor=BG,
                                 border=ft.Border.all(1, BORDER), border_radius=14,
                                 alignment=ft.Alignment.CENTER, height=420),
                    ft.Container(content=live_badge, padding=10),
                ]),
                self.camera_error_text,
                self._build_camera_source_picker(),
                url_section,
                (pairing_panel if self.camera_mode_streaming else ft.Container()),
                ft.Row([stream_btn], alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
            bgcolor=BG, padding=24, expand=True)

    def _switch_to_inputter_mode(self, _=None):
        if self.camera_mode_streaming:
            self._stop_mjpeg_server()
        self._stop_camera()
        self._camera_mode_poll_stop.set()
        self.app_mode = "inputter"
        set_app_mode("inputter")
        if self.is_web: self._save_web()
        self._full_refresh()

    def _switch_to_camera_mode(self, _=None):
        self._stop_camera()
        self.app_mode = "camera"
        set_app_mode("camera")
        if self.is_web: self._save_web()
        self._full_refresh()

    def _build_live_video_panel(self):
        """Live camera feed shown directly on the Logger tab, next to the
        action buttons, so the person logging stats can watch the match
        video and click buttons on the same screen without switching tabs.
        Supports multiple local devices and external/wireless (IP) cameras
        via the source picker below."""
        cam_btn = (
            ft.Button(
                content=ft.Row([ft.Icon(ft.Icons.VIDEOCAM, size=13, color="#fff"),
                                ft.Text("Turn On Camera", size=10, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
                bgcolor=EMERALD6,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                     padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                on_click=self._start_camera)
            if not self.camera_on else
            ft.OutlinedButton(
                content=ft.Row([ft.Icon(ft.Icons.VIDEOCAM_OFF, size=13, color=ROSE),
                                ft.Text("Turn Off Camera", size=10, color=ROSE, weight=ft.FontWeight.BOLD)], spacing=5),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                     side=ft.BorderSide(1, ROSE+"44"),
                                     padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                on_click=self._stop_camera))

        fullscreen_btn = ft.IconButton(
            icon=ft.Icons.FULLSCREEN, icon_size=16, icon_color=INDIGO4,
            tooltip="Fullscreen video logging mode",
            on_click=self._enter_fullscreen_video,
            style=ft.ButtonStyle(bgcolor=SURFACE2, shape=ft.RoundedRectangleBorder(radius=8),
                                 side=ft.BorderSide(1, BORDER), padding=ft.Padding.all(6)))

        live_badge = ft.Container(
            content=ft.Row([ft.Container(width=6, height=6, bgcolor="#fff" if self.camera_on else MUTED2, border_radius=3),
                            ft.Text("LIVE" if self.camera_on else "OFF", size=9,
                                    color="#fff" if self.camera_on else MUTED, weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor=EMERALD+"e6" if self.camera_on else SURFACE+"e6",
            border_radius=16, padding=ft.Padding.symmetric(horizontal=8, vertical=3))

        camera_off_overlay = (
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.VIDEOCAM_OFF, size=32, color=MUTED2),
                    txt("Camera is off", size=11, color=MUTED2, weight=ft.FontWeight.BOLD),
                    txt("Click 'Turn On Camera' to start the live feed", size=9, color=MUTED2),
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=SURFACE2, border_radius=12, alignment=ft.Alignment.CENTER,
                expand=True)
            if not self.camera_on else ft.Container())

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.VIDEOCAM, size=14, color=EMERALD),
                    txt("Live Match Video", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    cam_btn,
                    fullscreen_btn,
                ], spacing=8),
                ft.Stack([
                    ft.Container(content=self._video_display_widget(), bgcolor=BG,
                                 border=ft.Border.all(1, BORDER), border_radius=12,
                                 alignment=ft.Alignment.CENTER, height=220),
                    ft.Container(content=camera_off_overlay, height=220, border_radius=12,
                                 border=ft.Border.all(1, BORDER)),
                    ft.Container(content=live_badge, padding=8),
                ]),
                self.camera_error_text,
                self._build_camera_source_picker(),
            ], spacing=8),
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10))

    def _build_camera_source_picker(self):
        """Pick a camera source. On Android/iOS this offers the native
        front/back on-device camera (via flet-camera) plus the wireless/IP
        URL field; on desktop it offers detected local devices (OpenCV)
        plus the same URL field; on the web build it offers the browser's
        own camera (also via flet-camera, using getUserMedia) plus the
        same URL field. Changing the
        source while the camera is on restarts the capture with the new
        source.

        The first time this is shown each session, it kicks off both
        auto-detection scans in the background (deferred one event-loop
        tick so this doesn't recursively trigger a rebuild mid-build):
        a local-device scan on desktop (mobile doesn't need one — front/
        back are already known without probing), and a wireless
        auto-discovery listen everywhere, so a Camera Mode device already
        broadcasting on the network shows up without the user needing to
        type its URL in or even press a button."""
        if not self._auto_camera_scan_done:
            self._auto_camera_scan_done = True
            if not self.is_mobile and not self.is_web:
                self.page.run_task(self._deferred_auto_detect_cameras)
        if not self._auto_wireless_scan_done:
            self._auto_wireless_scan_done = True
            self.page.run_task(self._deferred_auto_discover_wireless)

        if self.is_web:
            return self._build_web_camera_source_picker()
        if self.is_mobile:
            return self._build_mobile_camera_source_picker()

        def _use_index(i):
            def _click(_):
                self.camera_source = i
                if self.camera_on:
                    self._stop_camera(); self._start_camera()
                else:
                    self._full_refresh()
            return _click

        device_chips = []
        for i in self.detected_cameras:
            active = self.camera_source == i
            device_chips.append(ft.Container(
                content=ft.Text(f"Cam {i}", size=10, color=TEXT if active else MUTED,
                                weight=ft.FontWeight.BOLD),
                bgcolor=INDIGO6+"cc" if active else SURFACE2,
                border=ft.Border.all(1, INDIGO4+"66" if active else BORDER),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                on_click=_use_index(i), ink=True))

        detect_btn = ft.Button(
            content=ft.Row([
                ft.ProgressRing(width=10, height=10, stroke_width=2, color=TEXT) if self.camera_scanning
                else ft.Icon(ft.Icons.SEARCH, size=13, color=TEXT),
                ft.Text("Scanning…" if self.camera_scanning else "Detect Cameras",
                        size=10, color=TEXT, weight=ft.FontWeight.BOLD),
            ], spacing=5),
            bgcolor=SURFACE2 if self.camera_scanning else INDIGO6,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                 padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
            on_click=self._detect_cameras, disabled=self.camera_scanning)

        status_line = (
            txt("Scanning for connected cameras…", size=9, color=SKY) if self.camera_scanning else
            txt(f"{len(self.detected_cameras)} camera(s) found — click 'Detect Cameras' to re-scan.",
                size=9, color=MUTED2) if self.detected_cameras else
            txt(self.camera_error, size=9, color=ROSE) if (self._camera_scan_ran_once and self.camera_error) else
            txt("Scan completed — no cameras found. Click 'Detect Cameras' to try again.",
                size=9, color=AMBER) if self._camera_scan_ran_once else
            txt("No cameras detected yet — click 'Detect Cameras' to scan for connected devices.",
                size=9, color=AMBER))

        return ft.Column([
            ft.Row([txt("Camera source:", size=9, color=MUTED2), *device_chips, detect_btn], spacing=6, wrap=True),
            status_line,
            self._build_url_connect_row(),
            txt(f"Active source: {self.camera_source}", size=9, color=MUTED2, mono=True),
        ], spacing=6)

    def _build_web_camera_source_picker(self):
        """Web build variant: a "This Device's Camera" button (the
        browser's own webcam, via flet-camera's getUserMedia-backed Camera
        control — the same control and "native:" source string the mobile
        picker below uses), plus the same wireless/IP-camera URL field
        used everywhere else. A single button rather than mobile's
        front/back chips, since a laptop/desktop webcam doesn't have a
        meaningful "front vs back" distinction the way a phone does — it
        always requests "native:back", and _start_native_camera_inner
        already falls back to whatever camera the browser actually offers
        if there's no literal "back" match, so this works the same
        whether the visitor has one webcam or several."""
        def _use_builtin(_):
            if not NATIVE_CAMERA_ENABLED:
                return
            self.camera_source = "native:back"
            if self.camera_on:
                self._stop_camera(); self._start_camera()
            else:
                self._start_camera()

        builtin_btn = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.VIDEOCAM_OFF if not NATIVE_CAMERA_ENABLED else ft.Icons.VIDEOCAM,
                                     size=13,
                                     color=MUTED if not NATIVE_CAMERA_ENABLED
                                           else (TEXT if self.camera_source == "native:back" else MUTED)),
                             ft.Text("This Device's Camera (temporarily unavailable)"
                                     if not NATIVE_CAMERA_ENABLED else "This Device's Camera", size=10,
                                     color=MUTED if not NATIVE_CAMERA_ENABLED
                                           else (TEXT if self.camera_source == "native:back" else MUTED),
                                     weight=ft.FontWeight.BOLD)], spacing=5),
            bgcolor=SURFACE2 if (not NATIVE_CAMERA_ENABLED or self.camera_source != "native:back") else INDIGO6 + "cc",
            border=ft.Border.all(1, BORDER if (not NATIVE_CAMERA_ENABLED or self.camera_source != "native:back") else INDIGO4 + "66"),
            border_radius=6, padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            on_click=_use_builtin if NATIVE_CAMERA_ENABLED else None,
            ink=NATIVE_CAMERA_ENABLED, opacity=0.55 if not NATIVE_CAMERA_ENABLED else 1.0)

        status_line = (
            txt("Native camera support isn't installed in this build.", size=9, color=ROSE)
            if not HAS_FLET_CAMERA else
            txt("Temporarily disabled — known bug in the flet-camera plugin itself. "
                "Use a wireless/IP camera URL below instead for now.", size=9, color=AMBER)
            if not NATIVE_CAMERA_ENABLED else
            txt("Uses your browser's own camera permission prompt — allow access when asked.",
                size=9, color=MUTED2))

        return ft.Column([
            ft.Row([txt("Camera source:", size=9, color=MUTED2), builtin_btn], spacing=6, wrap=True),
            status_line,
            txt("Or point a phone running Camera Mode (or any IP-camera app) at a URL below.",
                size=9, color=MUTED2),
            self._build_url_connect_row(),
            txt(f"Active source: {self.camera_source}", size=9, color=MUTED2, mono=True),
        ], spacing=6)

    def _build_mobile_camera_source_picker(self):
        """Android/iOS variant: a front/back toggle for the native on-device
        camera (flet-camera), plus the same wireless/IP-camera URL field
        used on desktop — that path is pure-Python (no OpenCV) so it works
        identically here."""
        def _use_lens(lens):
            def _click(_):
                if not NATIVE_CAMERA_ENABLED:
                    return
                self.mobile_camera_lens = lens
                self.camera_source = f"native:{lens}"
                if self.camera_on:
                    self._stop_camera(); self._start_camera()
                else:
                    self._full_refresh()
            return _click

        def lens_chip(lens, label, icon):
            active = NATIVE_CAMERA_ENABLED and self.mobile_camera_lens == lens
            return ft.Container(
                content=ft.Row([ft.Icon(icon, size=13, color=MUTED if not NATIVE_CAMERA_ENABLED else (TEXT if active else MUTED)),
                                 ft.Text(label, size=10, color=MUTED if not NATIVE_CAMERA_ENABLED else (TEXT if active else MUTED),
                                         weight=ft.FontWeight.BOLD)], spacing=5),
                bgcolor=SURFACE2 if (not NATIVE_CAMERA_ENABLED or not active) else INDIGO6 + "cc",
                border=ft.Border.all(1, BORDER if (not NATIVE_CAMERA_ENABLED or not active) else INDIGO4 + "66"),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                on_click=_use_lens(lens) if NATIVE_CAMERA_ENABLED else None,
                ink=NATIVE_CAMERA_ENABLED, opacity=0.55 if not NATIVE_CAMERA_ENABLED else 1.0)

        status_line = (
            txt("Native camera support isn't installed in this build.", size=9, color=ROSE)
            if not HAS_FLET_CAMERA else
            txt("Temporarily unavailable — known bug in the flet-camera plugin itself "
                "(same on Android and web). Use a wireless/IP camera URL below instead "
                "for now.", size=9, color=AMBER)
            if not NATIVE_CAMERA_ENABLED else
            txt("Using this device's own camera — no separate setup needed.", size=9, color=MUTED2))

        return ft.Column([
            ft.Row([txt("Camera source:", size=9, color=MUTED2),
                    lens_chip("back", "Back Camera", ft.Icons.CAMERA_REAR),
                    lens_chip("front", "Front Camera", ft.Icons.CAMERA_FRONT)], spacing=6, wrap=True),
            status_line,
            self._build_url_connect_row(),
            txt(f"Active source: {self.camera_source}", size=9, color=MUTED2, mono=True),
        ], spacing=6)

    def _build_url_connect_row(self):
        """Wireless/IP-camera URL field + Connect button, plus an
        auto-discovery row above it — shared by the desktop, mobile, and
        web source pickers."""
        def _connect_url(_):
            url = (self.camera_source_url_field.value or "").strip()
            if not url:
                self._snack("Enter an IP camera URL first.", ROSE); return
            if hasattr(self.page, "run_task"):
                try:
                    self.page.run_task(self._pairing_connect_flow_async, url)
                    return
                except Exception as ex:
                    print(f"[Pairing] run_task unavailable, connecting directly: {ex}")
            # No async task support available — connect directly without the
            # pairing handshake (still works, just skips verification).
            self.camera_source = url
            if self.camera_on:
                self._stop_camera(); self._start_camera()
            else:
                self._full_refresh()
            self._snack(f"📡  Camera source set to {url}", EMERALD)

        discover_btn = ft.Button(
            content=ft.Row([
                ft.ProgressRing(width=12, height=12, stroke_width=2, color="#fff")
                if self.wireless_discovering else ft.Icon(ft.Icons.WIFI_FIND, size=14, color="#fff"),
                ft.Text("Scanning…" if self.wireless_discovering else "Auto-Discover Cameras",
                        size=10, color="#fff", weight=ft.FontWeight.BOLD),
            ], spacing=6, tight=True),
            bgcolor=PURPLE4, disabled=self.wireless_discovering,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                 padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
            on_click=self._scan_for_wireless_cameras)

        result_rows = []
        if self.discovered_cameras:
            for cam in self.discovered_cameras:
                result_rows.append(ft.Container(
                    content=ft.Row([ft.Icon(ft.Icons.VIDEOCAM, size=14, color=EMERALD),
                                    ft.Text(cam["name"], size=11, color=TEXT, weight=ft.FontWeight.BOLD),
                                    ft.Container(expand=True),
                                    txt(cam["url"], size=9, color=MUTED2, mono=True)], spacing=8),
                    bgcolor=SURFACE2, border=ft.Border.all(1, EMERALD+"44"), border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    on_click=lambda _, u=cam["url"]: self._connect_discovered_camera(u), ink=True))
        elif self.wireless_discovering:
            result_rows.append(txt("Listening for devices in Camera Mode on this network…", size=9, color=MUTED2))
        else:
            result_rows.append(txt("No devices found yet — tap Auto-Discover while another "
                                   "device has Camera Mode → Start Streaming running.",
                                   size=9, color=MUTED2))

        return ft.Column([
            ft.Row([discover_btn], spacing=6),
            ft.Column(result_rows, spacing=4),
            ft.Row([
                self.camera_source_url_field,
                ft.Button(
                    content=ft.Text("Connect", size=10, color="#fff", weight=ft.FontWeight.BOLD),
                    bgcolor=SKY, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                                      padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
                    on_click=_connect_url),
            ], spacing=6),
        ], spacing=8)

    # ══════════════════════════════════════════════════════════════════════════
    # Fullscreen video logging mode
    # Layout: top = score + time controllers, right = action buttons +
    # team/player selectors, left = incomplete buttons, bottom = cards +
    # undo button + sequences. Video fills the center.
    # ══════════════════════════════════════════════════════════════════════════
    def _build_fullscreen_logger(self, m: Match):
        # Keep the persistent clock ref's value in sync whenever this is
        # rebuilt (e.g. entering fullscreen, manual minute +/-, half-time).
        self.fs_clock_text.value = f"{m.minute}'{getattr(m,'second',0):02d}\""

        # Semi-transparent floating panel background/border colors (used
        # throughout this layout instead of solid SURFACE/BORDER so the
        # video shows through behind every control group).
        GLASS_BG     = "#0f172acc"   # SURFACE at ~80% opacity
        GLASS_BORDER = "#1e293b99"   # BORDER at ~60% opacity

        # ── TOP overlay: exit button, scores, time controllers ──────────────
        exit_btn = ft.IconButton(
            icon=ft.Icons.FULLSCREEN_EXIT, icon_size=16, icon_color=ROSE,
            tooltip="Exit fullscreen (Esc)",
            on_click=self._exit_fullscreen_video,
            style=ft.ButtonStyle(bgcolor=ROSE+"33", shape=ft.RoundedRectangleBorder(radius=8),
                                 side=ft.BorderSide(1, ROSE+"66"), padding=ft.Padding.all(6)))

        is_running = self._timer_running
        cur_poss = m.possession_team
        def _poss_btn(team, color):
            active = cur_poss == team
            return ft.Container(
                content=ft.Text("⚽" if active else "", size=10, color="#fff"),
                bgcolor=color+"cc" if active else SURFACE+"88",
                border=ft.Border.all(1, color+"88"), border_radius=6,
                width=26, height=20, alignment=ft.Alignment.CENTER,
                on_click=lambda _, t=team: self._set_possession(t), ink=True,
                tooltip=f"{'SCC' if team=='home' else m.away_team.short_name} has possession")

        top_bar = ft.Container(
            content=ft.Column([
                ft.Row([
                exit_btn,
                ft.Container(width=10),
                ft.Text(m.home_team.short_name, size=11, color=m.home_team.logo_color, weight=ft.FontWeight.BOLD),
                ft.IconButton(icon=ft.Icons.REMOVE, icon_size=12, icon_color=MUTED2,
                              on_click=lambda _: self._update_score("home", -1),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.Text(str(m.home_score), size=22, color=INDIGO4, weight=ft.FontWeight.W_900, font_family="monospace"),
                ft.IconButton(icon=ft.Icons.ADD, icon_size=12, icon_color=INDIGO4,
                              on_click=lambda _: self._update_score("home", 1),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.Text(":", size=16, color=BORDER2, font_family="monospace"),
                ft.IconButton(icon=ft.Icons.REMOVE, icon_size=12, icon_color=MUTED2,
                              on_click=lambda _: self._update_score("away", -1),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.Text(str(m.away_score), size=22, color=EMERALD, weight=ft.FontWeight.W_900, font_family="monospace"),
                ft.IconButton(icon=ft.Icons.ADD, icon_size=12, icon_color=EMERALD,
                              on_click=lambda _: self._update_score("away", 1),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.Text(m.away_team.short_name, size=11, color=m.away_team.logo_color, weight=ft.FontWeight.BOLD),
                ft.Container(width=16),
                ft.Container(
                    content=ft.Icon(ft.Icons.PAUSE if is_running else ft.Icons.PLAY_ARROW,
                                    size=14, color=AMBER if is_running else TEXT),
                    width=28, height=28, bgcolor=AMBER+"33" if is_running else INDIGO6+"cc",
                    border_radius=8, on_click=self._toggle_timer, ink=True, alignment=ft.Alignment.CENTER),
                self.fs_clock_text,
                ft.IconButton(icon=ft.Icons.REMOVE, icon_size=11, icon_color=MUTED2,
                              on_click=lambda _: self._set_minute(max(0, self.match.minute - 1)),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.IconButton(icon=ft.Icons.ADD, icon_size=11, icon_color=MUTED2,
                              on_click=lambda _: self._set_minute(min(120, self.match.minute + 1)),
                              style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ft.Container(width=16),
                ft.Button(
                    content=ft.Text("Half Time", size=10, color="#fff", weight=ft.FontWeight.BOLD),
                    bgcolor=INDIGO6+"cc", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                                               padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                    on_click=lambda _: self._mark_halftime()),
                ft.Button(
                    content=ft.Text("Full Time", size=10, color="#fff", weight=ft.FontWeight.BOLD),
                    bgcolor=ROSE+"cc", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                                            padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                    on_click=lambda _: self._mark_fulltime()),
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER, wrap=True),
                ft.Row([
                    ft.Icon(ft.Icons.SPORTS_SOCCER, size=11,
                            color=(m.home_team.logo_color if cur_poss=="home" else
                                   m.away_team.logo_color if cur_poss=="away" else MUTED2)),
                    txt(("IN POSSESSION: " + (m.home_team.name if cur_poss=="home" else
                                              m.away_team.name if cur_poss=="away" else "not set")),
                        size=10, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(width=8),
                    _poss_btn("home", m.home_team.logo_color),
                    _poss_btn("away", m.away_team.logo_color),
                    txt(f"{m.stats.home_possession}%/{m.stats.away_possession}%", size=9, color=MUTED2, mono=True),
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            ], spacing=6),
            bgcolor=GLASS_BG, border=ft.Border.all(1, GLASS_BORDER), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8))

        # ── LEFT overlay: incomplete buttons (compact, vertical) ────────────
        last = self.last_logged_action
        INC_DEFS = [
            ("Pass ✗","PASS"), ("Long Pass ✗","LONG_PASS"), ("Cross ✗","CROSS"),
            ("Shot ✗","SHOT"), ("Throw-in ✗","THROW_IN"), ("Tackle ✗","TACKLE"),
            ("Intercept ✗","INTERCEPT"), ("Block ✗","BLOCK"), ("Save ✗","SAVE"),
            ("Clear ✗","CLEAR"), ("Offside ✗","OFFSIDE"), ("Off. Given ✗","OFFSIDE_GIVEN"),
        ]
        def _on_inc(parent):
            def _click(_):
                self.last_logged_action = None
                self.can_convert = False
                self._quick_action(f"{parent}_INCOMPLETE", f"{parent} (Incomplete)")
            return _click
        left_tiles = [action_btn(lbl, ft.Icons.CLOSE, ROSE if (last==p) else MUTED2, _on_inc(p),
                                 disabled=(last != p), width=140)
                     for lbl, p in INC_DEFS]
        left_panel = ft.Container(
            content=ft.Column([
                txt("INCOMPLETES", size=9, color=MUTED2, weight=ft.FontWeight.BOLD),
                ft.Column(left_tiles, spacing=5, scroll=ft.ScrollMode.AUTO, expand=True),
            ], spacing=8, expand=True),
            bgcolor=GLASS_BG, border=ft.Border.all(1, ROSE+"66" if last else GLASS_BORDER),
            border_radius=10, padding=10, width=170, expand=True)

        # ── RIGHT overlay: team/player selectors + action buttons ───────────
        if self.action_category == "Attack":
            action_defs = ATTACK_BUTTONS
        elif self.action_category == "Defence":
            action_defs = DEFENCE_BUTTONS
        else:
            action_defs = [("Yellow Card","YELLOW_CARD","🟨",AMBER), ("Red Card","RED_CARD","🟥",ROSE)]

        def _on_action(etype, label, xg=0.0):
            def _click(_):
                self.last_logged_action = etype if etype in INCOMPLETE_PARENTS else None
                self.can_convert = etype in ATTACK_PARENTS
                if etype in ("SAVE", "BLOCK"):
                    self.can_defence_convert = True
                elif self.action_category == "Defence":
                    self.can_defence_convert = False
                self._quick_action(etype, label, xg)
            return _click

        right_action_tiles = []
        for label, etype, emoji, color in action_defs:
            xg = {"GOAL": 0.65, "SHOT": 0.15}.get(etype, 0.0)
            right_action_tiles.append(action_btn(label, emoji, color, _on_action(etype, label, xg), width=210))

        conv_disabled = not self.can_convert
        defconv_disabled = not self.can_defence_convert
        right_panel = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text(f"SCC — {m.home_team.name}", size=11, color=TEXT, weight=ft.FontWeight.BOLD),
                    bgcolor=m.home_team.logo_color+"cc", border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6)),
                ft.Row([self._cat_tab("Attack", EMERALD), self._cat_tab("Defence", INDIGO4),
                        self._cat_tab("Cards", AMBER)], spacing=4),
                ft.Divider(height=1, color=GLASS_BORDER),
                *right_action_tiles,
                ft.Divider(height=1, color=GLASS_BORDER),
                action_btn("Conversion ✅", "✅", EMERALD, self._log_conversion, disabled=conv_disabled, width=210),
                action_btn("+ Goal ⚽", "⚽", INDIGO4, lambda _: self._quick_action("GOAL","Goal",0.65), width=210),
                action_btn("+ Assist 🅰️", "🅰️", SKY, lambda _: self._quick_action("ASSIST","Assist"), width=210),
                action_btn("Fouls Won 🙌", "🙌", AMBER, lambda _: self._quick_action("FOULS_WON","Fouls Won"), width=210),
                action_btn("Fouls Given ⚠️", "⚠️", RED4, lambda _: self._quick_action("FOULS_GIVEN","Fouls Given"), width=210),
                action_btn("Substitution 🔄", "🔄", SKY, lambda _: self._quick_action("SUBSTITUTION","Substitution"), width=210),
                action_btn("Turnover 🔁", "🔁", ROSE, self._log_turnover, width=210),
                ft.Divider(height=1, color=GLASS_BORDER),
                action_btn("Goals Given 🥅", "🥅", ROSE, self._log_goals_given, width=210),
                action_btn("Conversion (Given) ✅", "✅", ROSE, self._log_defence_conversion, disabled=defconv_disabled, width=210),
            ], spacing=6, scroll=ft.ScrollMode.AUTO, expand=True),
            bgcolor=GLASS_BG, border=ft.Border.all(1, GLASS_BORDER), border_radius=10,
            padding=10, width=230)

        # ── BOTTOM overlay: cards + undo + sequences ─────────────────────
        undo_btn = ft.Button(
            content=ft.Row([ft.Icon(ft.Icons.UNDO, size=14, color="#fff"),
                            ft.Text("Undo Last", size=11, color="#fff", weight=ft.FontWeight.BOLD)], spacing=5),
            bgcolor=MUTED2+"cc",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                 padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
            on_click=lambda _: self._undo_last_event())

        seq_home = generate_sequences(m.events, "home")
        seq_text = ft.Column([
            txt(f"ATTACK:  {seq_home['attack'] or '—'}", size=10, color=MUTED2, mono=True),
            txt(f"DEFENCE: {seq_home['defence'] or '—'}", size=10, color=MUTED2, mono=True),
            txt(f"CARDS:   {seq_home['cards'] or '—'}", size=10, color=MUTED2, mono=True),
        ], spacing=3)

        bottom_bar = ft.Container(
            content=ft.Column([
                ft.Row([
                    txt("CARDS", size=9, color=MUTED2, weight=ft.FontWeight.BOLD),
                    action_btn("Yellow 🟨", "🟨", AMBER, lambda _: self._quick_action("YELLOW_CARD","Yellow Card")),
                    action_btn("Red 🟥", "🟥", ROSE, lambda _: self._quick_action("RED_CARD","Red Card")),
                    ft.Container(width=16),
                    undo_btn,
                ], spacing=8),
                ft.Divider(height=1, color=GLASS_BORDER),
                seq_text,
            ], spacing=6),
            bgcolor=GLASS_BG, border=ft.Border.all(1, GLASS_BORDER), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8))

        # ── Video (center) ───────────────────────────────────────────────
        live_badge = ft.Container(
            content=ft.Row([ft.Container(width=6, height=6, bgcolor="#fff" if self.camera_on else MUTED2, border_radius=3),
                            ft.Text("LIVE" if self.camera_on else "OFF", size=9,
                                    color="#fff" if self.camera_on else MUTED, weight=ft.FontWeight.BOLD)], spacing=4),
            bgcolor=EMERALD+"e6" if self.camera_on else SURFACE+"e6",
            border_radius=16, padding=ft.Padding.symmetric(horizontal=8, vertical=3))
        cam_toggle_btn = (
            ft.IconButton(icon=ft.Icons.VIDEOCAM, icon_size=16, icon_color=EMERALD,
                         tooltip="Turn on camera", on_click=self._start_camera,
                         style=ft.ButtonStyle(bgcolor=SURFACE+"cc", shape=ft.RoundedRectangleBorder(radius=8)))
            if not self.camera_on else
            ft.IconButton(icon=ft.Icons.VIDEOCAM_OFF, icon_size=16, icon_color=ROSE,
                         tooltip="Turn off camera", on_click=self._stop_camera,
                         style=ft.ButtonStyle(bgcolor=SURFACE+"cc", shape=ft.RoundedRectangleBorder(radius=8))))
        video_area = ft.Container(
            content=ft.Stack([
                ft.Container(content=self._video_display_widget(), bgcolor=BG, expand=True,
                             border=ft.Border.all(1, GLASS_BORDER), border_radius=12,
                             alignment=ft.Alignment.CENTER),
                ft.Container(content=live_badge, padding=8),
                ft.Container(content=cam_toggle_btn, padding=8, alignment=ft.Alignment.TOP_RIGHT),
            ], expand=True),
            expand=True)

        # ── Assemble: left | (top / video / bottom) | right — a normal flex
        # layout, so panels sit beside and around the video and can never
        # overlap each other, unlike the previous Stack-based approach.
        # Panel backgrounds stay semi-transparent for a "floating" look.
        #
        # The 5 pieces built above (left_panel, top_bar, video_area,
        # bottom_bar, right_panel) get assigned into the 5 persistent slot
        # containers' .content here, rather than this function returning a
        # brand new top-level tree each call — see where self._fs_skeleton
        # is initialized (in __init__) for why that distinction is what
        # actually stops the fullscreen view (camera included) from
        # visibly "reloading" on every single stat button press.
        self.fs_left_slot.content = left_panel
        self.fs_top_slot.content = top_bar
        self.fs_video_slot.content = video_area
        self.fs_bottom_slot.content = bottom_bar
        self.fs_right_slot.content = right_panel

        if self._fs_skeleton is None:
            self._fs_skeleton = ft.Container(
                content=ft.Row([
                    ft.Container(content=self.fs_left_slot, expand=False),
                    ft.Container(
                        content=ft.Column([self.fs_top_slot, self.fs_video_slot, self.fs_bottom_slot],
                                          spacing=8, expand=True),
                        expand=True),
                    ft.Container(content=self.fs_right_slot, expand=False),
                ], spacing=8, expand=True),
                bgcolor=BG, padding=8, expand=True)
        return self._fs_skeleton

    def _enter_fullscreen_video(self, _=None):
        self.fullscreen_video = True
        try:
            self.page.window.full_screen = True
            self.page.window.update()
        except Exception as ex:
            print(f"[Fullscreen] Could not enter OS fullscreen: {ex}")
        self._full_refresh()

    def _exit_fullscreen_video(self, _=None):
        self.fullscreen_video = False
        try:
            self.page.window.full_screen = False
            self.page.window.update()
        except Exception as ex:
            print(f"[Fullscreen] Could not exit OS fullscreen: {ex}")
        self._full_refresh()

    def _undo_last_event(self):
        m = self.match
        if not m or not m.events:
            self._snack("Nothing to undo.", MUTED2); return
        removed = m.events.pop()
        recalculate_stats(m)
        self._save()
        self._full_refresh()
        self._snack(f"↩️  Undid: {removed.event_type.replace('_',' ').title()} — {removed.player_name}", AMBER)

    def _cat_tab(self, category, color):
        active = self.action_category == category
        def _click(_):
            self.action_category = category
            self._full_refresh()
        return ft.Container(
            content=ft.Text(category, size=10, color=color if active else MUTED2,
                            weight=ft.FontWeight.BOLD),
            bgcolor=color+"22" if active else "transparent",
            border=ft.Border.all(1, color+"44" if active else BORDER),
            border_radius=8, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            on_click=_click, ink=True)

    def _quick_row(self, label, emoji, color, on_click):
        icon_map = {"🔄": ft.Icons.SWAP_HORIZ, "🔁": ft.Icons.SYNC_ALT}
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon_map.get(emoji, ft.Icons.CIRCLE), size=14, color=color),
                txt(label, size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                action_btn(label, emoji, color, on_click),
            ], spacing=10),
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10))

    def _build_category_grid(self, m: Match):
        """req 22: render the correct button set for Attack / Defence / Cards."""
        if self.action_category == "Attack":
            buttons = ATTACK_BUTTONS
        elif self.action_category == "Defence":
            buttons = DEFENCE_BUTTONS
        else:
            buttons = [("Yellow Card","YELLOW_CARD","🟨",AMBER), ("Red Card","RED_CARD","🟥",ROSE)]

        def _on(etype, label, xg=0.0):
            def _click(_):
                self.last_logged_action = etype if etype in INCOMPLETE_PARENTS else None
                self.can_convert = etype in ATTACK_PARENTS   # req 23
                if etype in ("SAVE", "BLOCK"):
                    self.can_defence_convert = True
                elif self.action_category == "Defence":
                    self.can_defence_convert = False
                self._quick_action(etype, label, xg)
            return _click

        tiles = []
        for label, etype, emoji, color in buttons:
            xg = {"GOAL":0.65,"SHOT":0.15,"CONVERSION":0.5}.get(etype, 0.0)
            tiles.append(action_btn(label, emoji, color, _on(etype, label, xg)))

        h = max(56, (len(tiles) // 4 + 1) * 56)
        return ft.GridView(controls=tiles, runs_count=4, max_extent=200,
                           child_aspect_ratio=2.5, spacing=6, run_spacing=6, height=h)

    def _build_incompletes_row(self):
        """req 21: only the button matching last_logged_action is enabled."""
        last = self.last_logged_action
        DEFS = [
            ("Pass ✗",       "PASS"),
            ("Long Pass ✗",  "LONG_PASS"),
            ("Cross ✗",      "CROSS"),
            ("Shot ✗",       "SHOT"),
            ("Throw-in ✗",   "THROW_IN"),
            ("Tackle ✗",     "TACKLE"),
            ("Intercept ✗",  "INTERCEPT"),
            ("Block ✗",      "BLOCK"),
            ("Save ✗",       "SAVE"),
            ("Clear ✗",      "CLEAR"),
            ("Offside ✗",    "OFFSIDE"),
            ("Offside Gvn ✗","OFFSIDE_GIVEN"),
        ]
        def _on_inc(parent):
            def _click(_):
                self.last_logged_action = None
                self.can_convert = False
                self._quick_action(f"{parent}_INCOMPLETE", f"{parent} (Incomplete)")
            return _click

        tiles = [action_btn(lbl, ft.Icons.CLOSE, ROSE if (last==p) else MUTED2,
                            _on_inc(p), disabled=(last != p))
                 for lbl, p in DEFS]

        status = (f"✓ Mark {last.replace('_',' ').title()} as incomplete" if last
                  else "Incompletes — press an action button first")
        s_color = ROSE if last else MUTED2

        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(ft.Icons.CANCEL_OUTLINED, size=14, color=s_color),
                        txt("Incompletes", size=12, color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Container(content=txt(status, size=9, color=s_color),
                                     bgcolor=s_color+"22", border=ft.Border.all(1, s_color+"44"),
                                     border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=2))], spacing=8),
                ft.GridView(controls=tiles, runs_count=6, max_extent=150,
                            child_aspect_ratio=2.5, spacing=5, run_spacing=5, height=92),
            ], spacing=8),
            bgcolor=SURFACE, border=ft.Border.all(1, ROSE+"44" if last else BORDER),
            border_radius=10, padding=ft.Padding.symmetric(horizontal=14, vertical=12))

    def _log_conversion(self, _=None):
        """req 23: Conversion = goals+1, assists+1, conversions+1. Team stats only — SCC."""
        m = self.match
        if not self.can_convert:
            return
        self.can_convert = False
        self.last_logged_action = None
        ev = make_event(m, "home", "CONVERSION", m.home_team.short_name,
                        f"Conversion [{m.minute}']", xg=0.5)
        m.events.append(ev)
        recalculate_stats(m)
        # Conversion counts as a goal — opponent kicks off, possession switches.
        self._set_possession("away", silent=True)
        self._save()
        self._full_refresh()
        self._snack(f"✅  Conversion ({m.minute}') → Goals+1 Assists+1 Conversions+1")

    def _log_goals_given(self, _=None):
        """The opponent scores directly against SCC. Manual, like the
        scoreboard +/- — there's no 'away team' event stream to derive this
        from. Logged under team_id 'home' (not 'away') so it shows up in
        SCC's own defence sequence — this app only ever tracks and exports
        SCC's perspective, and conceding a goal is fundamentally a
        defensive stat for SCC. Hands SCC the kickoff/possession afterward."""
        m = self.match
        if not m: return
        ev = make_event(m, "home", "GOALS_GIVEN", m.away_team.short_name, f"Goals Given [{m.minute}']")
        m.events.append(ev)
        m.away_score = max(0, m.away_score + 1)
        self._set_possession("home", silent=True)
        self._save()
        self._full_refresh()
        self._snack(f"🥅  Goals Given ({m.minute}') — {m.away_team.short_name} {m.away_score}", ROSE)

    def _log_defence_conversion(self, _=None):
        """Gated conversion for the defensive side: a Save or Block that
        still results in the opponent scoring (rebound, follow-up shot,
        etc). Only clickable immediately after Save/Block is pressed —
        mirrors the attack Conversion button's gating logic. Logged under
        team_id 'home' for the same reason as Goals Given above."""
        m = self.match
        if not self.can_defence_convert or not m:
            return
        self.can_defence_convert = False
        ev = make_event(m, "home", "GOALS_GIVEN_CONVERSION", m.away_team.short_name,
                        f"Conversion — Goals Given [{m.minute}']")
        m.events.append(ev)
        m.away_score = max(0, m.away_score + 1)
        self._set_possession("home", silent=True)
        self._save()
        self._full_refresh()
        self._snack(f"🥅  Defensive Conversion ({m.minute}') — {m.away_team.short_name} {m.away_score}", ROSE)

    # ══════════════════════════════════════════════════════════════════════════
    # Tab — Timeline
    # ══════════════════════════════════════════════════════════════════════════
    def _build_timeline_tab(self, m: Match):
        events = sorted(m.events, key=lambda e: (e.minute, getattr(e, "second", 0)), reverse=True)
        if not events:
            return card(ft.Column([ft.Icon(ft.Icons.FORMAT_LIST_BULLETED,size=40,color=BORDER),
                                   ft.Text("No events logged yet.",size=13,color=MUTED)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=10),padding=50)

        def ev_row(ev: StatEvent):
            is_home = ev.team_id == "home"
            team = m.home_team if is_home else m.away_team
            # Incomplete events get a bundled vector icon (guaranteed to
            # render) instead of the "❌" text emoji every other event
            # type uses — same "missing glyph renders as a bare '!'" issue
            # fixed for the Mark Incomplete buttons above.
            if ev.event_type.endswith("_INCOMPLETE"):
                icon_widget = ft.Icon(ft.Icons.CLOSE, size=18, color=ROSE)
            else:
                icon_widget = ft.Text(EVENT_EMOJI.get(ev.event_type, "•"), size=18)
            xg_badge = (ft.Container(content=ft.Text(f"xG {ev.xg:.2f}",size=9,color=AMBER,font_family="monospace"),
                                     bgcolor=AMBER+"22",border=ft.Border.all(1,AMBER+"55"),border_radius=4,
                                     padding=ft.Padding.symmetric(horizontal=5,vertical=1))
                        if ev.xg > 0 else ft.Container())
            return ft.Container(
                content=ft.Row([
                    ft.Container(content=ft.Text(f"{ev.minute}'{getattr(ev,'second',0):02d}\"",size=11,color=team.logo_color,
                                                  weight=ft.FontWeight.BOLD,font_family="monospace"),
                                 width=52,alignment=ft.Alignment.CENTER),
                    icon_widget,
                    ft.Column([
                        ft.Row([ft.Text(ev.event_type.replace("_"," ").title(),size=12,color=TEXT,weight=ft.FontWeight.BOLD),xg_badge],spacing=5),
                        ft.Row([
                            ft.Container(content=ft.Text(team.short_name,size=9,color=team.logo_color),
                                         bgcolor=team.logo_color+"22",border=ft.Border.all(1,team.logo_color+"44"),
                                         border_radius=4,padding=ft.Padding.symmetric(horizontal=5,vertical=1)),
                            txt(ev.description[:65]+"…" if len(ev.description)>65 else ev.description,size=10),
                        ],spacing=5),
                    ],spacing=3,expand=True),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE,icon_size=14,icon_color=ROSE+"aa",
                                  on_click=lambda _,eid=ev.id: self._delete_event(eid),
                                  style=ft.ButtonStyle(padding=ft.Padding.all(2))),
                ],spacing=8,vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=SURFACE,border=ft.Border.all(1,BORDER),border_radius=10,
                padding=ft.Padding.symmetric(horizontal=12,vertical=8))

        return ft.Column([
            ft.Row([ft.Icon(ft.Icons.FORMAT_LIST_BULLETED,color=EMERALD,size=14),
                    ft.Text("Match Event Log",size=13,color=TEXT,weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    txt(f"{len(events)} events",size=10,color=INDIGO4)],spacing=8),
            ft.Divider(height=1,color=BORDER),
            *[ev_row(ev) for ev in events],
        ],spacing=6,scroll=ft.ScrollMode.AUTO,expand=True)

    def _build_stats_tab(self, m: Match):
        s = m.stats
        ht = m.home_team; at = m.away_team
        radar_widget = self._build_radar_chart_canvas(m)

        def bar(lbl, hv, av, hr, ar):
            return dual_stat_bar(lbl, hv, av, hr, ar, ht.logo_color, at.logo_color)

        stat_rows = [
            bar("Possession",f"{s.home_possession}%",f"{s.away_possession}%",s.home_possession,s.away_possession),
            bar("Expected Goals (xG)",f"{s.home_xg:.2f}",f"{s.away_xg:.2f}",s.home_xg,s.away_xg),
            bar("Goals",str(s.home_goals),str(s.away_goals),s.home_goals,s.away_goals),
            bar("Assists / Conv.",f"{s.home_assists}/{s.home_conversions}",f"{s.away_assists}/{s.away_conversions}",
                s.home_assists+s.home_conversions,s.away_assists+s.away_conversions),
            bar("Shots",f"{s.home_shots}(+{s.home_incomplete_shots})",f"{s.away_shots}(+{s.away_incomplete_shots})",
                s.home_shots+s.home_incomplete_shots,s.away_shots+s.away_incomplete_shots),
            bar("Shots on Target",str(s.home_shots_on_target),str(s.away_shots_on_target),
                s.home_shots_on_target,s.away_shots_on_target),
            bar("Passes",f"{s.home_completed_passes}({s.home_incomplete_passes} inc)",
                f"{s.away_completed_passes}({s.away_incomplete_passes} inc)",
                s.home_completed_passes,s.away_completed_passes),
            bar("Pass Accuracy",f"{s.home_pass_acc}%",f"{s.away_pass_acc}%",s.home_pass_acc,s.away_pass_acc),
            bar("Crosses",f"{s.home_completed_crosses}({s.home_incomplete_crosses} inc)",
                f"{s.away_completed_crosses}({s.away_incomplete_crosses} inc)",
                s.home_completed_crosses,s.away_completed_crosses),
            bar("Tackles",f"{s.home_tackles}({s.home_incomplete_tackles} inc)",
                f"{s.away_tackles}({s.away_incomplete_tackles} inc)",
                s.home_tackles,s.away_tackles),
            bar("Saves",str(s.home_saves),str(s.away_saves),s.home_saves,s.away_saves),
            bar("Corners",str(s.home_corners),str(s.away_corners),s.home_corners,s.away_corners),
            bar("Fouls",str(s.home_fouls),str(s.away_fouls),s.home_fouls,s.away_fouls),
            bar("Yellow Cards",str(s.home_yellow_cards),str(s.away_yellow_cards),
                s.home_yellow_cards,s.away_yellow_cards),
            bar("Red Cards",str(s.home_red_cards),str(s.away_red_cards),s.home_red_cards,s.away_red_cards),
        ]
        for name, etype, has_inc in GENERIC_TALLY_ACTIONS:
            hc,hi,ac,ai = tally_action(m.events, etype)
            stat_rows.append(bar(name,
                f"{hc}({hi} inc)" if has_inc else str(hc),
                f"{ac}({ai} inc)" if has_inc else str(ac), hc, ac))

        header = ft.Row([
            ft.Row([kit_dot(ht.logo_color),ft.Text(ht.short_name,size=13,color=TEXT,weight=ft.FontWeight.BOLD)],spacing=6),
            ft.Text("LIVE STAT COMPARISON",size=10,color=MUTED,font_family="monospace",expand=True,text_align=ft.TextAlign.CENTER),
            ft.Row([ft.Text(at.short_name,size=13,color=TEXT,weight=ft.FontWeight.BOLD),kit_dot(at.logo_color)],spacing=6),
        ],alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        return ft.Column([
            # Radar chart (req 12) — top of Stats tab
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.RADAR,size=14,color=INDIGO4),
                            ft.Text("Radar Comparison",size=13,color=TEXT,weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            pill("Shots · Possession · Tackles · Passes",INDIGO,size=8)],spacing=8),
                    ft.Divider(height=1,color=BORDER),
                    ft.Row([
                        radar_widget,
                        ft.Column([
                            ft.Container(content=ft.Row([ft.Container(width=12,height=12,bgcolor=ht.logo_color,border_radius=3),
                                                          txt(ht.short_name,size=11,color=TEXT)],spacing=6),
                                         bgcolor=SURFACE,border=ft.Border.all(1,BORDER),border_radius=6,
                                         padding=ft.Padding.symmetric(horizontal=8,vertical=4)),
                            ft.Container(content=ft.Row([ft.Container(width=12,height=12,bgcolor=at.logo_color,border_radius=3),
                                                          txt(at.short_name,size=11,color=TEXT)],spacing=6),
                                         bgcolor=SURFACE,border=ft.Border.all(1,BORDER),border_radius=6,
                                         padding=ft.Padding.symmetric(horizontal=8,vertical=4)),
                            ft.Container(height=6),
                            txt("Axes: Shots · Possession% · Tackles · Passes · Saves · Goals",size=9,color=MUTED2),
                        ],spacing=6),
                    ],spacing=12,vertical_alignment=ft.CrossAxisAlignment.START),
                ],spacing=10),
                bgcolor=SURFACE,border=ft.Border.all(1,BORDER),border_radius=16,padding=16),
            ft.Container(height=8),
            card(ft.Column([header,ft.Divider(height=1,color=BORDER),*stat_rows],spacing=10),padding=16),
        ],spacing=0,scroll=ft.ScrollMode.AUTO,expand=True)

    def _build_radar_chart_canvas(self, m: Match):
        """Native vector radar chart drawn with flet.canvas — no image
        rendering/encoding involved at all, so this needs neither
        matplotlib nor numpy (both removed from requirements.txt). Cuts a
        large chunk of dead weight out of every build, especially the
        Android APK, for a chart that's otherwise just six numbers on a
        hexagon."""
        import math
        s = m.stats
        categories = ["Shots", "Poss.%", "Tackles", "Passes", "Saves", "Goals"]
        home_vals = [s.home_shots, s.home_possession, s.home_tackles,
                     s.home_completed_passes, s.home_saves, s.home_goals]
        away_vals = [s.away_shots, s.away_possession, s.away_tackles,
                     s.away_completed_passes, s.away_saves, s.away_goals]
        n = len(categories)
        max_v = max(home_vals + away_vals + [1])

        width, height = 340, 280
        cx, cy = width / 2, height / 2 - 6
        radius = 92
        # Start at the top (-90°) and go clockwise, matching a conventional
        # radar/spider chart layout.
        angles = [(-math.pi / 2) + i * (2 * math.pi / n) for i in range(n)]

        def point(angle, frac):
            return (cx + math.cos(angle) * radius * frac,
                    cy + math.sin(angle) * radius * frac)

        shapes = []
        # Grid rings at 25/50/75/100%.
        for frac in (0.25, 0.5, 0.75, 1.0):
            elements = []
            for i, ang in enumerate(angles):
                x, y = point(ang, frac)
                elements.append(cv.Path.MoveTo(x, y) if i == 0 else cv.Path.LineTo(x, y))
            elements.append(cv.Path.Close())
            shapes.append(cv.Path(elements, paint=ft.Paint(
                style=ft.PaintingStyle.STROKE, stroke_width=1, color=BORDER)))
        # Spokes + axis labels.
        for i, ang in enumerate(angles):
            x, y = point(ang, 1.0)
            shapes.append(cv.Line(cx, cy, x, y, paint=ft.Paint(
                style=ft.PaintingStyle.STROKE, stroke_width=1, color=BORDER)))
            lx, ly = point(ang, 1.17)
            shapes.append(cv.Text(lx, ly, categories[i],
                                   style=ft.TextStyle(size=9, color=MUTED, weight=ft.FontWeight.W_600),
                                   alignment=ft.Alignment.CENTER))

        def polygon_shapes(values, color):
            fracs = [v / max_v for v in values]
            elements = []
            for i, (ang, frac) in enumerate(zip(angles, fracs)):
                x, y = point(ang, frac)
                elements.append(cv.Path.MoveTo(x, y) if i == 0 else cv.Path.LineTo(x, y))
            elements.append(cv.Path.Close())
            fill = cv.Path(elements, paint=ft.Paint(
                style=ft.PaintingStyle.FILL, color=ft.Colors.with_opacity(0.22, color)))
            stroke = cv.Path(elements, paint=ft.Paint(
                style=ft.PaintingStyle.STROKE, stroke_width=2, color=color))
            dots = [cv.Circle(*point(ang, frac), radius=2.6,
                               paint=ft.Paint(style=ft.PaintingStyle.FILL, color=color))
                    for ang, frac in zip(angles, fracs)]
            return [fill, stroke, *dots]

        shapes += polygon_shapes(home_vals, m.home_team.logo_color)
        shapes += polygon_shapes(away_vals, m.away_team.logo_color)

        return ft.Container(
            content=cv.Canvas(shapes=shapes, width=width, height=height),
            width=width, height=height)



    # ══════════════════════════════════════════════════════════════════════════
    # Core event handlers
    # ══════════════════════════════════════════════════════════════════════════
    def _quick_action(self, etype: str, label: str, xg: float = 0.0):
        m = self.match
        if not m: return
        ev = make_event(m, "home", etype, m.home_team.short_name, f"{label} [{m.minute}']", xg)
        m.events.append(ev)
        recalculate_stats(m)
        if etype == "GOAL":
            # After SCC scores, the opponent kicks off — possession switches.
            self._set_possession("away", silent=True)
        self._save()
        self._full_refresh()
        self._snack(f"✅  {label} ({m.minute}')")

    def _delete_event(self, eid: str):
        m = self.match
        m.events = [e for e in m.events if e.id != eid]
        recalculate_stats(m)
        self._save()
        self._full_refresh()

    def _update_score(self, team: str, delta: int):
        m = self.match
        if team == "home": m.home_score = max(0, m.home_score + delta)
        else:              m.away_score = max(0, m.away_score + delta)
        if team == "away" and delta > 0:
            # Opponent scored (manual score adjustment) — SCC kicks off after conceding.
            self._set_possession("home", silent=True)
        self._save(); self._full_refresh()

    # ── Possession tracking ─────────────────────────────────────────────────
    def _set_possession(self, team: Optional[str], silent: bool = False):
        """Switch which team currently has the ball. Accumulated seconds are
        tallied per-tick in _run_timer while the match clock is running."""
        m = self.match
        if not m: return
        m.possession_team = team
        self._save()
        if not silent:
            self._full_refresh()

    def _recompute_possession_pct(self, m: Match):
        hs = m.stats.home_possession_seconds
        as_ = m.stats.away_possession_seconds
        total = hs + as_
        if total > 0:
            m.stats.home_possession = round(hs / total * 100)
            m.stats.away_possession = 100 - m.stats.home_possession

    def _log_turnover(self, _=None):
        """Turnover = ball changes hands. Logs the event AND automatically
        flips possession to whichever team doesn't currently have it."""
        m = self.match
        if not m: return
        ev = make_event(m, "home", "TURNOVER", m.home_team.short_name, f"Turnover [{m.minute}']")
        m.events.append(ev)
        recalculate_stats(m)
        # Flip possession: home<->away. If nothing was set yet, assume SCC
        # had it (since only SCC actions are logged) and it's now lost.
        new_team = "away" if m.possession_team != "away" else "home"
        self._set_possession(new_team, silent=True)
        self._save()
        self._full_refresh()
        self._snack(f"🔁  Turnover ({m.minute}') — possession → "
                    f"{m.home_team.short_name if new_team=='home' else m.away_team.short_name}")

    def _build_possession_row(self, m: Match):
        """Toggle which team currently has the ball. Seconds accumulate
        while the match clock is running; percentages are computed live."""
        current = m.possession_team

        def _btn(team, label, color):
            active = current == team
            def _click(_):
                self._set_possession(team)
            return ft.Container(
                content=ft.Text(label, size=11, color=TEXT if active else MUTED, weight=ft.FontWeight.BOLD),
                bgcolor=color if active else SURFACE,
                border=ft.Border.all(1, color+"88"), border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                on_click=_click, ink=True)

        # Prominent "currently in possession" indicator — shows the team
        # name and swaps automatically on Turnover / goals.
        if current == "home":
            poss_name, poss_color = m.home_team.name, m.home_team.logo_color
        elif current == "away":
            poss_name, poss_color = m.away_team.name, m.away_team.logo_color
        else:
            poss_name, poss_color = None, MUTED2

        indicator = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SPORTS_SOCCER, size=13, color="#fff"),
                ft.Text(f"IN POSSESSION: {poss_name}" if poss_name else "POSSESSION NOT SET",
                        size=11, color="#fff", weight=ft.FontWeight.BOLD),
            ], spacing=6),
            bgcolor=poss_color, border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=7))

        return ft.Column([
            ft.Row([indicator], spacing=8),
            ft.Row([
                txt("Set possession:", size=10, color=MUTED2),
                _btn("home", f"{m.home_team.short_name}", m.home_team.logo_color),
                _btn("away", f"{m.away_team.short_name}", m.away_team.logo_color),
                ft.Container(expand=True),
                txt(f"{m.stats.home_possession}% / {m.stats.away_possession}%", size=11, color=MUTED, mono=True),
            ], spacing=8, wrap=True),
        ], spacing=6)

    def _set_minute(self, new_min: int):
        self.match.minute = new_min
        self._save(); self._full_refresh()

    def _mark_halftime(self):
        m = self.match; m.period = "HALF_TIME"; m.is_live = False
        with self._timer_lock: self._timer_running = False
        self._save(); self._full_refresh(); self._snack("⏸  Half Time!", AMBER)

    def _mark_fulltime(self):
        m = self.match; m.period = "FULL_TIME"; m.is_live = False
        with self._timer_lock: self._timer_running = False
        self._save(); self._full_refresh()
        self._snack("🏁  Full Time!", EMERALD)

    def _toggle_period(self):
        advance_period(self.match); self._save(); self._full_refresh()

    # ── Timer (req 10: 1 game-minute = 60 real seconds) ───────────────────────
    def _toggle_timer(self, _=None):
        m = self.match
        if not m: return
        with self._timer_lock:
            currently_running = self._timer_running

        if not currently_running:
            # About to START the clock. If this is the very beginning of a
            # half (kickoff), ask who has first possession before starting.
            is_fresh_first_half = (m.period == "1ST_HALF" and m.minute == 0
                                   and m.second == 0 and m.possession_team is None)
            is_half_time_start  = (m.period == "HALF_TIME")
            if is_fresh_first_half or is_half_time_start:
                self._open_kickoff_dialog(starting_second_half=is_half_time_start)
                return

        with self._timer_lock:
            self._timer_running = not self._timer_running
            if self._timer_running:
                self.match.is_live = True
                self._launch_timer_thread()
            else:
                if self.match: self.match.is_live = False
        self._full_refresh()

    def _open_kickoff_dialog(self, starting_second_half: bool = False):
        """Choose which team has first possession at the start of a half,
        then start the match clock."""
        m = self.match
        if not m: return

        def _pick(team):
            def _click(_):
                m.possession_team = team
                if starting_second_half:
                    m.period = "2ND_HALF"
                    m.is_live = True
                try: self.page.pop_dialog()
                except Exception: pass
                with self._timer_lock:
                    self._timer_running = True
                self.match.is_live = True
                self._launch_timer_thread()
                self._save()
                self._full_refresh()
            return _click

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.SPORTS_SOCCER, color=INDIGO4),
                          ft.Text(f"Kickoff — {'2nd Half' if starting_second_half else '1st Half'}",
                                  color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=360, content=ft.Column([
                txt("Which team has first possession?", size=11, color=MUTED),
                ft.Container(height=8),
                ft.Row([
                    ft.Button(
                        content=ft.Text(m.home_team.short_name, size=13, color="#fff", weight=ft.FontWeight.BOLD),
                        bgcolor=m.home_team.logo_color,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                             padding=ft.Padding.symmetric(horizontal=20, vertical=14)),
                        on_click=_pick("home"), expand=True),
                    ft.Button(
                        content=ft.Text(m.away_team.short_name, size=13, color="#fff", weight=ft.FontWeight.BOLD),
                        bgcolor=m.away_team.logo_color,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8),
                                             padding=ft.Padding.symmetric(horizontal=20, vertical=14)),
                        on_click=_pick("away"), expand=True),
                ], spacing=10),
            ], spacing=6, tight=True)),
            actions=[ft.TextButton("Skip (decide later)", style=ft.ButtonStyle(color=MUTED),
                                   on_click=lambda _: _pick(None)(_))],
            actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    def _launch_timer_thread(self):
        """Launch the timer tick loop using the same 3-tier strategy that
        fixed the frozen video: plain threading.Thread calling .update() on
        a control was unreliable in this Flet version — that's exactly why
        the clock looked frozen in fullscreen mode until something else
        forced a full page rebuild. Try page.run_task (async, runs on
        Flet's own event loop) first, then page.run_thread, then fall back
        to a raw thread as a last resort."""
        started_via = None
        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(self._run_timer_async)
                started_via = "page.run_task (async)"
            except Exception as ex:
                print(f"[Timer] page.run_task failed: {type(ex).__name__}: {ex}")
        if not started_via and hasattr(self.page, "run_thread"):
            try:
                self.page.run_thread(self._run_timer)
                started_via = "page.run_thread (sync)"
            except Exception as ex:
                print(f"[Timer] page.run_thread failed: {type(ex).__name__}: {ex}")
        if not started_via:
            threading.Thread(target=self._run_timer, daemon=True).start()
            started_via = "raw threading.Thread (fallback)"
        print(f"[Timer] Started via: {started_via}")

    async def _run_timer_async(self):
        """Async twin of _run_timer — identical tick logic, scheduled on
        Flet's own event loop via page.run_task so control updates land
        reliably instead of crossing threads."""
        import asyncio
        while True:
            await asyncio.sleep(1)
            with self._timer_lock:
                if not self._timer_running: break
            m = self.match
            if not m: break
            self._tick_match_clock(m)
            with self._timer_lock:
                if not self._timer_running: break

    def _tick_match_clock(self, m: Match):
        """One second of match-clock bookkeeping: advance the clock,
        accumulate possession seconds, and push the display update. Shared
        by both the sync and async timer loops so the logic only lives in
        one place."""
        m.second = getattr(m, "second", 0) + 1
        if m.second >= 60:      # req 10
            m.second = 0
            m.minute = min(120, m.minute + 1)
            self._save()
        # Possession stopwatch: accumulate real seconds to whichever team
        # currently has the ball. A "no possession set" state (kickoff,
        # not yet assigned) accrues nothing to either side.
        if m.possession_team == "home":
            m.stats.home_possession_seconds += 1
        elif m.possession_team == "away":
            m.stats.away_possession_seconds += 1
        self._recompute_possession_pct(m)
        if self.fullscreen_video:
            # scoreboard_ref isn't part of the page tree while in
            # fullscreen mode (page.controls is replaced entirely), so
            # updating it does nothing — that's why the clock looked
            # frozen until something else forced a full rebuild. Update
            # the fullscreen clock's own persistent ref instead.
            try:
                self.fs_clock_text.value = f"{m.minute}'{m.second:02d}\""
                self.fs_clock_text.update()
            except Exception: pass
        else:
            try:
                self.scoreboard_ref.content = self._build_scoreboard(m)
                self.scoreboard_ref.update()
            except Exception: pass

    def _run_timer(self):
        """Tick every real second; 60 ticks = 1 game minute (req 10)."""
        while True:
            time.sleep(1)
            with self._timer_lock:
                if not self._timer_running: break
            m = self.match
            if not m: break
            self._tick_match_clock(m)
            with self._timer_lock:
                if not self._timer_running: break

    # ══════════════════════════════════════════════════════════════════════════
    # Export / Import  (req 7, 11)
    # ══════════════════════════════════════════════════════════════════════════
    def _export_txt(self):
        """Export match stats, sequences, timestamps, and match details to a
        plain TXT file — no AI content. Can be re-imported later."""
        m = self.match
        if not m: self._snack("No match to export.", ROSE); return
        s   = m.stats
        ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sq_h = generate_sequences(m.events, "home")
        sq_a = generate_sequences(m.events, "away")

        def _tally(etype):
            return tally_action(m.events, etype)

        gk_k_h,_,gk_k_a,_ = _tally("GK_KICK")
        gk_t_h,_,gk_t_a,_ = _tally("GK_THROW")
        drb_h,_,drb_a,_   = _tally("DRIBBLE")
        lp_h,lp_i_h,lp_a,lp_i_a = _tally("LONG_PASS")
        th_h,th_i_h,th_a,th_i_a = _tally("THROW_IN")
        int_h,int_i_h,int_a,int_i_a = _tally("INTERCEPT")
        blk_h,blk_i_h,blk_a,blk_i_a = _tally("BLOCK")
        clr_h,clr_i_h,clr_a,clr_i_a = _tally("CLEAR")
        pen_h,_,pen_a,_ = _tally("PENALTY")
        off_h,_,off_a,_ = _tally("OFFSIDE")
        fw_h,_,fw_a,_   = _tally("FOULS_WON")
        offg_h,_,offg_a,_ = _tally("OFFSIDE_GIVEN")

        def block(is_home):
            pw   = s.home_completed_passes   if is_home else s.away_completed_passes
            cw   = s.home_completed_crosses  if is_home else s.away_completed_crosses
            sh   = s.home_shots              if is_home else s.away_shots
            gl   = s.home_goals              if is_home else s.away_goals
            ast  = s.home_assists            if is_home else s.away_assists
            conv = s.home_conversions        if is_home else s.away_conversions
            dr   = drb_h                     if is_home else drb_a
            fw   = fw_h                      if is_home else fw_a
            ip   = s.home_incomplete_passes  if is_home else s.away_incomplete_passes
            ic   = s.home_incomplete_crosses if is_home else s.away_incomplete_crosses
            ishot= s.home_incomplete_shots   if is_home else s.away_incomplete_shots
            tk   = s.home_tackles            if is_home else s.away_tackles
            sv   = s.home_saves              if is_home else s.away_saves
            fg   = s.home_fouls              if is_home else s.away_fouls
            offt = off_h                     if is_home else off_a
            cl   = clr_h                     if is_home else clr_a
            it   = s.home_incomplete_tackles if is_home else s.away_incomplete_tackles
            ii   = int_i_h                   if is_home else int_i_a
            ib   = blk_i_h                   if is_home else blk_i_a
            yc   = s.home_yellow_cards       if is_home else s.away_yellow_cards
            rc   = s.home_red_cards          if is_home else s.away_red_cards
            sq   = sq_h                      if is_home else sq_a
            poss = s.home_possession         if is_home else s.away_possession
            return (f"Possession: {poss}%\n"
                    f"--- ATTACK STATISTICS ---\n"
                    f"Passes: {pw}\n"
                    f"Long Passes: {lp_h if is_home else lp_a}\n"
                    f"Crosses: {cw}\n"
                    f"Shots: {sh}\n"
                    f"Goals: {gl}\n"
                    f"Assists: {ast}\n"
                    f"Conversions: {conv}\n"
                    f"Dribbles: {dr}\n"
                    f"Fouls Won: {fw}\n"
                    f"GK Kicks: {gk_k_h if is_home else gk_k_a}\n"
                    f"GK Throws: {gk_t_h if is_home else gk_t_a}\n"
                    f"Offsides Given: {offg_h if is_home else offg_a}\n"
                    f"Throw-ins: {th_h if is_home else th_a}\n"
                    f"Incomplete (P!/C!/S!): {ip}/{ic}/{ishot}\n"
                    f"Attack Sequence: {sq['attack']}\n\n"
                    f"--- DEFENCE STATISTICS ---\n"
                    f"Tackles: {tk}\n"
                    f"Interceptions: {int_h if is_home else int_a}\n"
                    f"Blocks: {blk_h if is_home else blk_a}\n"
                    f"Saves: {sv}\n"
                    f"Fouls Given: {fg}\n"
                    f"Offsides: {offt}\n"
                    f"Clears: {cl}\n"
                    f"Penalty Received: {pen_h if is_home else pen_a}\n"
                    f"Incomplete (T!/I!/B!/S!): {it}/{ii}/{ib}/0\n"
                    f"Defence Sequence: {sq['defence']}\n\n"
                    f"--- CARDS ---\n"
                    f"Yellow Cards: {yc}\n"
                    f"Red Cards: {rc}\n"
                    f"Cards Sequence: {sq['cards']}")

        ev_lines = "\n".join(
            f"  {i+1}. [{e.minute}'{e.second:02d}\"] {'HOME' if e.team_id=='home' else 'AWAY'} - "
            f"{e.event_type} — {e.description}"
            + (f" (xG:{e.xg:.2f})" if e.xg else "")
            for i, e in enumerate(m.events)) or "  (no events)"

        content = (
            f"=== FULL GAME REPORT: {m.home_team.short_name} vs {m.away_team.short_name} ===\n"
            f"Timestamp: {ts}\n"
            f"Logged by: {self.logger_name or 'Unknown'}\n"
            f"Final Score: {m.home_score} - {m.away_score}\n"
            f"Final Half-time Count: 2\n"
            f"Match Duration: {m.minute}'{getattr(m,'second',0):02d}\"\n"
            f"Sport: {m.sport}  |  Location: {m.location}  |  Date: {m.date}\n"
            "==============================\n\n"
            f"HOME TEAM: {m.home_team.name} ({m.home_team.short_name})\n"
            "==============================\n"
            f"{block(True)}\n\n"
            "==============================\n"
            f"AWAY TEAM: {m.away_team.name} ({m.away_team.short_name})\n"
            "==============================\n"
            f"{block(False)}\n\n"
            "==============================\n"
            f"MATCH EVENTS ({len(m.events)} total)\n"
            "==============================\n"
            f"{ev_lines}\n\n"
            "===================================================================\n"
            "EMBEDDED RE-IMPORTABLE DATA (DO NOT MODIFY BELOW THIS LINE)\n"
            "===================================================================\n"
            "=== STAT_TRACKER_AI_MATCH_DATA_START ===\n"
            f"{json.dumps(m.to_dict(), indent=2)}\n"
            "=== STAT_TRACKER_AI_MATCH_DATA_END ===\n"
        )
        fname = f"match-{m.home_team.short_name}-vs-{m.away_team.short_name}-{m.date}.txt"
        # ft.FilePicker.save_file(..., src_bytes=...) is the one mechanism
        # that actually works across every target this app builds for:
        # a native OS save dialog on Windows, a share/save sheet on
        # Android, AND — the reason this replaced the previous
        # tkinter.filedialog version — a real browser download on the web
        # build. tkinter opens a dialog on whatever machine is *running*
        # the Python process; for a web deployment that's the server, not
        # the visitor's browser, so it was silently useless there (and
        # would have popped up a confusing dialog on your own machine if
        # you were the one hosting it). FilePicker is a "Service" in this
        # Flet version — see _ensure_file_picker().
        self.page.run_task(self._export_txt_async, fname, content)

    async def _export_txt_async(self, fname: str, content: str):
        try:
            picker = self._ensure_file_picker()
            path = await picker.save_file(
                dialog_title="Export Match Report",
                file_name=fname,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["txt"],
                src_bytes=content.encode("utf-8"))
            if not path:
                return  # user cancelled, or (web) the browser handled the
                        # download directly and there's no local path to report
            self._snack(f"📄  Exported → {os.path.basename(path)}", EMERALD)
        except Exception as ex:
            self._snack(f"Export failed: {ex}", ROSE)

    def _import_txt(self):
        """Re-import a previously exported TXT file. Same FilePicker
        mechanism as export — works whether the file is being picked from
        local disk (desktop/mobile) or uploaded through the browser (web)."""
        self.page.run_task(self._import_txt_async)

    async def _import_txt_async(self):
        try:
            picker = self._ensure_file_picker()
            files = await picker.pick_files(
                dialog_title="Import Stat Tracker TXT",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["txt"],
                with_data=True)  # ask for the file's bytes directly — the
                                 # only way to actually read a file's
                                 # content on the web build, since there's
                                 # no server-local path to open() there
            if not files:
                return
            f = files[0]
            if f.bytes is not None:
                content = f.bytes.decode("utf-8", errors="replace")
            elif f.path:
                with open(f.path, "r", encoding="utf-8") as fh:
                    content = fh.read()
            else:
                self._snack("Could not read the selected file.", ROSE); return
            start = content.find("=== STAT_TRACKER_AI_MATCH_DATA_START ===")
            end   = content.find("=== STAT_TRACKER_AI_MATCH_DATA_END ===")
            if start==-1 or end==-1:
                self._snack("No embedded match data found in file.", ROSE); return
            raw = content[start+len("=== STAT_TRACKER_AI_MATCH_DATA_START ==="):end].strip()
            data = json.loads(raw)
            nm = Match.from_dict(data)
            self.matches.insert(0, nm)
            self.active_match_idx = 0
            self._save(); self._full_refresh()
            self._snack(f"✅  Imported: {nm.title}", EMERALD)
        except Exception as ex:
            self._snack(f"Import failed: {ex}", ROSE)

    def _ensure_file_picker(self):
        """Lazily create the shared FilePicker Service used for both
        export and import. In Flet 0.86.5+, FilePicker is a Service and
        must be registered via page.services, not page.overlay."""
        if self._file_picker is None:
            self._file_picker = ft.FilePicker()
            self.page.services.append(self._file_picker)
        return self._file_picker

    # ══════════════════════════════════════════════════════════════════════════
    # Camera helpers
    # ══════════════════════════════════════════════════════════════════════════
    def _start_camera(self, _=None):
        if self.camera_on:
            # Already running — clicking "Turn On Camera" again while it's
            # on would spawn a second concurrent capture loop fighting over
            # the same device, which is what caused the repeated
            # "can't grab frame" / "index out of range" errors in testing.
            return
        source = self.camera_source

        # Wireless / IP camera / remote Camera Mode device — a pure-Python
        # MJPEG reader with no OpenCV dependency, so this path works
        # identically on desktop, mobile, AND the web build (it's the
        # *only* camera source that works on web — see the is_web checks
        # below).
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            self.camera_on = True; self.camera_error = None
            self._camera_capture_stop.clear()
            threading.Thread(target=self._mjpeg_url_pull_loop, args=(source,), daemon=True).start()
            self._full_refresh(); return

        # Android/iOS/Web on-device camera — native capture via
        # flet-camera, no OpenCV involved (opencv-python has no Android
        # wheel, and no browser/WASM build at all — flet-camera talks to
        # the browser's own getUserMedia API on web instead, the same
        # Camera control and the same "native:" source string as mobile).
        # Checked before the is_web catch-all below so a web build with a
        # "native:" source actually reaches this branch instead of being
        # rejected by it.
        if isinstance(source, str) and source.startswith("native:"):
            if not NATIVE_CAMERA_ENABLED:
                self.camera_error = ("This device's built-in camera is temporarily disabled "
                                      "due to a known bug in the flet-camera plugin itself — "
                                      "use a wireless/IP camera URL instead for now.")
                self.camera_on = False
                self._full_refresh(); return
            lens = source.split(":", 1)[1]

            # Inputter Mode: prefer stc_camera_preview (this project's own
            # custom Dart extension — see its module docstring for why)
            # for a genuinely smooth native/browser-frame-rate live view,
            # with zero Python involvement per frame. Nothing async to
            # kick off here at all — the Dart side handles camera
            # selection/initialization entirely on its own the moment the
            # control is actually shown (see _video_display_widget),
            # triggered just by _full_refresh() below placing it in the
            # tree/updating its "lens" property.
            if self.app_mode != "camera" and HAS_STC_CAMERA_PREVIEW:
                self.camera_on = True; self.camera_error = None
                self._camera_capture_stop.clear()
                self._ensure_stc_preview_ctrl().lens = lens
                self._full_refresh(); return

            # Camera Mode (needs actual frame bytes to broadcast, not
            # just a preview) — or Inputter Mode falling back because
            # stc_camera_preview isn't available in this build for some
            # reason — uses flet-camera's take_picture(), polled
            # repeatedly. See _native_camera_takepicture_poll_loop's
            # docstring for why take_picture() specifically (confirmed
            # working, unlike flet-camera's continuous-preview/streaming
            # path).
            if not HAS_FLET_CAMERA:
                self.camera_error = ("Native camera support isn't installed in this build. "
                                      "Add 'flet-camera' to requirements.txt and rebuild the app.")
                self._full_refresh(); return
            self.camera_on = True; self.camera_error = None
            self._camera_capture_stop.clear()
            # Create the control synchronously so the video panel (built by
            # the _full_refresh() call right below) can already reference
            # it via _video_display_widget() on this very first render,
            # instead of showing a blank frame until the async init below
            # finishes.
            self._ensure_native_camera_ctrl()
            self.page.run_task(self._start_native_camera_async, lens)
            self._full_refresh(); return

        if self.is_web:
            # The desktop OpenCV path still doesn't make sense for a web
            # deployment (no camera is attached to the server) — but the
            # native: branch above now handles the browser's own camera
            # via flet-camera, and the http(s):// branch above handles
            # wireless/IP cameras. Reaching here means camera_source is
            # something else entirely (e.g. a raw device-index int carried
            # over from a save file created on a different platform).
            self.camera_error = ("This camera source isn't available in the web build — "
                                  "use \"This Device's Camera\" or a wireless/IP camera URL instead.")
            self._full_refresh(); return

        # Desktop local device (Windows/macOS/Linux) — OpenCV path.
        self._start_cv2_camera(source)

    def _start_cv2_camera(self, source):
        try:
            import cv2
        except ImportError as ex:
            # The real exception (e.g. "DLL load failed while importing
            # cv2: ...", a missing transitive dependency, a Python
            # ABI/version mismatch between what was pip-installed and what
            # the built app actually runs on) was being silently replaced
            # with a generic "not installed" message that hid the actual
            # reason — even in cases like this one, where the cv2.pyd file
            # genuinely exists on disk but still fails to import. Showing
            # the real text is what actually gets us a diagnosable answer.
            self.camera_error = f"cv2 import failed: {type(ex).__name__}: {ex}"
            self._full_refresh(); return
        _win32_com_init()
        if sys.platform == "win32":
            import ctypes
            ctypes.set_last_error(0)
        # Try the default backend first, then explicitly try MSMF and
        # DSHOW (Windows' two native capture backends) — matches the same
        # multi-backend fallback _detect_cameras uses, so a device that
        # was only detected via one specific backend still actually opens
        # here rather than silently failing again.
        cap = cv2.VideoCapture(source)
        if not cap.isOpened() and isinstance(source, int):
            for backend_name in ("CAP_MSMF", "CAP_DSHOW"):
                backend = getattr(cv2, backend_name, None)
                if backend is None: continue
                cap.release()
                if sys.platform == "win32":
                    ctypes.set_last_error(0)
                cap = cv2.VideoCapture(source, backend)
                if cap.isOpened():
                    break
        if not cap.isOpened():
            win32_hint = ""
            if sys.platform == "win32":
                err_code = ctypes.get_last_error()
                if err_code:
                    try: msg = ctypes.WinError(err_code).strerror
                    except Exception: msg = "(no description available)"
                    win32_hint = f" (WinError {err_code}: {msg})"
            self.camera_error = f"Cannot open camera source: {source}.{win32_hint} Try 'Detect Cameras' to find a working device."
            self._full_refresh(); return
        self._cv2_cap = cap
        self.camera_on = True; self.camera_error = None
        self._camera_capture_stop.clear()

        # Neither plain threading.Thread nor page.run_thread() reliably
        # pushed frame updates to the client in testing — the video stayed
        # frozen on the first frame. Try the async task path (page.run_task,
        # which schedules the coroutine on Flet's own event loop — the most
        # "correct" way to touch the UI from background work in an
        # asyncio-based Flet app) first, then fall back through the other
        # methods. Each path prints which one actually ran, so if it's still
        # frozen we'll know exactly which mechanism to investigate next.
        started_via = None
        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(self._camera_capture_loop_async)
                started_via = "page.run_task (async)"
            except Exception as ex:
                print(f"[Camera] page.run_task failed: {type(ex).__name__}: {ex}")
        if not started_via and hasattr(self.page, "run_thread"):
            try:
                self.page.run_thread(self._camera_capture_loop)
                started_via = "page.run_thread (sync)"
            except Exception as ex:
                print(f"[Camera] page.run_thread failed: {type(ex).__name__}: {ex}")
        if not started_via:
            threading.Thread(target=self._camera_capture_loop, daemon=True).start()
            started_via = "raw threading.Thread (fallback)"
        print(f"[Camera] Capture loop started via: {started_via}")
        self._full_refresh()

    async def _start_native_camera_async(self, lens: str):
        """Initialize the native Android/iOS/Web camera (flet-camera) for
        the requested lens ("back"/"front"), then poll take_picture()
        repeatedly to build the live view — a real photo roughly every
        0.5s rather than smooth continuous video.

        This replaced relying on the native preview surface
        (preview_enabled=True) and continuous frame streaming
        (start_image_stream()/on_stream_image): both of those go through
        flet-camera 0.86.5's continuous-event pipeline, which has a
        confirmed upstream bug — decoding a streamed frame or a preview
        state-change event throws
            TypeError: Instance of 'minified:...': type 'minified:...'
            is not a subtype of type 'minified:...'
        inside the plugin's own compiled Dart/JS code, on both Android
        and Web identically (confirmed via browser DevTools). A previous
        version of this app used take_picture() (a single photo capture)
        successfully — take_picture() sends and receives a far simpler
        payload than the continuous paths (no arguments going in, plain
        bytes coming back — see flet-camera's camera.py), which lines up
        with why that worked while streaming didn't: the bug looks tied
        to the richer continuous-event payloads specifically, not to
        initialize() or capture in general. Polling it repeatedly here
        gets a live-feeling view without touching that code path at all,
        for both Inputter Mode's local view and Camera Mode's broadcast
        frames — both now share the exact same polling loop and the same
        self._latest_jpeg_frame buffer, unlike before where they used two
        different mechanisms."""
        # Wait for any in-flight start/stop on the native camera to
        # genuinely finish first — see _native_camera_busy's definition
        # for why this specific race matters (a Dart-side
        # ConcurrentModificationError from two operations racing on the
        # same native object). Polling rather than an asyncio.Lock so
        # this works the same regardless of which event loop/task
        # actually ends up running this — simple and robust enough for
        # how rarely this contention path is actually hit.
        import asyncio
        wait_iterations = 0
        while self._native_camera_busy and wait_iterations < 40:  # up to ~4s
            await asyncio.sleep(0.1)
            wait_iterations += 1
        self._native_camera_busy = True
        try:
            await self._start_native_camera_inner(lens)
        finally:
            self._native_camera_busy = False

    async def _wait_for_camera_ctrl_mounted(self, cam, timeout: float = 3.0) -> bool:
        """Poll cam.page (raises RuntimeError — "Control must be added to
        the page first" — until it's actually mounted into the tree)
        instead of guessing with a single fixed sleep. This only confirms
        the control is mounted on the *Python/server* side of the tree,
        which is a real prerequisite but not a full guarantee the native
        platform view exists yet on the device — see the settle buffer
        right after this call for that remaining gap."""
        import asyncio
        waited = 0.0
        step = 0.1
        while waited < timeout:
            try:
                _ = cam.page
                return True
            except RuntimeError:
                await asyncio.sleep(step)
                waited += step
        return False

    async def _native_camera_takepicture_poll_loop(self, cam):
        """Runs for as long as self.camera_on stays True and
        self.camera_source is still this native camera — calls
        take_picture() repeatedly and feeds each shot into
        self.camera_image / self._latest_jpeg_frame, the same buffer
        every other camera source (desktop OpenCV, wireless/IP camera)
        already uses. Stopped via self._camera_capture_stop, the same
        stop-event every other capture loop in this app already checks
        (see _camera_capture_loop for the cv2 equivalent) — _stop_camera
        sets it.

        Paced against a target interval rather than a flat per-iteration
        sleep: the previous version always slept a further 0.5s *after*
        take_picture() itself already returned, meaning the real cycle
        time was capture_time + 0.5s — often closer to 1s (~1fps) than
        the 0.5s (~2fps) that looked intended, since take_picture()'s own
        round-trip (device-dependent, often 200-500ms) was being added on
        top rather than counted against the interval. Only sleeping the
        *remainder* of _TARGET_INTERVAL closes that gap — a device where
        take_picture() itself takes close to the full interval will
        naturally just run back-to-back with near-zero extra sleep,
        rather than always paying the full delay regardless."""
        import asyncio
        _TARGET_INTERVAL = 0.35  # ~2.8fps ceiling — see docstring above for why
        first_error_shown = False
        while self.camera_on and not self._camera_capture_stop.is_set():
            if not (isinstance(self.camera_source, str)
                    and self.camera_source.startswith("native:")):
                break  # source changed out from under this loop — stop quietly
            iteration_start = time.monotonic()
            try:
                raw = await cam.take_picture()
                self._latest_jpeg_frame = raw
                self._native_frame_count += 1
                with self._new_frame_cond:
                    self._new_frame_cond.notify_all()
                b64 = base64.b64encode(raw).decode("ascii")
                self.camera_image.src = f"data:image/jpeg;base64,{b64}"
                self.camera_image.update()
                if self.camera_error is not None:
                    self.camera_error = None
                    self._full_refresh()
            except Exception as ex:
                print(f"[NativeCamera] take_picture failed: {type(ex).__name__}: {ex}")
                if not first_error_shown:
                    # Shown once rather than every failed poll — a
                    # transient single failure (camera briefly busy,
                    # etc.) shouldn't flash an error the person then has
                    # to dismiss; only worth surfacing if it's clearly
                    # persistent (still happening a few seconds later).
                    first_error_shown = True
                else:
                    self.camera_error = f"Camera capture failing: {ex}"
                    self._full_refresh()
                    break
            elapsed = time.monotonic() - iteration_start
            remaining = _TARGET_INTERVAL - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

    async def _start_native_camera_inner(self, lens: str):
        try:
            import asyncio
            cam = self._ensure_native_camera_ctrl()
            # Confirm the control is actually mounted before touching it
            # at all — _ensure_native_camera_ctrl() creates it and
            # _full_refresh()/page.update() tells the client to mount it,
            # but that call returns as soon as the message is *sent*, not
            # once the device has actually finished building the native
            # camera view. A blind fixed sleep here was a guess at how
            # long that takes; polling the one thing we can actually check
            # (is it mounted server-side yet) is more reliable, though it
            # still can't see the platform-side view being built, which is
            # why the extra settle buffer below and the retry loop further
            # down both still exist — those cover the remaining gap this
            # can't see. This is what let "Camera is not initialized.
            # Call initialize() first." through even though initialize()
            # genuinely was called (and awaited) first.
            mounted = await self._wait_for_camera_ctrl_mounted(cam, timeout=3.0)
            if not mounted:
                print("[NativeCamera] Control still not mounted after 3s — attempting init anyway.")
            await asyncio.sleep(0.4)  # settle buffer for the native platform view itself
            cameras = await cam.get_available_cameras()
            wanted_dir = (ftc.CameraLensDirection.FRONT if lens == "front"
                          else ftc.CameraLensDirection.BACK)
            desc = next((c for c in cameras if c.lens_direction == wanted_dir),
                        cameras[0] if cameras else None)
            if desc is None:
                self.camera_error = "No camera found on this device."
                self.camera_on = False
                self._full_refresh(); return

            # initialize() itself can still lose the same "not initialized
            # yet" race the mount-poll + settle buffer above are meant to
            # close — on slower devices, a cold app start where the
            # Flutter shell is still finishing its first frame, or (on
            # first-ever launch) the system camera-permission dialog
            # pausing the app's own rendering while it's shown, the
            # settling time needed can genuinely run past what's covered
            # above. 5 attempts with growing backoff (up to ~6s total)
            # gives real headroom for the permission-dialog case
            # specifically, where the delay isn't fixed — it's "however
            # long the user takes to tap Allow".
            last_init_error = None
            _INIT_BACKOFFS = (0.4, 0.8, 1.2, 1.8, 2.4)
            for attempt, backoff in enumerate(_INIT_BACKOFFS):
                try:
                    await cam.initialize(
                        description=desc,
                        resolution_preset=ftc.ResolutionPreset.MEDIUM,
                    )
                    last_init_error = None
                    break
                except Exception as ex:
                    last_init_error = ex
                    print(f"[NativeCamera] initialize attempt {attempt+1} failed: {ex}")
                    await asyncio.sleep(backoff)
            if last_init_error is not None:
                raise last_init_error
            self._native_camera_ready = True
            self.camera_error = None
            self._full_refresh()

            # Both Inputter Mode's local view and Camera Mode's broadcast
            # frames now come from the exact same take_picture()-polling
            # loop — see _native_camera_takepicture_poll_loop's docstring
            # for why (avoids flet-camera 0.86.5's continuous-streaming
            # bug entirely). Camera Mode's MJPEG server already reads
            # from self._latest_jpeg_frame, which this loop keeps
            # updated, so no separate wiring is needed for that mode.
            self.page.run_task(self._native_camera_takepicture_poll_loop, cam)
        except Exception as ex:
            self.camera_error = f"Could not start native camera: {ex}"
            self.camera_on = False
            self._native_camera_ready = False
            self._full_refresh()

    def _ensure_stc_preview_ctrl(self):
        """Lazily create this project's own custom camera preview control
        (see packages/stc_camera_preview) — a smooth live view built
        entirely in Dart, unlike flet-camera's own preview/streaming
        path. No overlay-mounting dance needed the way
        _ensure_native_camera_ctrl() requires: this control isn't driven
        by imperative invoke_method calls at all, just a plain "lens"
        property, so it initializes itself the moment
        _video_display_widget() actually places it in the visible tree —
        ordinary Flet control property diffing handles the rest, the
        same as any other control's properties."""
        if self._stc_preview_ctrl is None:
            self._stc_preview_ctrl = stcam.StcCameraPreview(
                lens="back", expand=True, on_error=self._on_stc_preview_error)
        return self._stc_preview_ctrl

    def _on_stc_preview_error(self, e):
        """stc_camera_preview's on_error — e.data is a plain string (see
        that control's docstring for why: no structured/typed error
        object, deliberately)."""
        msg = getattr(e, "data", None) or "Unknown camera error."
        self.camera_error = f"Could not start native camera: {msg}"
        self.camera_on = False
        self._full_refresh()

    def _ensure_native_camera_ctrl(self):
        """Lazily create the flet-camera control. preview_enabled=False
        and on_stream_image is no longer wired up — both of those are
        exactly the continuous-event code paths hitting flet-camera
        0.86.5's marshaling bug (see _start_native_camera_async for the
        full explanation). This control now exists purely to hold the
        initialize()/take_picture() platform-channel connection; the
        actual visible feed is built entirely in Python from periodic
        take_picture() calls, same as every other camera source in this
        app (desktop OpenCV, wireless/IP camera).

        Always mounted into page.overlay (not just for Camera Mode like
        before) since it's never placed directly in the visible video
        panel anymore either way — Flet requires a control to be mounted
        into the page before platform-channel calls (initialize(),
        get_available_cameras(), take_picture(), etc.) work on it at
        all; without this, calls fail with "Control must be added to the
        page first.\""""
        if self._native_camera_ctrl is None:
            self._native_camera_ctrl = ftc.Camera(preview_enabled=False)
            self.page.overlay.append(self._native_camera_ctrl)
            self.page.update()
        return self._native_camera_ctrl

    def _video_display_widget(self):
        """What to place in the video panel's Container.

        Inputter Mode viewing the native/browser camera specifically
        shows stc_camera_preview — this project's own custom Dart
        extension (see packages/stc_camera_preview) — for genuine native
        frame rate, zero Python involvement per frame. This is the one
        real exception to "always self.camera_image": that control
        renders itself directly (a live Dart-side CameraPreview widget),
        the same way flet-camera's own native preview used to before its
        continuous-event bug was found.

        Every other case — desktop OpenCV, wireless/IP camera URL, or
        Camera Mode (which needs frame *bytes* to broadcast over MJPEG,
        not just a preview, so it still uses flet-camera's take_picture()
        polling loop feeding self.camera_image) — uses the regular
        self.camera_image, same as before."""
        if (self.camera_on and self.app_mode != "camera"
                and isinstance(self.camera_source, str)
                and self.camera_source.startswith("native:")
                and HAS_STC_CAMERA_PREVIEW
                and self._stc_preview_ctrl is not None):
            return self._stc_preview_ctrl
        return self.camera_image

    def _on_native_camera_frame(self, e):
        """flet-camera on_stream_image handler — no longer wired up to
        anything (see _start_native_camera_async for why: this event
        pipeline is exactly what's hitting flet-camera 0.86.5's
        marshaling bug). Left in place only in case a future flet-camera
        release fixes streaming and this becomes worth re-enabling."""
        try:
            raw = e.bytes
            self._latest_jpeg_frame = raw
            with self._new_frame_cond:
                self._new_frame_cond.notify_all()
            self._native_frame_count += 1   # lets _start_native_camera_async's
                                             # timeout check tell "frames are
                                             # arriving" from "stream never
                                             # actually started delivering"
            b64 = base64.b64encode(raw).decode("ascii")
            self.camera_image.src = f"data:image/jpeg;base64,{b64}"
            self.camera_image.update()
        except Exception as ex:
            # print() alone is invisible in a windowed/built app — surface
            # this on screen too (but only once, not per-frame, since a
            # persistent per-frame failure would otherwise spam a refresh
            # 20+ times a second).
            msg = f"Camera frame error: {type(ex).__name__}: {ex}"
            print(f"[NativeCamera] {msg}")
            if self.camera_error != msg:
                self.camera_error = msg
                self._full_refresh()

    def _mjpeg_url_pull_loop(self, url: str):
        """Pure-Python MJPEG-over-HTTP client (multipart/x-mixed-replace).
        No OpenCV dependency, so this is what makes the wireless/IP-camera
        and paired-Camera-Mode-device sources work on Android too, not just
        desktop. Scans the raw byte stream for JPEG SOI/EOI markers rather
        than parsing multipart boundaries precisely — simpler and robust to
        the minor formatting differences between IP-camera apps."""
        printed_error = False
        _MIN_UPDATE_INTERVAL = 1.0 / 30.0  # cap UI pushes at ~30fps
        _last_ui_update = 0.0
        while not self._camera_capture_stop.is_set():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "StatTracker/4"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    buf = b""
                    while not self._camera_capture_stop.is_set():
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        buf += chunk
                        # Drain every complete JPEG currently sitting in buf,
                        # but only keep the LAST one for display. Reading in
                        # 8KB chunks means several whole frames can already
                        # be waiting in the socket buffer by the time we get
                        # here (e.g. right after camera_image.update()'s own
                        # round-trip finished) — displaying every one of
                        # those in order, oldest first, is exactly what was
                        # producing the growing lag: the UI was always a few
                        # frames behind and never caught back up, since each
                        # .update() (a real network/UI round-trip) takes far
                        # longer than a frame decode. Skipping straight to
                        # the newest frame here means the pull loop is
                        # always showing "now", not "a few frames ago", and
                        # any queued frames get discarded instead of forcing
                        # the UI to slowly work through a backlog.
                        newest_jpeg = None
                        while True:
                            start = buf.find(b"\xff\xd8")
                            if start == -1:
                                buf = buf[-2:]  # keep a tail in case SOI is split across reads
                                break
                            end = buf.find(b"\xff\xd9", start + 2)
                            if end == -1:
                                if len(buf) - start > 3_000_000:  # runaway frame — bail out
                                    buf = buf[start + 2:]
                                break
                            end += 2
                            newest_jpeg = buf[start:end]
                            buf = buf[end:]
                        if newest_jpeg is not None:
                            self._latest_jpeg_frame = newest_jpeg
                            with self._new_frame_cond:
                                self._new_frame_cond.notify_all()
                            # Throttle how often we push to the local Flet
                            # UI specifically — the MJPEG passthrough above
                            # (for a second paired device) already runs at
                            # full speed via _latest_jpeg_frame/the
                            # condition variable and isn't affected by this;
                            # this only paces the on-screen preview so it
                            # can't fall behind its own update() calls.
                            now = time.monotonic()
                            if now - _last_ui_update >= _MIN_UPDATE_INTERVAL:
                                _last_ui_update = now
                                b64 = base64.b64encode(newest_jpeg).decode("ascii")
                                self.camera_image.src = f"data:image/jpeg;base64,{b64}"
                                try:
                                    self.camera_image.update()
                                except Exception:
                                    pass
                        if self._camera_capture_stop.is_set():
                            break
            except Exception as ex:
                if not printed_error:
                    print(f"[MJPEG pull] {type(ex).__name__}: {ex}")
                    printed_error = True
                if self._camera_capture_stop.is_set():
                    break
                time.sleep(1.5)  # brief pause before retrying the connection

    def _stop_camera(self, _=None):
        self.camera_on = False
        self._camera_capture_stop.set()
        if self._cv2_cap:
            try: self._cv2_cap.release()
            except Exception: pass
            self._cv2_cap = None
        if self._native_camera_ctrl is not None and self._native_camera_ready:
            async def _stop_native():
                # Same busy-guard _start_native_camera_inner waits on —
                # this needs to wait its turn too, not just set the flag,
                # or a stop can still barge in and race a start that's
                # already mid-flight (the flag alone doesn't help if only
                # one side actually respects it).
                import asyncio
                wait_iterations = 0
                while self._native_camera_busy and wait_iterations < 40:
                    await asyncio.sleep(0.1)
                    wait_iterations += 1
                self._native_camera_busy = True
                try:
                    # No stream/preview to explicitly stop anymore — the
                    # take_picture()-polling loop
                    # (_native_camera_takepicture_poll_loop) already exits
                    # on its own as soon as it sees
                    # self._camera_capture_stop set (above) or
                    # self.camera_on go False, and there's no continuous
                    # stream or native preview surface running in the
                    # background to separately tear down anymore (see
                    # _ensure_native_camera_ctrl / _start_native_camera_async
                    # for why: both preview_enabled and
                    # start_image_stream()/on_stream_image were removed
                    # entirely, since they're what hit flet-camera 0.86.5's
                    # marshaling bug). This used to call
                    # stop_image_stream() and pause_preview() here, which
                    # is exactly what was producing the confusing
                    # "pause_preview: Camera is not initialized" log spam
                    # seen in DevTools — calls into a pipeline that was
                    # never healthy to begin with.
                    pass
                finally:
                    self._native_camera_busy = False
            try:
                self.page.run_task(_stop_native)
            except Exception as ex:
                print(f"[NativeCamera] stop failed: {type(ex).__name__}: {ex}")
            self._native_camera_ready = False
        self._full_refresh()

    def _detect_cameras(self, _=None):
        """Scan for locally-connected camera devices (built-in webcams, USB
        cameras, capture cards). Only devices that actually open AND
        successfully return a frame are listed — this is what was missing
        before, which caused clicking a non-existent 'Cam 2' / 'Cam 3' to
        crash with 'index out of range' / 'can't grab frame' errors.

        The actual cv2 probing runs on a background thread either way (it's
        blocking I/O), but — same lesson learned with the camera capture
        loop — the *UI updates* (self._full_refresh(), self._snack()) need
        to happen via page.run_task/run_thread rather than a raw
        threading.Thread. A raw thread calling .update() worked fine when
        running via `python main.py` (Flet's dev/hot-reload server seems to
        tolerate it) but silently did nothing in the packaged desktop/APK
        build, which is why the button appeared to do nothing there."""
        if self.camera_scanning: return
        self.camera_scanning = True
        self._full_refresh()

        def _scan_blocking():
            """No UI touches in here — just the blocking cv2 probing.
            Tries multiple backends per index: plain default backend, then
            explicit MSMF (Windows' modern native backend) and DSHOW (the
            older one) — a camera that fails to open on one can still open
            fine on another, and this varies by machine/driver/webcam
            model in ways that aren't predictable up front.

            Returns (found, last_error) — the last_error string is surfaced
            on-screen when nothing is found, because a packaged/built
            Windows app has no visible console: a plain print() of the
            real cv2 exception (e.g. a missing backend DLL that got left
            out of the build — a known issue with opencv-python's native
            binaries and Python-packaging tools in general) goes nowhere
            anyone can actually see. This is exactly the class of bug
            behind "works via `python main.py`, fails once built.\""""
            import cv2
            _win32_com_init()
            backends = [None]
            if hasattr(cv2, "CAP_MSMF"): backends.append(cv2.CAP_MSMF)
            if hasattr(cv2, "CAP_DSHOW"): backends.append(cv2.CAP_DSHOW)
            found = []
            last_error = None
            last_win32_error = None
            for i in range(6):
                opened = False
                for backend in backends:
                    try:
                        if sys.platform == "win32":
                            import ctypes
                            ctypes.set_last_error(0)  # clear so a stale code from
                                                       # something unrelated isn't
                                                       # mistaken for this attempt's
                        cap = cv2.VideoCapture(i) if backend is None else cv2.VideoCapture(i, backend)
                        if cap.isOpened():
                            ok, _frame = cap.read()
                            if ok:
                                found.append(i)
                                opened = True
                        elif sys.platform == "win32":
                            # OpenCV itself often swallows the actual reason a
                            # backend failed to open — cap.isOpened() just
                            # comes back False with no Python exception at
                            # all (this is exactly the "no error, no crash,
                            # just consistently finds nothing" case that's
                            # been so hard to get real signal on). The raw
                            # Windows error code underneath sometimes
                            # survives even when OpenCV doesn't surface it —
                            # worth capturing as a last-resort diagnostic.
                            err_code = ctypes.get_last_error()
                            if err_code:
                                try:
                                    msg = ctypes.WinError(err_code).strerror
                                except Exception:
                                    msg = "(no description available)"
                                last_win32_error = f"index {i} backend {backend}: WinError {err_code}: {msg}"
                        cap.release()
                    except Exception as ex:
                        last_error = f"index {i} backend {backend}: {type(ex).__name__}: {ex}"
                        print(f"[DetectCameras] {last_error}")
                    if opened:
                        break
            return found, (last_error or last_win32_error)

        def _finish(found, last_scan_error=None, error=None):
            self.camera_scanning = False
            if error:
                # This used to ONLY show a snack (a toast that disappears
                # after a few seconds) — meaning an unexpected-exception
                # message would flash briefly and be gone before it could
                # even be screenshotted, with the persistent status line
                # underneath the button reverting to plain "no cameras
                # detected yet" as if nothing had happened at all. Now also
                # sets the same persistent camera_error text every other
                # failure path uses, and marks the scan as having run.
                self.camera_error = error
                self._camera_scan_ran_once = True
                self._snack(error, ROSE)
                self._full_refresh()
                return
            self.detected_cameras = found
            self._camera_scan_ran_once = True  # lets the status line distinguish
                                                # "never scanned" from "scanned,
                                                # found nothing, zero exceptions" —
                                                # those two cases used to render
                                                # identical text, which is exactly
                                                # what made a real completed scan
                                                # indistinguishable from a scan
                                                # that silently never ran at all.
            # If the currently selected source isn't actually available,
            # snap to the first real device found (if any) instead of
            # leaving it pointed at something that will fail to open.
            if isinstance(self.camera_source, int) and self.camera_source not in found and found:
                self.camera_source = found[0]
            try:
                if found:
                    self.camera_error = None
                    self._full_refresh()
                    self._snack(f"✅  Found {len(found)} camera(s): {', '.join(f'Cam {i}' for i in found)}", EMERALD)
                else:
                    hint = (" Check Windows Settings → Privacy & security → Camera → "
                            "'Let desktop apps access your camera' is ON." if not self.is_mobile else "")
                    # last_scan_error, when present, is a real cv2 exception
                    # (not just "no device" — an actual failure opening
                    # every backend) — put it in the persistent on-screen
                    # error text (not just a snack, which disappears) so
                    # it's there to screenshot/report. When there's no
                    # exception at all (every backend just cleanly reported
                    # "not opened"), say that explicitly too — that's a
                    # meaningfully different, real result, not a blank.
                    self.camera_error = (
                        f"No cameras detected.{hint} ({last_scan_error})" if last_scan_error else
                        f"Scan completed — every device/backend combination reported 'not opened', "
                        f"with no error raised.{hint}")
                    self._full_refresh()
                    self._snack(f"No local cameras detected.{hint} Or try an IP camera URL instead.", AMBER)
            except Exception: pass

        async def _run_async():
            try:
                import cv2  # noqa: F401 — just checking availability up front
            except ImportError as ex:
                _finish([], error=f"cv2 import failed: {type(ex).__name__}: {ex}")
                return
            # Don't scan while a capture is already open — probing other
            # indices can interfere with an active device on some drivers.
            if self.camera_on:
                self._stop_camera()
            import asyncio
            # This whole block used to have no safety net: if _scan_blocking
            # raised anything at all (rather than catching it internally
            # per-attempt, which it does, but this covers anything
            # unexpected outside that — e.g. in the ctypes/ WinError
            # diagnostic code added most recently), the exception vanished
            # silently, camera_scanning never reset, and no message ever
            # appeared — exactly "the page reloads once, then nothing."
            # Now guaranteed to always reach _finish() with something to
            # show, even on a completely unanticipated failure.
            try:
                found, last_scan_error = await asyncio.to_thread(_scan_blocking)
            except Exception as ex:
                print(f"[DetectCameras] Unexpected failure: {type(ex).__name__}: {ex}")
                _finish([], error=f"Unexpected error during scan: {type(ex).__name__}: {ex}")
                return
            _finish(found, last_scan_error)

        def _run_sync():
            try:
                import cv2  # noqa: F401
            except ImportError as ex:
                _finish([], error=f"cv2 import failed: {type(ex).__name__}: {ex}")
                return
            if self.camera_on:
                self._stop_camera()
            try:
                found, last_scan_error = _scan_blocking()
            except Exception as ex:
                print(f"[DetectCameras] Unexpected failure: {type(ex).__name__}: {ex}")
                _finish([], error=f"Unexpected error during scan: {type(ex).__name__}: {ex}")
                return
            _finish(found, last_scan_error)

        # Same three-tier dispatch used for starting the camera capture
        # loop: prefer scheduling on Flet's own event loop, then Flet's
        # managed thread bridge, and only fall back to a raw thread (which
        # is the one mode that doesn't reliably reach the UI in a built app).
        started_via = None
        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(_run_async)
                started_via = "page.run_task (async)"
            except Exception as ex:
                print(f"[DetectCameras] page.run_task failed: {type(ex).__name__}: {ex}")
        if not started_via and hasattr(self.page, "run_thread"):
            try:
                self.page.run_thread(_run_sync)
                started_via = "page.run_thread (sync)"
            except Exception as ex:
                print(f"[DetectCameras] page.run_thread failed: {type(ex).__name__}: {ex}")
        if not started_via:
            threading.Thread(target=_run_sync, daemon=True).start()
            started_via = "raw threading.Thread (fallback)"
        print(f"[DetectCameras] Scan started via: {started_via}")

    # ── Camera Mode streaming server ────────────────────────────────────────
    def _start_mjpeg_server(self):
        if self._mjpeg_server is not None:
            return   # already running
        if self.is_web:
            # A browser tab fundamentally cannot host a listening TCP
            # server socket — that's not a missing feature or a bug to
            # fix, it's a hard limit of what browser JavaScript/Pyodide
            # can do at all, the same reason no website can accept
            # incoming network connections from other devices on its
            # visitor's behalf. socket.socket().bind()/.listen() for a
            # real server (as opposed to the outgoing connections
            # web_fetch-style code makes) simply isn't implemented in
            # Pyodide's socket module, which is what the raw
            # "[Errno 138] Not supported" was — a real but unhelpful
            # underlying error message, now caught here before it can
            # surface at all. Camera Mode's broadcasting-to-another-
            # device feature is Android/iOS/Windows/macOS/Linux only for
            # this reason; the web build's camera use is limited to
            # Inputter Mode's local live view (see stc_camera_preview)
            # and the wireless/IP-camera *receiving* side, which only
            # ever makes outgoing HTTP requests to a phone/camera
            # elsewhere on the network rather than accepting incoming
            # ones itself.
            self.camera_error = ("Broadcasting Camera Mode's feed to another device isn't "
                                  "possible from a web browser — browsers can't accept incoming "
                                  "network connections at all, only make outgoing ones. Camera "
                                  "Mode's broadcasting works on the Windows, Android, and iOS "
                                  "apps instead; the web build can still be used as the "
                                  "*receiving* Inputter Mode side, watching a stream from one of "
                                  "those.")
            return
        try:
            server = _ThreadingMJPEGServer(("0.0.0.0", MJPEG_PORT), _MJPEGRequestHandler)
            server.app_ref = self
            self._mjpeg_server = server
            self.camera_mode_streaming = True
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            self._mjpeg_server_thread = t
            self._start_discovery_beacon()
        except OSError as ex:
            self._mjpeg_server = None
            self.camera_error = f"Could not start stream server on port {MJPEG_PORT}: {ex}"

    def _start_discovery_beacon(self):
        """Announce this device as a Camera Mode source over UDP broadcast
        every 2s while streaming, so Inputter Mode devices on the same
        network can find it automatically instead of needing the stream
        URL typed in by hand. Best-effort: some networks (notably school
        WiFi with "client/AP isolation" enabled, common precisely on the
        kind of network this app gets used on) block broadcast traffic
        between devices entirely — the manual URL field in the camera
        source picker always still works as a fallback regardless."""
        self._discovery_beacon_stop = threading.Event()

        def _beacon_loop():
            local_ip = get_local_ip()
            url = f"http://{local_ip}:{MJPEG_PORT}/video"
            name = self.logger_name or "Camera Device"
            payload = json.dumps({"magic": DISCOVERY_MAGIC, "name": name, "url": url}).encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                while not self._discovery_beacon_stop.is_set():
                    try:
                        sock.sendto(payload, ("<broadcast>", DISCOVERY_PORT))
                    except OSError as ex:
                        print(f"[Discovery] broadcast send failed: {ex}")
                    self._discovery_beacon_stop.wait(2.0)
            finally:
                sock.close()

        threading.Thread(target=_beacon_loop, daemon=True).start()

    def _stop_discovery_beacon(self):
        stop = getattr(self, "_discovery_beacon_stop", None)
        if stop is not None:
            stop.set()

    async def _deferred_auto_detect_cameras(self):
        import asyncio
        await asyncio.sleep(0)  # let the in-progress build/render finish first
        self._detect_cameras()

    async def _deferred_auto_discover_wireless(self):
        import asyncio
        await asyncio.sleep(0)
        self._scan_for_wireless_cameras()

    def _scan_for_wireless_cameras(self, _=None):
        """Listen for ~4s of UDP broadcasts from any device currently
        running Camera Mode on this network, and list whatever answers —
        the receiving-side counterpart to _start_discovery_beacon(). This
        is what makes wireless pairing "automatic": no stream URL needs to
        be typed in if the filming device is already broadcasting."""
        if self.wireless_discovering:
            return
        self.wireless_discovering = True
        self.discovered_cameras = []
        self._full_refresh()

        def _scan_blocking():
            found = {}
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", DISCOVERY_PORT))
                sock.settimeout(0.5)
                deadline = time.time() + 4.0
                while time.time() < deadline:
                    try:
                        data, _addr = sock.recvfrom(2048)
                        msg = json.loads(data.decode("utf-8"))
                        if msg.get("magic") == DISCOVERY_MAGIC and msg.get("url"):
                            found[msg["url"]] = msg.get("name") or msg["url"]
                    except socket.timeout:
                        continue
                    except (OSError, ValueError, UnicodeDecodeError):
                        continue
            except OSError as ex:
                print(f"[Discovery] listen failed: {ex}")
            finally:
                sock.close()
            return [{"name": name, "url": url} for url, name in found.items()]

        async def _run_async():
            import asyncio
            results = await asyncio.to_thread(_scan_blocking)
            self.discovered_cameras = results
            self.wireless_discovering = False
            self._full_refresh()

        def _run_sync():
            results = _scan_blocking()
            self.discovered_cameras = results
            self.wireless_discovering = False
            self._full_refresh()

        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(_run_async); return
            except Exception as ex:
                print(f"[Discovery] page.run_task failed: {ex}")
        threading.Thread(target=_run_sync, daemon=True).start()

    def _connect_discovered_camera(self, url: str):
        self.camera_source = url
        self.camera_source_url_field.value = url
        if self.camera_on:
            self._stop_camera(); self._start_camera()
        else:
            self._full_refresh()
        self._snack(f"📡  Connected to {url}", EMERALD)

    def _stop_mjpeg_server(self):
        self.camera_mode_streaming = False
        self._stop_discovery_beacon()
        # A fresh pairing handshake is required next time streaming starts.
        self.pair_status = "idle"
        self.pair_pending_code = None
        self.pair_choices = []
        if self._mjpeg_server is not None:
            try: self._mjpeg_server.shutdown()
            except Exception: pass
            try: self._mjpeg_server.server_close()
            except Exception: pass
            self._mjpeg_server = None

    def _toggle_camera_mode_stream(self, _=None):
        if self.camera_mode_streaming:
            self._stop_mjpeg_server()
            self._stop_camera()
        else:
            self._start_camera()
            if self.camera_on:
                self._start_mjpeg_server()
        self._full_refresh()

    # ── Pairing handshake ────────────────────────────────────────────────────
    def pair_start_request(self, code: int):
        """Called from the HTTP server thread when a connecting device (the
        Inputter Mode device) sends /pair/request?code=NN. Generates 3
        decoy numbers, shuffles them in with the real code, and flips
        pair_status to 'pending' so the Camera Mode poller notices and shows
        the confirmation screen. Only touches plain Python state — never
        Flet controls directly — since this runs on a background thread."""
        import random
        decoys = set()
        while len(decoys) < 3:
            d = random.randint(10, 99)
            if d != code:
                decoys.add(d)
        choices = [code] + list(decoys)
        random.shuffle(choices)
        self.pair_pending_code = code
        self.pair_choices = choices
        self.pair_status = "pending"

    def _pair_select(self, choice: int):
        """Camera Mode operator taps one of the 4 numbers shown on their own
        screen — this runs from a local Flet button click, so it's safe to
        refresh the UI directly."""
        if choice == self.pair_pending_code:
            self.pair_status = "approved"
        else:
            self.pair_status = "rejected"
            self.pair_pending_code = None
            self.pair_choices = []
        self._full_refresh()

    async def _pairing_connect_flow_async(self, url: str):
        """Inputter-side half of the handshake: generate our own code, show
        it on THIS device's screen, send it to the target, and wait for the
        Camera Mode operator to confirm it by picking the matching number.
        If the target doesn't understand the pairing endpoints at all (a
        third-party IP camera, drone, or anything not running our own
        Camera Mode) the initial request simply fails/times out, and we
        fall back to connecting directly with no verification — matching
        "cable or an actual camera/drone won't need verification"."""
        import asyncio, random
        import urllib.request, json as _json

        code = random.randint(10, 99)
        base = url.rstrip("/")
        if base.endswith("/video"):
            base = base[: -len("/video")]

        def _http_get(path, timeout=3):
            try:
                with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as resp:
                    return _json.loads(resp.read().decode("utf-8"))
            except Exception:
                return None

        result = await asyncio.to_thread(_http_get, f"/pair/request?code={code}")

        if not result or result.get("status") != "pending":
            # Not a Stat Tracker Camera Mode device (or unreachable) — no
            # pairing protocol to speak to. Connect directly, unverified.
            self.camera_source = url
            if self.camera_on:
                self._stop_camera(); self._start_camera()
            self._full_refresh()
            self._snack(f"📡  Connected to {url} (no pairing available on this source)", EMERALD)
            return

        code_text = ft.Text(str(code), size=48, color=INDIGO4,
                            weight=ft.FontWeight.W_900, font_family="monospace")
        status_text = ft.Text("Waiting for the other device to confirm…", size=11, color=MUTED)
        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.SECURITY, color=AMBER),
                          ft.Text("Pairing", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=320, content=ft.Column([
                txt("Show this number to the person at the Camera Mode device — "
                    "they need to tap the matching number on their screen.", size=11, color=MUTED),
                ft.Container(height=8),
                ft.Row([code_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=8),
                status_text,
            ], spacing=4, tight=True)),
            actions=[ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                                   on_click=lambda _: self.page.pop_dialog())])
        self.page.show_dialog(dlg)

        approved = rejected = False
        for _ in range(45):   # ~45s timeout at 1s polling
            await asyncio.sleep(1)
            status_result = await asyncio.to_thread(_http_get, "/pair/status")
            status = (status_result or {}).get("status")
            if status == "approved":
                approved = True; break
            if status == "rejected":
                rejected = True; break

        try: self.page.pop_dialog()
        except Exception: pass

        if approved:
            self.camera_source = url
            if self.camera_on:
                self._stop_camera(); self._start_camera()
            self._full_refresh()
            self._snack(f"✅  Paired and connected to {url}", EMERALD)
        elif rejected:
            self._snack("❌  Pairing rejected — wrong number selected on the other device.", ROSE)
        else:
            self._snack("⏱  Pairing timed out — try again.", AMBER)

    def _launch_camera_mode_poller(self):
        """Camera Mode's screen only rebuilds on local user actions by
        default, but a pairing request can arrive at any time from the
        network (a different thread). This poller notices when pair_status
        changes and refreshes the screen — using the same 3-tier launch
        strategy that fixed the timer/video freeze, since this also needs
        to reliably touch Flet controls from outside the main click-handler
        flow."""
        self._camera_mode_poll_stop.clear()
        started_via = None
        if hasattr(self.page, "run_task"):
            try:
                self.page.run_task(self._camera_mode_poll_loop_async)
                started_via = "page.run_task (async)"
            except Exception as ex:
                print(f"[Pairing] page.run_task failed: {type(ex).__name__}: {ex}")
        if not started_via and hasattr(self.page, "run_thread"):
            try:
                self.page.run_thread(self._camera_mode_poll_loop)
                started_via = "page.run_thread (sync)"
            except Exception as ex:
                print(f"[Pairing] page.run_thread failed: {type(ex).__name__}: {ex}")
        if not started_via:
            threading.Thread(target=self._camera_mode_poll_loop, daemon=True).start()
            started_via = "raw threading.Thread (fallback)"
        print(f"[Pairing] Camera Mode poller started via: {started_via}")

    def _camera_mode_poll_loop(self):
        last_status = self.pair_status
        while not self._camera_mode_poll_stop.is_set() and self.app_mode == "camera":
            time.sleep(0.5)
            if self.pair_status != last_status:
                last_status = self.pair_status
                try: self._full_refresh()
                except Exception: pass
        self._camera_mode_poller_running = False

    async def _camera_mode_poll_loop_async(self):
        import asyncio
        last_status = self.pair_status
        while not self._camera_mode_poll_stop.is_set() and self.app_mode == "camera":
            await asyncio.sleep(0.5)
            if self.pair_status != last_status:
                last_status = self.pair_status
                try: self._full_refresh()
                except Exception: pass
        self._camera_mode_poller_running = False

    def _encode_frame(self, cv2):
        """Read + JPEG-encode one frame. Returns base64 data URI or None.
        Also stashes the raw JPEG bytes for the MJPEG server (Camera Mode)
        to serve to a connected Inputter Mode device, independent of
        whatever the local Flet UI is doing with the data URI version."""
        _win32_com_init()  # the DirectShow/MSMF capture object was opened
                            # on a different thread — COM objects aren't
                            # safely usable from a thread with no COM
                            # apartment of its own, and asyncio.to_thread's
                            # executor threads (which is what actually
                            # calls this) never have one by default.
        ok, frame = self._cv2_cap.read()
        if not ok:
            return None
        ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok2:
            return None
        raw = buf.tobytes()
        self._latest_jpeg_frame = raw
        with self._new_frame_cond:
            self._new_frame_cond.notify_all()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    async def _camera_capture_loop_async(self):
        """Async version, scheduled via page.run_task() so UI updates happen
        on Flet's own event loop instead of crossing threads at all."""
        import cv2, asyncio
        printed_error = False
        while not self._camera_capture_stop.is_set() and self._cv2_cap:
            # cv2.read()/imencode() are blocking — run them off the event
            # loop so they don't stall it, then do the UI update back on
            # the loop itself.
            data_uri = await asyncio.to_thread(self._encode_frame, cv2)
            if data_uri:
                self.camera_image.src = data_uri
                try:
                    self.camera_image.update()
                except Exception as ex:
                    if not printed_error:
                        print(f"[CameraLoopAsync] update() failed: {type(ex).__name__}: {ex}")
                        printed_error = True
            # No artificial frame-rate cap: cv2.read() already blocks until
            # the camera hardware delivers its next frame, so this loop
            # naturally runs at whatever speed the camera actually
            # supports. asyncio.sleep(0) just yields control back to the
            # event loop between iterations — it adds no real delay.
            await asyncio.sleep(0)

    def _camera_capture_loop(self):
        import cv2
        _win32_com_init()
        printed_error = False
        while not self._camera_capture_stop.is_set() and self._cv2_cap:
            data_uri = self._encode_frame(cv2)
            if data_uri:
                self.camera_image.src = data_uri
                try:
                    self.camera_image.update()
                except Exception as ex:
                    # Print once so it shows up in the console if this
                    # thread's updates are being silently dropped again.
                    if not printed_error:
                        print(f"[CameraLoop] update() failed: {type(ex).__name__}: {ex}")
                        printed_error = True
            # No artificial frame-rate cap — cv2.read() already blocks
            # until the camera hardware has a new frame ready, so removing
            # the old fixed sleep(1/60) lets this run at the camera's own
            # max native speed instead of throttling it down to 60fps.
            time.sleep(0)

    # NOTE: the AI auto-detection loop (analyzing video frames every few
    # seconds and auto-logging detected actions) was removed. It burned
    # through Gemini's free-tier quota (20 requests/day) in under 3 minutes
    # and duplicated the manual logging workflow. The live video is now just
    # a visual aid on the Logger tab — you watch it and click the action
    # buttons yourself, same as before.

    # ══════════════════════════════════════════════════════════════════════════
    # Match management dialogs  (req 8, 9, 16, 24)
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_match_dd(self):
        if not self.matches:
            self.match_dd.options = [ft.dropdown.Option(key="none", text="No fixtures — create one")]
            self.match_dd.value = "none"; return
        self.match_dd.options = [
            ft.dropdown.Option(
                key=str(i),
                text=(f"{m.home_team.short_name} {m.home_score}-{m.away_score} "
                      f"{m.away_team.short_name}  •  {m.date}"))
            for i,m in enumerate(self.matches)]
        self.match_dd.value = str(min(self.active_match_idx, len(self.matches)-1))

    def _on_match_select(self, e):
        try: idx = int(e.control.value)
        except Exception: return
        self.active_match_idx = idx
        self._timer_running = False
        self._stop_camera()
        self.last_logged_action = None; self.can_convert = False
        self._full_refresh()

    def _open_edit_match_dialog(self, _=None):
        """Edit match details after creation — opponent name, location, date,
        team rank, and sport can all be changed post-creation."""
        m = self.match
        if not m:
            self._snack("No match to edit.", ROSE); return

        away_f = ft.TextField(label="Opponent team name", value=m.away_team.name,
                              text_size=12, color=TEXT, bgcolor=SURFACE,
                              border_color=BORDER, focused_border_color=INDIGO,
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        loc_f  = ft.TextField(label="Location / Venue", value=m.location, text_size=12, color=TEXT,
                              bgcolor=SURFACE, border_color=BORDER, focused_border_color=INDIGO,
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        date_f = ft.TextField(label="Date (YYYY-MM-DD)", value=m.date, text_size=12, color=TEXT,
                              bgcolor=SURFACE, border_color=BORDER, focused_border_color=INDIGO,
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        rank_f = ft.Dropdown(label="Team / Age Group", text_size=12, color=TEXT,
                             bgcolor=SURFACE, border_color=BORDER, value=m.away_team.team_rank or "1st Team",
                             options=[ft.dropdown.Option(r) for r in
                                      ["U14A","U14B","U15A","U15B","U16A","U16B","1st Team","2nd Team","Other"]])
        sport_f = ft.Dropdown(label="Sport", text_size=12, color=TEXT, bgcolor=SURFACE,
                              border_color=BORDER, value=m.sport,
                              options=[ft.dropdown.Option(s) for s in
                                       ["SOCCER","HOCKEY","BASKETBALL","RUGBY","RUGBY_SEVENS","WATERPOLO","CRICKET"]])
        err = ft.Text("", color=ROSE, size=11)

        def _save_edit(_):
            at = away_f.value.strip()
            if not at:
                err.value = "Opponent team name is required."
                try: self.page.update()
                except Exception: pass
                return
            m.away_team.name = at
            m.away_team.short_name = at[:3].upper()
            m.away_team.school_name = at
            m.away_team.team_rank = rank_f.value or "1st Team"
            m.location = loc_f.value.strip() or "TBD"
            m.date = date_f.value.strip() or m.date
            m.sport = sport_f.value or m.sport
            m.title = f"St Charles College vs {at}"
            self._save()
            try: self.page.pop_dialog()
            except Exception: pass
            self._full_refresh()
            self._snack("✅  Match details updated.", EMERALD)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.EDIT, color=INDIGO4),
                          ft.Text("Edit Match Details", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=440,
                content=ft.Column([away_f, loc_f, date_f, rank_f, sport_f, err], spacing=10, tight=True)),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                              on_click=lambda _: self.page.pop_dialog()),
                ft.Button("Save Changes", bgcolor=INDIGO6,
                                  style=ft.ButtonStyle(color=TEXT, shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=_save_edit),
            ], actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    def _confirm_delete_match(self, _=None):
        """req 24: Confirm then delete current match and its player scans."""
        if not self.matches: return
        m = self.match
        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.DELETE_FOREVER, color=ROSE),
                          ft.Text("Delete Match?", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=360, content=ft.Text(
                f"Delete '{m.title}'?\n\nAll events, stats and player scans will be permanently removed.",
                size=11, color=TEXT2)),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                              on_click=lambda _: self.page.pop_dialog()),
                ft.Button("Delete", bgcolor=ROSE,
                                  style=ft.ButtonStyle(color=TEXT, shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=lambda _: self._do_delete_match()),
            ], actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    def _do_delete_match(self):
        self.matches.pop(self.active_match_idx)
        self.active_match_idx = max(0, self.active_match_idx - 1)
        self._save()
        try: self.page.pop_dialog()
        except Exception: pass
        self._full_refresh()
        self._snack("🗑  Match deleted.", AMBER)

    def _open_new_match_dialog(self, _=None):
        """This app tracks St Charles College only — home team is always
        SCC and cannot be changed. Only the opponent (away) is entered."""
        home_locked = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.SHIELD, size=14, color="#1E3A8A"),
                            ft.Text("St Charles College (fixed)", size=12, color=TEXT, weight=ft.FontWeight.BOLD)], spacing=8),
            bgcolor=SURFACE2, border=ft.Border.all(1, BORDER), border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10))
        away_f = ft.TextField(label="Opponent team name (required)", text_size=12,
                              color=TEXT, bgcolor=SURFACE,
                              border_color=BORDER, focused_border_color=INDIGO,
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        date_f = ft.TextField(label="Match date (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d"),
                              text_size=12, color=TEXT, bgcolor=SURFACE,
                              border_color=BORDER, focused_border_color=INDIGO,
                              hint_text="Leave as today, or enter a future date to schedule ahead",
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        loc_f  = ft.TextField(label="Location / Venue", text_size=12, color=TEXT,
                              bgcolor=SURFACE, border_color=BORDER, focused_border_color=INDIGO,
                              on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        rank_f = ft.Dropdown(label="Team / Age Group", text_size=12, color=TEXT,
                             bgcolor=SURFACE, border_color=BORDER, value="1st Team",
                             options=[ft.dropdown.Option(r) for r in
                                      ["U14A","U14B","U15A","U15B","U16A","U16B","1st Team","2nd Team","Other"]])
        sport_f = ft.Dropdown(label="Sport", text_size=12, color=TEXT, bgcolor=SURFACE,
                              border_color=BORDER, value="SOCCER",
                              options=[ft.dropdown.Option(s) for s in
                                       ["SOCCER","HOCKEY","BASKETBALL","RUGBY","RUGBY_SEVENS","WATERPOLO","CRICKET"]])
        err = ft.Text("", color=ROSE, size=11)

        def _create(_):
            at = away_f.value.strip()
            if not at:
                err.value = "Opponent team name is required."; self.page.update(); return
            date_str = date_f.value.strip()
            try:
                match_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                err.value = "Invalid date — use YYYY-MM-DD format."; self.page.update(); return
            is_future = match_date > datetime.now().date()
            home_team = build_scc_team("home")
            away_team = Team(id="away", name=at, short_name=at[:3].upper(),
                             logo_color="#15803D", secondary_color="#FFFFFF", badge_symbol="",
                             school_name=at, team_rank=rank_f.value or "1st Team",
                             kit_color_primary="#15803D", kit_color_secondary="#FFFFFF",
                             kit_colors=["#15803D","#FFFFFF"])
            nm = Match(id=f"match-{uuid.uuid4().hex[:8]}", sport=sport_f.value or "SOCCER",
                       title=f"St Charles College vs {at}", date=date_str,
                       location=loc_f.value.strip() or "TBD",
                       home_team=home_team, away_team=away_team,
                       home_score=0, away_score=0, minute=0, second=0,
                       # Matches scheduled ahead start as "not yet begun"
                       # rather than live — you can't be mid-1st-half for a
                       # game that hasn't happened yet.
                       period=("SCHEDULED" if is_future else "1ST_HALF"),
                       is_live=(not is_future), stats=MatchStats(), events=[])
            self.matches.insert(0, nm); self.active_match_idx = 0
            self._save()
            try: self.page.pop_dialog()
            except Exception: pass
            self._full_refresh()
            if is_future:
                self._snack(f"📅  Match scheduled for {date_str}.", SKY)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=INDIGO4),
                          ft.Text("Create New Match", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=440,
                content=ft.Column([home_locked, away_f, date_f, loc_f, rank_f, sport_f, err], spacing=10, tight=True)),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                              on_click=lambda _: self.page.pop_dialog()),
                ft.Button("Create Match", bgcolor=INDIGO6,
                                  style=ft.ButtonStyle(color=TEXT, shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=_create),
            ], actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    # ══════════════════════════════════════════════════════════════════════════
    # Kit Colours dialog  (req 13-15)
    # ══════════════════════════════════════════════════════════════════════════
    def _open_kit_colours_dialog(self, _=None):
        """
        req 13: Add more colours to match kits.
        req 14: SCC colours locked to #1E3A8A / White / Gold.
        req 15: Default 2 colours; can add or remove.

        Uses ft.Row(wrap=True) instead of GridView — more reliable inside
        AlertDialog content in Flet 0.86.x.
        Uses a vertical (stacked) layout instead of side-by-side expand columns.
        """
        m = self.match
        if not m:
            self._snack("No match loaded.", ROSE); return

        home_colours = list(m.home_team.kit_colors or ["#1E3A8A", "#FFFFFF"])
        away_colours = list(m.away_team.kit_colors or ["#15803D", "#FFFFFF"])
        home_locked  = m.home_team.is_scc   # req 14
        away_locked  = m.away_team.is_scc

        status_txt  = ft.Text("", size=11, color=EMERALD)
        home_swatches = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        away_swatches = ft.Row([], wrap=True, spacing=6, run_spacing=6)

        def _make_swatches(colours, locked, side, row_ref):
            """Rebuild the swatch row for one team."""
            items = []
            for idx, c in enumerate(colours):
                dot = ft.Container(
                    width=32, height=32, bgcolor=c, border_radius=6,
                    border=ft.Border.all(2, "#ffffff55"), tooltip=c)
                label = txt(c, size=9, color=MUTED2, mono=True)
                if locked:
                    items.append(ft.Column([dot, label], spacing=3,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER))
                else:
                    def _rm(i=idx, s=side):
                        lst = home_colours if s == "home" else away_colours
                        if len(lst) <= 2:
                            status_txt.value = "Minimum 2 colours required (req 15)"
                            status_txt.color  = ROSE
                            try: status_txt.update()
                            except Exception: pass
                            return
                        lst.pop(i)
                        _refresh()
                    rm_btn = ft.Container(
                        content=ft.Icon(ft.Icons.CLOSE, size=10, color=ROSE),
                        width=18, height=18, bgcolor=ROSE+"33",
                        border=ft.Border.all(1, ROSE+"66"), border_radius=9,
                        on_click=lambda _, fn=_rm: fn(), ink=True)
                    items.append(ft.Column([
                        ft.Stack([dot, ft.Container(content=rm_btn, alignment=ft.Alignment.TOP_RIGHT)]),
                        label,
                    ], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER))
            row_ref.controls = items
            try: row_ref.update()
            except Exception: pass

        def _make_palette(side):
            """Return a ft.Row(wrap=True) palette for adding colours."""
            if home_locked if side=="home" else away_locked:
                return ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK, size=13, color=GOLD),
                        txt("St Charles College colours locked — Navy, White, Gold only (req 14)",
                            size=10, color=GOLD),
                    ], spacing=6),
                    bgcolor=GOLD+"22", border=ft.Border.all(1, GOLD+"44"),
                    border_radius=8, padding=ft.Padding.symmetric(horizontal=10, vertical=6))

            def _add(c, s=side):
                lst = home_colours if s == "home" else away_colours
                if c not in lst:
                    lst.append(c)
                    status_txt.value = f"Added {c} to {s} kit"
                    status_txt.color  = EMERALD
                else:
                    status_txt.value = f"{c} already in {s} kit"
                    status_txt.color  = AMBER
                try: status_txt.update()
                except Exception: pass
                _refresh()

            tiles = [ft.Container(
                width=28, height=28, bgcolor=c, border_radius=5,
                border=ft.Border.all(1, "#ffffff33"),
                on_click=lambda _, col=c, s=side: _add(col, s),
                ink=True, tooltip=f"Add {c} to {side} kit")
                for c in COLOUR_PALETTE]
            return ft.Column([
                txt(f"Click a swatch to add to {side} kit:", size=9, color=MUTED2),
                ft.Row(tiles, wrap=True, spacing=5, run_spacing=5),
            ], spacing=6)

        def _refresh():
            _make_swatches(home_colours, home_locked, "home", home_swatches)
            _make_swatches(away_colours, away_locked, "away", away_swatches)

        # Initial population
        _make_swatches(home_colours, home_locked, "home", home_swatches)
        _make_swatches(away_colours, away_locked, "away", away_swatches)

        def _section(team_label, locked, swatches_ref, side):
            """Build one team's colour section (stacked vertically)."""
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(team_label, size=13, color=TEXT, weight=ft.FontWeight.BOLD),
                        *([ pill("🔒 SCC Kit Locked", GOLD, size=8)] if locked else []),
                    ], spacing=8),
                    swatches_ref,
                    _make_palette(side),
                ], spacing=10),
                bgcolor=SURFACE2, border=ft.Border.all(1, BORDER),
                border_radius=12, padding=14)

        def _save_colours(_):
            m.home_team.kit_colors      = list(home_colours)
            m.away_team.kit_colors      = list(away_colours)
            m.home_team.kit_color_primary   = home_colours[0] if home_colours else "#1E3A8A"
            m.home_team.kit_color_secondary = home_colours[1] if len(home_colours) > 1 else "#FFFFFF"
            m.away_team.kit_color_primary   = away_colours[0] if away_colours else "#15803D"
            m.away_team.kit_color_secondary = away_colours[1] if len(away_colours) > 1 else "#FFFFFF"
            m.home_team.logo_color = home_colours[0] if home_colours else m.home_team.logo_color
            m.away_team.logo_color = away_colours[0] if away_colours else m.away_team.logo_color
            self._save()
            try: self.page.pop_dialog()
            except Exception: pass
            self._full_refresh()
            self._snack("🎨  Kit colours saved.", EMERALD)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([
                ft.Icon(ft.Icons.PALETTE, color=PURPLE4),
                ft.Text("Kit Colours", color=TEXT, size=14, weight=ft.FontWeight.BOLD),
                pill("req 13-15", MUTED2, size=8),
            ], spacing=8),
            content=ft.Container(
                width=500, height=520,
                content=ft.Column([
                    _section(f"🏠 {m.home_team.name}", home_locked, home_swatches, "home"),
                    _section(f"✈️ {m.away_team.name}", away_locked, away_swatches, "away"),
                    status_txt,
                    txt("Min 2 colours per team (req 15) · SCC locked to Navy/#1E3A8A, White, Gold/#FFD700 (req 14)",
                        size=9, color=MUTED2),
                ], spacing=12, scroll=ft.ScrollMode.AUTO)),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                              on_click=lambda _: self.page.pop_dialog()),
                ft.Button("Save Colours", bgcolor=INDIGO6,
                                  style=ft.ButtonStyle(color=TEXT,
                                                       shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=_save_colours),
            ], actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    # NOTE: Auto-loading fixtures from stcharles.sportscap.co.za was removed.
    # The site is a fully client-side rendered SPA — fetching the URL returns
    # only a "Loading…" shell with no fixture data anywhere in the HTML, so it
    # cannot be scraped with requests/BeautifulSoup. Making it work would
    # require a full headless browser (Selenium/Playwright), which is a much
    # heavier dependency than fits this app. Fixtures are created manually via
    # "New Match" instead.

    # ══════════════════════════════════════════════════════════════════════════
    # Dictionary popup
    # ══════════════════════════════════════════════════════════════════════════
    def _open_name_dialog(self, e=None, first_launch=False):
        name_f = ft.TextField(
            label="Your name", value=self.logger_name, autofocus=True,
            text_size=13, color=TEXT, bgcolor=SURFACE,
            border_color=BORDER, focused_border_color=INDIGO,
            on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        err = ft.Text("", color=ROSE, size=11)

        def _save_name(_):
            n = (name_f.value or "").strip()
            if not n:
                err.value = "Please enter a name."
                try: self.page.update()
                except Exception: pass
                return
            self.logger_name = n
            set_logger_name(n)
            if self.is_web: self._save_web()
            try: self.page.pop_dialog()
            except Exception: pass
            self._full_refresh()
            self._snack(f"👋  Welcome, {n}!" if first_launch else f"Name updated to {n}", EMERALD)
            if first_launch and not self._app_mode_ever_chosen:
                self._open_mode_dialog(first_launch=True)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.PERSON, color=INDIGO4),
                          ft.Text("Welcome to Stat Tracker" if first_launch else "Change Your Name",
                                  color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=360, content=ft.Column([
                txt("Enter your name — it will be shown in the app and included "
                    "in exported match reports. You can change it anytime.",
                    size=11, color=MUTED),
                ft.Container(height=6),
                name_f, err,
            ], spacing=6, tight=True)),
            actions=[
                *([] if first_launch else [
                    ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                                  on_click=lambda _: self.page.pop_dialog())]),
                ft.Button("Save", bgcolor=INDIGO6,
                                  style=ft.ButtonStyle(color=TEXT, shape=ft.RoundedRectangleBorder(radius=8)),
                                  on_click=_save_name),
            ], actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    def _open_mode_dialog(self, e=None, first_launch=False):
        def _choose(mode):
            def _click(_):
                if self.app_mode == "camera" and mode != "camera":
                    if self.camera_mode_streaming:
                        self._stop_mjpeg_server()
                    self._stop_camera()
                    self._camera_mode_poll_stop.set()
                self.app_mode = mode
                self._app_mode_ever_chosen = True
                set_app_mode(mode)
                if self.is_web: self._save_web()
                try: self.page.pop_dialog()
                except Exception: pass
                self._full_refresh()
                self._snack(f"✅  {'Inputter' if mode=='inputter' else 'Camera'} Mode active", EMERALD)
            return _click

        mode_card = lambda icon, title, desc, mode, color: ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=28, color=color),
                ft.Text(title, size=14, color=TEXT, weight=ft.FontWeight.BOLD),
                txt(desc, size=10, color=MUTED),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=SURFACE2, border=ft.Border.all(1, color+"66"), border_radius=12,
            padding=16, on_click=_choose(mode), ink=True, expand=True)

        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.DEVICES, color=INDIGO4),
                          ft.Text("Choose Device Mode", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=440, content=ft.Column([
                txt("Using two devices? One can film the match and stream it to the "
                    "other, which logs stats. Pick what this device does — you can "
                    "switch anytime from the navbar.", size=11, color=MUTED),
                ft.Container(height=8),
                ft.Row([
                    mode_card(ft.Icons.KEYBOARD, "Inputter Mode",
                             "Log match stats. Can receive a video feed from a Camera Mode device.",
                             "inputter", INDIGO4),
                    mode_card(ft.Icons.VIDEOCAM, "Camera Mode",
                             "Capture video and stream it to an Inputter Mode device.",
                             "camera", EMERALD),
                ], spacing=10),
            ], spacing=6, tight=True)),
            actions=([] if first_launch else [
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=MUTED),
                              on_click=lambda _: self.page.pop_dialog())]),
            actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    def _open_dictionary_dialog(self, _=None):
        def entry(name, definition, has_inc=False):
            return ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text(name, size=13, color=INDIGO3, weight=ft.FontWeight.BOLD),
                            pill("+ Incomplete", MUTED2, size=8) if has_inc else ft.Container()], spacing=6),
                    ft.Text(definition, size=11, color=TEXT2, selectable=True),
                ], spacing=3),
                bgcolor=SURFACE2, border=ft.Border.all(1, BORDER),
                border_radius=10, padding=10)

        rows  = [entry(n, d, hi) for n, _, hi, d in ACTION_RULES]
        rows += [entry(n, d) for n, d in DICTIONARY_ONLY_ENTRIES]
        dlg = ft.AlertDialog(
            modal=True, bgcolor=SURFACE,
            title=ft.Row([ft.Icon(ft.Icons.MENU_BOOK, color=AMBER),
                          ft.Text("Action Dictionary", color=TEXT, size=14, weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=520, height=520,
                content=ft.Column(
                    [txt("Official definitions for every loggable action.", size=10, color=MUTED),
                     ft.Divider(height=1, color=BORDER), *rows],
                    spacing=8, scroll=ft.ScrollMode.AUTO, tight=True)),
            actions=[ft.TextButton("Close", style=ft.ButtonStyle(color=MUTED),
                                   on_click=lambda _: self.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END)
        self.page.show_dialog(dlg)

    # ══════════════════════════════════════════════════════════════════════════
    # Keyboard shortcuts
    # ══════════════════════════════════════════════════════════════════════════
    def _mark_input_focused(self, _=None):
        self._text_input_focused = True

    def _mark_input_blurred(self, _=None):
        self._text_input_focused = False

    def _on_keyboard(self, e: ft.KeyboardEvent):
        if getattr(self, "_text_input_focused", False):
            # A text field (IP camera URL, opponent name, date, location,
            # your name, etc.) currently has focus — every one of those
            # boxes is set to call _mark_input_focused()/_mark_input_blurred()
            # on focus/blur precisely so this guard can tell the difference.
            # Without it, every letter typed anywhere in the app (while on
            # the Logger tab) also matched one of the single-key logging
            # shortcuts below — e.g. typing "http://" into the IP camera
            # field silently logged Fouls Given/Throw-in/Pass/Cross/etc. and
            # forced a full page rebuild on almost every keystroke, which is
            # what made continuous typing in that field impossible.
            return
        if e.key == "Escape" and self.fullscreen_video:
            self._exit_fullscreen_video()
            return
        if self.active_tab != "LOGGER" or not self.match: return
        km = {
            "g": ("GOAL","Goal",0.65),
            "p": ("PASS","Pass",0.0),
            "i": ("PASS_INCOMPLETE","Pass (Incomplete)",0.0),
            "c": ("CROSS","Cross",0.0),
            "v": ("CROSS_INCOMPLETE","Cross (Incomplete)",0.0),
            "l": ("LONG_PASS","Long Pass",0.0),
            "t": ("THROW_IN","Throw In",0.0),
            "s": ("SHOT","Shot",0.15),
            "x": ("SHOT_INCOMPLETE","Shot (Incomplete)",0.0),
            "k": ("TACKLE","Tackle",0.0),
            "e": ("INTERCEPT","Intercept",0.0),
            "b": ("BLOCK","Block",0.0),
            "d": ("SAVE","Save",0.0),
            "o": ("OFFSIDE","Offside",0.0),
            "u": ("CLEAR","Clear",0.0),
            "w": ("FOULS_WON","Fouls Won",0.0),
            "j": ("PENALTY","Penalty",0.0),
            "m": ("CORNER","Corner",0.0),
            "a": ("ASSIST","Assist",0.0),
            "n": ("CONVERSION","Conversion",0.5),
            "h": ("FOULS_GIVEN","Fouls Given",0.0),
            "z": ("DRIBBLE","Dribble",0.0),
            "y": ("YELLOW_CARD","Yellow Card",0.0),
            "r": ("RED_CARD","Red Card",0.0),
        }
        key = e.key.lower()
        if key == "q":
            self._log_turnover()
            return
        if key in km:
            etype, lbl, xg = km[key]
            if etype in INCOMPLETE_PARENTS:
                self.last_logged_action = etype
            self.can_convert = etype in ATTACK_PARENTS
            self._quick_action(etype, lbl, xg)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main(page: ft.Page):
    StatTrackerApp(page)


if __name__ == "__main__":
    ft.run(main)
