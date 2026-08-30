import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flet/flet.dart';
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

      // enableAudio: false, and no imageFormatGroup/fps/bitrate
      // arguments at all — CameraController's constructor here is
      // plain Dart, entirely on this side of the bridge, so none of
      // this crosses into the marshaling layer that's actually broken.
      // ResolutionPreset.medium is a Dart-side literal, never sent from
      // Python — the whole point.
      final controller = CameraController(
        description,
        ResolutionPreset.medium,
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
      child = CameraPreview(controller);
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
