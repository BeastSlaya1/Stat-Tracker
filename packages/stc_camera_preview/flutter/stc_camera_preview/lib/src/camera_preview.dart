import 'dart:async';
import 'bgra_frame.dart';
import 'frame_orientation.dart';
import 'dart:convert' show base64Encode;
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart'
    show kIsWeb, compute, debugPrint, defaultTargetPlatform, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;

/// Plain-data bundle for one raw camera frame, handed to [_frameToJpeg]
/// via [compute] so the actual YUV->RGB conversion + JPEG encode (both
/// CPU-heavy, pure-Dart work) run on a background isolate instead of the
/// UI thread. Every field is a primitive or [Uint8List] — both are
/// isolate-transferable — deliberately for the same reason the
/// Python<->Dart bridge above only ever crosses plain strings: keeping
/// well clear of anything that could re-trigger a marshaling-style bug,
/// even though isolate messaging is a completely different mechanism
/// from the Python bridge and was never implicated in that bug at all.
class _FrameConversionArgs {
  final Uint8List yPlane;
  final Uint8List uPlane;
  final Uint8List vPlane;
  final int yRowStride;
  final int uvRowStride;
  final int uvPixelStride;
  final int width;
  final int height;
  final int quarterTurns;
  final bool mirror;
  final int maxWidth;
  final int quality;

  const _FrameConversionArgs({
    required this.yPlane,
    required this.uPlane,
    required this.vPlane,
    required this.yRowStride,
    required this.uvRowStride,
    required this.uvPixelStride,
    required this.width,
    required this.height,
    required this.quarterTurns,
    required this.mirror,
    required this.maxWidth,
    required this.quality,
  });
}

/// Runs entirely on a background isolate (see [_FrameConversionArgs]'s
/// docstring). Converts one YUV420 camera frame straight to a
/// downscaled, correctly-oriented JPEG — this is what replaces
/// take_picture()'s hardware photo-pipeline round trip (200-500ms per
/// still shot) with something that can run at genuine video framerate:
/// the image stream below hands us raw sensor planes directly, no
/// autofocus/photo-processing pipeline involved at all.
///
/// Sampling (via `step`) downscales and reduces conversion cost in the
/// same pass, rather than converting at full sensor resolution and
/// resizing afterward — for a live broadcast/preview feed (not an
/// archival photo), matching maxWidth to roughly what the receiving
/// device's video panel actually displays is what makes this fast
/// enough to run continuously rather than a one-off cost.
Uint8List? _frameToJpeg(_FrameConversionArgs a) {
  try {
    final step = a.width > a.maxWidth ? (a.width / a.maxWidth).round() : 1;
    final outW = (a.width / step).floor();
    final outH = (a.height / step).floor();
    final image = img.Image(width: outW, height: outH);
    for (int oy = 0; oy < outH; oy++) {
      final y = oy * step;
      final yRow = y * a.yRowStride;
      final uvRow = (y >> 1) * a.uvRowStride;
      for (int ox = 0; ox < outW; ox++) {
        final x = ox * step;
        final yVal = a.yPlane[yRow + x];
        final uvCol = (x >> 1) * a.uvPixelStride;
        final uVal = a.uPlane[uvRow + uvCol];
        final vVal = a.vPlane[uvRow + uvCol];
        // Standard BT.601 YUV -> RGB, the same conversion every
        // camera-frame-processing tutorial for this plugin uses — full
        // sensor data (yPlane/uPlane/vPlane), not anything derived from
        // the CameraImage object itself, so nothing enum-typed or
        // otherwise "complex" from the plugin ever crosses back out of
        // this isolate; only the primitives above went in, and only
        // raw JPEG bytes come out.
        // .clamp() on num returns num, not int — .toInt() keeps
        // setPixelRgb's (int, int, int) signature happy.
        final r = (yVal + 1.370705 * (vVal - 128)).round().clamp(0, 255).toInt();
        final g = (yVal - 0.337633 * (uVal - 128) - 0.698001 * (vVal - 128))
            .round()
            .clamp(0, 255)
            .toInt();
        final b = (yVal + 1.732446 * (uVal - 128)).round().clamp(0, 255).toInt();
        image.setPixelRgb(ox, oy, r, g, b);
      }
    }
    var oriented = image;
    if (a.quarterTurns != 0) {
      oriented = img.copyRotate(oriented, angle: a.quarterTurns * 90);
    }
    if (a.mirror) {
      oriented = img.flipHorizontal(oriented);
    }
    return Uint8List.fromList(img.encodeJpg(oriented, quality: a.quality));
  } catch (_) {
    return null; // a corrupt/short-lived frame just gets dropped —
                 // there'll be another one along in a few milliseconds.
  }
}

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
/// Camera Mode's need for frame *bytes* (to broadcast over MJPEG) is now
/// ALSO handled here, via the "broadcasting" bool property: when true,
/// this starts a real continuous camera image stream
/// (CameraController.startImageStream) alongside the on-screen preview
/// and emits each frame — JPEG-encoded on a background isolate, see
/// _frameToJpeg above — back to Python as a plain base64 string through
/// the "frame" event. That's still just a String crossing the bridge,
/// the same reasoning as "lens" and "error" above; only the frame's
/// *encoding* (base64 text) changed, not the shape of what crosses the
/// bridge. This is what replaces flet-camera's take_picture()-polling
/// fallback (main.py's _native_camera_takepicture_poll_loop, capped at
/// roughly 2.8fps by the hardware photo pipeline) with something that
/// can run at genuine video framerate instead of a still-image
/// slideshow — take_picture() takes a *photo* every time (autofocus +
/// full image-processing pipeline, 200-500ms), whereas the image stream
/// hands us raw, already-captured sensor frames directly.
///
/// startImageStream() only works on Android/iOS, never on web (the
/// `camera` plugin throws UnimplementedError there) — "broadcasting" is
/// only ever set true from Camera Mode, which the web build doesn't
/// offer in the first place, but this control still guards against it
/// defensively. Android uses YUV420 and iOS uses BGRA8888 frames.
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
  bool? _initializedForBroadcasting;
  // CameraX has shared native state, including across widget replacements.
  // Release the previous owner before creating any replacement controller.
  static Future<void>? _cameraOperations;
  static _StcCameraPreviewControlState? _cameraOwner;
  int _frameGeneration = 0;
  String? _lastError;
  bool _mirror = false;
  bool _streamingImages = false;
  bool _encodingFrame = false;

  static const int _broadcastMaxWidth = 480;  // deliberately smaller than
                                               // cv2's own 960-ish target
                                               // elsewhere in this app —
                                               // see the comment below for
                                               // why this one needs to be
                                               // more conservative.
  static const int _broadcastQuality = 70;    // matches cv2's own capture
                                               // path elsewhere in this app
                                               // for a network-appropriate
                                               // broadcast/preview quality,
                                               // not archival quality.
  // _broadcastMaxWidth controls how many pixels _frameToJpeg's manual
  // YUV->RGB loop actually touches per frame (see its "step" sampling) —
  // and that loop is the real cost here: it's pure Dart doing per-pixel
  // floating-point math, not a hardware-accelerated codec. cv2's own
  // encode path elsewhere in this app is a compiled C++ routine calling
  // into libjpeg-turbo, which is a completely different performance
  // class from a Dart isolate looping pixel-by-pixel — the two constants
  // look parallel but aren't, which is why this one is set noticeably
  // lower even though the visual target (a live broadcast/preview feed,
  // not archival quality) is the same. This has ZERO effect on the
  // on-screen local preview's sharpness — that's the CameraPreview
  // widget rendering the camera's native texture directly via the GPU,
  // completely separate from this conversion path, which only feeds the
  // MJPEG broadcast to a paired device.

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
    // Flutter dispose is synchronous; enqueue native cleanup so the next
    // widget must wait for it rather than racing a new camera open.
    unawaited(_enqueueCameraOperation(_disposeController).catchError((Object ex) {
      debugPrint("Could not release camera: $ex");
    }));
    super.dispose();
  }

  bool get _wantsBroadcast =>
      widget.control.getBool("broadcasting", false)!;

  int _consecutiveEncodeFailures = 0;
  int _consecutiveTimeouts = 0;
  bool _reportedBroadcastFailure = false;

  void _onCameraImage(CameraImage image) {
    // Always process only the newest available frame, exactly the same
    // backpressure principle this project's MJPEG receive loop uses on
    // the Python side (see main.py's _mjpeg_url_pull_loop): if a
    // conversion is still in flight when the next frame arrives, drop
    // this one rather than queueing it — queueing is what turns a
    // slower-than-camera consumer into ever-growing lag instead of just
    // a lower effective frame rate.
    if (!mounted || !_streamingImages || _encodingFrame) return;
    final generation = _frameGeneration;
    if (_reportedBroadcastFailure) return; // already told Python this
                                            // isn't working — stop
                                            // spending CPU on frames
                                            // that'll just fail the same
                                            // way again.
    final isBgra = image.format.group == ImageFormatGroup.bgra8888;
    final isYuv = image.format.group == ImageFormatGroup.yuv420;
    if ((!isBgra && !isYuv) ||
        (isBgra && image.planes.length != 1) ||
        (isYuv && image.planes.length < 3)) {
      _reportedBroadcastFailure = true;
      widget.control.triggerEvent("error",
          "Camera broadcast failed: unsupported camera frame format.");
      return;
    }
    _encodingFrame = true;
    final controller = _controller;
    final quarterTurns = controller == null ? 0 : cameraFrameQuarterTurns(
      controller.description.sensorOrientation,
      controller.value.deviceOrientation,
      controller.description.lensDirection == CameraLensDirection.front,
    );
    final Future<Uint8List?> encoded;
    if (isBgra) {
      // AVFoundation already applies device orientation to streamed buffers.
      encoded = compute(encodeBgraCameraFrame, BgraFrameData(
        bytes: image.planes[0].bytes,
        bytesPerRow: image.planes[0].bytesPerRow,
        width: image.width, height: image.height, mirror: _mirror,
        maxWidth: _broadcastMaxWidth, quality: _broadcastQuality,
      ));
    } else {
    final args = _FrameConversionArgs(
      yPlane: image.planes[0].bytes,
      uPlane: image.planes[1].bytes,
      vPlane: image.planes[2].bytes,
      yRowStride: image.planes[0].bytesPerRow,
      uvRowStride: image.planes[1].bytesPerRow,
      uvPixelStride: image.planes[1].bytesPerPixel ?? 1,
      width: image.width,
      height: image.height,
      quarterTurns: quarterTurns,
      mirror: _mirror,
      maxWidth: _broadcastMaxWidth,
      quality: _broadcastQuality,
    );
    encoded = compute(_frameToJpeg, args);
    }
    encoded.timeout(
      const Duration(seconds: 3),
      onTimeout: () {
        // A stuck/hung isolate call, not a normal encode failure —
        // without this timeout, _encodingFrame would stay true forever
        // the very first time this ever happened, since neither
        // .then() nor .catchError() below ever fires for a Future that
        // simply never completes. Every future frame would then be
        // silently dropped by the `if (_encodingFrame) return;` guard
        // above, permanently halting broadcasting with zero error ever
        // surfaced — this is the single most likely explanation for
        // "worked fine for a while, then just silently stopped" with
        // the app still open and in the foreground the entire time.
        if (mounted && generation == _frameGeneration) _consecutiveTimeouts++;
        return null;
      },
    ).then((jpeg) {
      if (!mounted || generation != _frameGeneration) return;
      _encodingFrame = false;
      if (jpeg != null) {
        _consecutiveEncodeFailures = 0;
        _consecutiveTimeouts = 0;
        if (mounted && _streamingImages) {
          widget.control.triggerEvent("frame", base64Encode(jpeg));
        }
      } else {
        _consecutiveEncodeFailures++;
        // Repeated timeouts specifically are a much stronger "something
        // is actually stuck" signal than an occasional corrupt/slow
        // frame, so they get their own lower, faster-firing threshold
        // (~15s) rather than sharing the general encode-failure one
        // below (~30 frames, which could be a minute or more at a low
        // effective framerate) — the whole point is reporting a real
        // stall quickly instead of leaving the feed looking dead for a
        // long stretch before anything gets said about it.
        if (_consecutiveTimeouts >= 5 && !_reportedBroadcastFailure) {
          _reportedBroadcastFailure = true;
          widget.control.triggerEvent("error",
              "Camera broadcast failed: frame conversion has stalled "
              "repeatedly (timed out) — this device may be struggling "
              "to keep up with encoding its camera feed.");
          return;
        }
        // A handful of one-off failures (a corrupt/short-lived frame) is
        // normal and not worth reporting — but if EVERY frame is failing
        // to encode, that's the same "silently producing nothing"
        // problem as the plane-count check above, just discovered later.
        if (_consecutiveEncodeFailures >= 30 && !_reportedBroadcastFailure) {
          _reportedBroadcastFailure = true;
          widget.control.triggerEvent("error",
              "Camera broadcast failed: frame conversion has failed "
              "repeatedly — this device may not be able to encode its "
              "camera feed for broadcasting.");
        }
      }
    }).catchError((_) {
      if (!mounted || generation != _frameGeneration) return;
      _encodingFrame = false;
      _consecutiveEncodeFailures++;
    });
  }

  Future<void> _disposeController() async {
    final controller = _controller;
    _controller = null;
    _initializedLens = null;
    _initializedForBroadcasting = null;
    _streamingImages = false;
    _encodingFrame = false;
    _frameGeneration++;
    if (mounted) setState(() {});
    if (controller != null) {
      try {
        if (controller.value.isStreamingImages) {
          await controller.stopImageStream();
        }
      } finally {
        await controller.dispose();
      }
    }
    if (identical(_cameraOwner, this)) _cameraOwner = null;
  }

  Future<void> _maybeReinitialize() {
    // Read the latest properties when this operation runs. A lens/mode
    // change arriving during initialization is queued, never discarded.
    return _enqueueCameraOperation(_reinitialize).catchError((Object ex) {
      if (!mounted) return;
      setState(() { _lastError = ex.toString(); });
      widget.control.triggerEvent("error", ex.toString());
    });
  }

  static Future<void> _enqueueCameraOperation(Future<void> Function() action) {
    final operation = (_cameraOperations ?? Future<void>.value())
        .then((_) => action());
    // Keep the queue usable after an error, but let the caller report it.
    final settled = operation.catchError((Object _) {});
    _cameraOperations = settled;
    unawaited(settled.then((_) {
      if (identical(_cameraOperations, settled)) _cameraOperations = null;
    }));
    return operation;
  }

  bool _settingsStillCurrent(String lens, bool broadcasting) =>
      mounted &&
      widget.control.getString("lens", "back") == lens &&
      _wantsBroadcast == broadcasting;

  bool _isSurfaceCombinationError(Object ex) {
    final message = ex.toString().toLowerCase();
    return message.contains("no supported surface combination") ||
        message.contains("too many use cases");
  }

  Future<void> _reinitialize() async {
    if (!mounted) return;
    final lens = widget.control.getString("lens", "back")!;
    final wantsBroadcast = _wantsBroadcast;
    if (lens == _initializedLens &&
        wantsBroadcast == _initializedForBroadcasting) return;

    // Dispose before initialize: CameraX cannot safely bind the new
    // session while the previous session's use cases are still attached.
    if (_cameraOwner != null && !identical(_cameraOwner, this)) {
      await _cameraOwner!._disposeController();
    }
    await _disposeController();
    if (!_settingsStillCurrent(lens, wantsBroadcast)) return;
    setState(() { _lastError = null; });

    final cameras = await availableCameras();
    if (!_settingsStillCurrent(lens, wantsBroadcast)) return;
    if (cameras.isEmpty) throw Exception("No camera found on this device.");
    final direction = lens == "front"
        ? CameraLensDirection.front : CameraLensDirection.back;
    final description = cameras.firstWhere(
      (camera) => camera.lensDirection == direction,
      orElse: () => cameras.first,
    );
    final isAndroid = !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    final isIOS = !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;
    final shouldStream = wantsBroadcast && (isAndroid || isIOS);
    // The current CameraX backend binds analysis during initialize(),
    // even before startImageStream(). Preview-only can need fallback too.
    final resolutions = shouldStream
        ? [ResolutionPreset.medium, ResolutionPreset.low]
        : isAndroid
            ? [ResolutionPreset.veryHigh, ResolutionPreset.high,
               ResolutionPreset.medium, ResolutionPreset.low]
            : [ResolutionPreset.veryHigh];

    for (final resolution in resolutions) {
      final controller = CameraController(
        description, resolution, enableAudio: false,
        imageFormatGroup: isIOS ? ImageFormatGroup.bgra8888 : ImageFormatGroup.yuv420,
      );
      _controller = controller;
      _cameraOwner = this;
      try {
        await controller.initialize();
        if (!_settingsStillCurrent(lens, wantsBroadcast)) {
          await _disposeController();
          return;
        }
        _mirror = description.lensDirection == CameraLensDirection.front;
        _reportedBroadcastFailure = false;
        _consecutiveEncodeFailures = 0;
        _consecutiveTimeouts = 0;
        if (shouldStream) {
          // Await this Future so startup exceptions reach cleanup/fallback.
          await controller.startImageStream((image) {
            if (identical(_controller, controller)) _onCameraImage(image);
          });
        }
        if (!_settingsStillCurrent(lens, wantsBroadcast)) {
          await _disposeController();
          return;
        }
        _initializedLens = lens;
        _initializedForBroadcasting = wantsBroadcast;
        _streamingImages = shouldStream;
        setState(() { _lastError = null; });
        return;
      } catch (ex) {
        await _disposeController();
        if (!_settingsStillCurrent(lens, wantsBroadcast)) return;
        // Permission/busy/other errors are not resolution problems.
        if (!_isSurfaceCombinationError(ex) || resolution == resolutions.last) {
          rethrow;
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    Widget child;
    if (controller != null && controller.value.isInitialized) {
      // CameraPreview already rotates its Android texture using device
      // orientation. Applying sensor rotation again makes it sideways.
      final oriented = ValueListenableBuilder<CameraValue>(
        valueListenable: controller,
        builder: (context, value, _) => CameraPreview(controller),
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
