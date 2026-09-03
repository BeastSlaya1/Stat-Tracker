import 'dart:async';
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

/// A deliberately minimal live camera preview control.
///
/// Why this exists at all: flet-camera 0.86.5's Camera control hits a
/// confirmed crash — "TypeError: ... is not a subtype of type ..." —
/// coming from deep inside Flet's own core SDK (the stack trace runs
/// through main.dart.js at line numbers far outside flet-camera's own
/// small compiled unit), not from flet-camera's own Dart code, which is
/// clean. The one thing every crashing call has in common —
/// initialize() (a CameraDescription object + a ResolutionPreset enum
/// going out) and continuous streaming (a CameraImage-derived event with
/// several enum fields coming back) — is that they carry complex typed
/// values (Dart enums, structured objects) across the Python<->Dart
/// bridge. take_picture() sends zero arguments and returns plain bytes,
/// and take_picture() is confirmed working — which lines up with "the
/// bug is in marshaling complex types specifically, not in camera
/// access itself".
///
/// So this control's entire Python<->Dart interface is exactly one
/// plain string property: "lens" ("back" or "front"). No enums, no
/// custom object arguments, no custom events with structured payloads —
/// just a string property, which is the single most common, most
/// heavily-exercised code path in all of Flet (every text field, every
/// button label, every single control with any string property at all
/// goes through it) — if that were broken, nothing in Flet would work.
/// Camera selection, initialization, and building the actual live
/// CameraPreview widget all happen entirely inside this Dart code,
/// using the official camera plugin directly — nothing about that
/// requires crossing back into Python at all.
///
/// Camera Mode's need for frame *bytes* (to broadcast over MJPEG) isn't
/// handled here — that still goes through flet-camera's own
/// take_picture(), which is already confirmed to work fine on its own,
/// polled repeatedly (see main.py's _native_camera_takepicture_poll_loop).
/// This control is specifically for Inputter Mode's local live view,
/// where getting back genuine native frame rate (rather than a
/// still-image slideshow) actually matters.
class StcCameraPreviewControl extends StatefulWidget {
  final Control control;

  const StcCameraPreviewControl({super.key, required this.control});

  @override
  State<StcCameraPreviewControl> createState() =>
      _StcCameraPreviewControlState();
}

class _StcCameraPreviewControlState extends State<StcCameraPreviewControl> {
  CameraController? _controller;
  String? _initializedLens;
  bool _initializing = false;
  String? _lastError;
  bool _mirror = false;

  @override
  void initState() {
    super.initState();
    _maybeReinitialize();
  }

  @override
  void didUpdateWidget(covariant StcCameraPreviewControl oldWidget) {
    super.didUpdateWidget(oldWidget);
    _maybeReinitialize();
  }

  @override
  void dispose() {
    _disposeController();
    super.dispose();
  }

  void _disposeController() {
    final controller = _controller;
    _controller = null;
    if (controller != null) {
      // Fire-and-forget: dispose() is async, but this widget is already
      // gone by the time it matters, and nothing here needs to await it.
      unawaited(controller.dispose());
    }
  }

  Future<void> _maybeReinitialize() async {
    // Plain string property read — getString() is the exact same helper
    // every ordinary Flet control's string properties already use
    // everywhere else in the framework, deliberately not anything
    // custom, to stay on the most well-trodden path possible.
    final lens = widget.control.getString("lens", "back")!;
    if (lens == _initializedLens || _initializing) {
      return;
    }
    _initializing = true;
    _initializedLens = lens;
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw Exception("No camera found on this device.");
      }
      final wantedDirection =
          lens == "front" ? CameraLensDirection.front : CameraLensDirection.back;
      final description = cameras.firstWhere(
        (c) => c.lensDirection == wantedDirection,
        orElse: () => cameras.first,
      );
      // Mirror based on the camera actually resolved above (its real
      // lensDirection), not the requested lens string — falling back to
      // cameras.first (a few lines up) means the camera we end up with
      // can genuinely differ from what was asked for, e.g. a laptop's
      // single built-in webcam typically reports as "front" regardless
      // of which lens this control asked for, since there's no "back"
      // option to find at all. The `camera` plugin's CameraPreview
      // widget does NOT auto-mirror front-facing cameras on its own —
      // that's a well-documented gap in the plugin itself, not
      // something specific to this app, and without correcting it a
      // front/selfie-style camera shows raw and backwards (text held up
      // to the camera reads mirror-flipped, movement direction feels
      // reversed) instead of the natural "looking in a mirror" view
      // people expect from this kind of camera.
      _mirror = description.lensDirection == CameraLensDirection.front;

      // enableAudio: false, and no imageFormatGroup/fps/bitrate
      // arguments at all — CameraController's constructor here is
      // plain Dart, entirely on this side of the bridge, so none of
      // this crosses into the marshaling layer that's actually broken.
      // ResolutionPreset.veryHigh (not .medium, and not .high either
      // now) is a Dart-side literal, never sent from Python — the whole
      // point. Bumped up twice: medium -> high after the first
      // side-by-side comparison against the phone's own camera app
      // showed medium looking noticeably blurrier (medium is roughly
      // 480p-class on most devices), then high -> veryHigh after a
      // second comparison showed high still visibly softer than the
      // phone's own camera app, with the difference described as not
      // being explained by the device's own hardware capability —
      // veryHigh asks for something close to the sensor's actual
      // resolution (device-dependent, often 1080p+), trading a bit more
      // decode/render cost for a live preview that's redrawn
      // continuously in exchange for real sharpness. If it's still not
      // sharp enough after this, ResolutionPreset.max is the last step
      // up (full native sensor resolution) — but that's a meaningfully
      // heavier cost for a continuously-redrawn preview, worth trying
      // only if veryHigh genuinely isn't enough.
      final controller = CameraController(
        description,
        ResolutionPreset.veryHigh,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      _disposeController();
      setState(() {
        _controller = controller;
        _lastError = null;
        _initializing = false;
      });
    } catch (ex) {
      if (!mounted) return;
      setState(() {
        _lastError = ex.toString();
        _initializing = false;
      });
      // Plain string event — same reasoning as the lens property above.
      widget.control.triggerEvent("error", ex.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    Widget child;
    if (controller != null && controller.value.isInitialized) {
      // ValueListenableBuilder here is what actually fixes "stays
      // vertical when the phone is turned sideways" — without it, this
      // widget only ever rebuilds when Python changes the "lens"
      // property (see didUpdateWidget), never in response to the phone
      // physically rotating. CameraController is itself a
      // ValueNotifier<CameraValue>, and (since camera plugin ^0.12.0)
      // automatically listens for the OS's own orientation-change
      // events — that update is what this listens for, so a rotation is
      // what actually triggers a fresh rebuild of CameraPreview below.
      //
      // Rotation itself, after two wrong attempts, is now derived from
      // actual evidence rather than more theorizing:
      //   1. Original: no correction at all -> "stays vertical" (this
      //      part was really about not rebuilding on rotation at all,
      //      fixed above by the ValueListenableBuilder).
      //   2. A dynamic sensorOrientation+deviceOrientation formula
      //      (borrowed from Google's own ML Kit example, meant for
      //      correcting raw image bytes for an ML model — a different
      //      job from rotating an already-rendered preview texture) ->
      //      "upside down" on Android.
      //   3. No manual rotation at all again (trusting the plugin to
      //      handle it internally, which turned out to be wrong for
      //      this device) -> "sideways" on Android, and incidentally
      //      "sideways" on web too (a desktop monitor isn't a
      //      physically rotatable device at all, so deviceOrientation
      //      was never meaningful there in the first place).
      // A 180° error (attempt 2's "upside down") is its own mirror
      // image regardless of rotation direction, which makes the
      // correct value computable directly from that result rather than
      // guessed again: exactly two quarter-turns away from whatever
      // attempt 2 produced. With baseDegrees=0 (portraitUp) and a
      // typical back-camera sensorOrientation of 90°, attempt 2's
      // formula reduced to quarterTurns = 1 — so the corrected value
      // below is (1 + 2) % 4 = 3, expressed generally as
      // ((sensorOrientation ~/ 90) + 2) % 4 so it still adapts to
      // whatever sensorOrientation this specific device/camera actually
      // reports rather than hardcoding 3 outright. Deliberately static
      // (no deviceOrientation dependency this time) — sensorOrientation
      // is a fixed per-camera constant, not something that changes as
      // the phone physically rotates, and dropping the dynamic part
      // entirely is also what avoids reintroducing web's false-positive
      // "landscape" misdetection from attempt 2.
      final quarterTurns =
          kIsWeb ? 0 : ((controller.description.sensorOrientation ~/ 90) + 2) % 4;
      final oriented = ValueListenableBuilder<CameraValue>(
        valueListenable: controller,
        builder: (context, value, _) => RotatedBox(
          quarterTurns: quarterTurns,
          child: CameraPreview(controller),
        ),
      );
      // See the comment where _mirror is set above for why this is
      // needed at all. Matrix4.rotationY(pi) is a standard horizontal
      // (left-right) mirror flip around the vertical axis — the same
      // effect as CSS's transform: scaleX(-1), which is what browsers'
      // own <video> elements apply by convention for a front-facing
      // camera preview (that convention is exactly what's missing here
      // without this, since CameraPreview shows the raw unflipped feed).
      child = _mirror
          ? Transform(
              alignment: Alignment.center,
              transform: Matrix4.rotationY(math.pi),
              child: oriented,
            )
          : oriented;
    } else if (_lastError != null) {
      child = Center(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(
            _lastError!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.redAccent, fontSize: 12),
          ),
        ),
      );
    } else {
      child = const Center(child: CircularProgressIndicator());
    }
    return LayoutControl(control: widget.control, child: child);
  }
}
