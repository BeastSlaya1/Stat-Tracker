"""
StcCameraPreview control definition.

Deliberately minimal by design — see the Dart side
(flutter/stc_camera_preview/lib/src/camera_preview.dart) for the full
reasoning. The short version: flet-camera 0.86.5 has a confirmed crash
originating in Flet's own core Python<->Dart marshaling layer specifically
when complex typed values (Python Enum members, dataclass instances) cross
that boundary — not in flet-camera's own Dart code, which is clean, and
not in camera access itself (take_picture(), which sends zero arguments
and returns plain bytes, is confirmed working). This control's entire
interface is one plain string property ("lens") and one plain string
event ("error") — the same simple property/event mechanism every ordinary
Flet control already relies on everywhere, deliberately avoiding anything
resembling the specific shape that's been observed to crash.

Camera selection, permission handling, and building the actual live
preview widget all happen entirely on the Dart side using the official
`camera` Flutter plugin directly — nothing about the live preview itself
requires a Python round-trip per frame, which is what gets genuine native
frame rate back (compared to the take_picture()-polling fallback
elsewhere in this app, which is real but capped at roughly 2 shots/sec by
hardware capture latency).
"""

from typing import Optional

import flet as ft

__all__ = ["StcCameraPreview"]


@ft.control("StcCameraPreview")
class StcCameraPreview(ft.LayoutControl):
    """A live camera preview with no Python-side per-frame involvement.

    Set `lens` to switch cameras — the Dart side re-initializes itself
    automatically whenever this value changes (see didUpdateWidget in the
    Dart implementation), the same way changing any ordinary Flet
    control's property triggers a rebuild.

    Set `broadcasting=True` (Camera Mode only) to additionally get frame
    *bytes* via on_frame, for feeding the MJPEG server — this control now
    covers both roles (Inputter Mode's smooth local preview, and Camera
    Mode's actual broadcast source) without needing flet-camera at all;
    see the Dart side's docstring for the full reasoning and the
    take_picture()-polling fallback this replaces.
    """

    lens: str = "back"
    """Which camera to use: "back" or "front". Changing this after the
    control is already showing a preview causes it to reinitialize with
    the newly-selected camera automatically."""

    broadcasting: bool = False
    """Set True (Camera Mode only) to also start a real continuous camera
    image stream on the Dart side and emit frames via on_frame — this is
    what replaces flet-camera's take_picture()-polling fallback (capped
    at roughly 2.8fps by the hardware photo pipeline) with genuine video
    framerate. Has no effect on the on-screen preview itself, which
    keeps rendering natively either way; this only controls whether
    frame *bytes* are additionally produced for the MJPEG server to
    broadcast. Android only for now (see the Dart side's docstring) —
    harmlessly ignored on web/other platforms."""

    on_error: Optional[ft.EventHandler[str]] = None
    """Fires with a plain human-readable error message (e.g. permission
    denied, no camera found, hardware busy) if initialization fails.
    Deliberately a plain string, not a structured/typed error object —
    same reasoning as everywhere else in this control."""

    on_frame: Optional[ft.EventHandler[str]] = None
    """Fires repeatedly while broadcasting=True, once per captured frame,
    with e.data being a plain base64-encoded JPEG string — deliberately
    still just a String crossing the bridge, same reasoning as on_error.
    Decode with base64.b64decode(e.data) to get raw JPEG bytes, same
    format _latest_jpeg_frame/the MJPEG server already expect everywhere
    else in this app."""
