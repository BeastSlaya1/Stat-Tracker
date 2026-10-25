
import 'dart:async';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flet/flet.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/camera_preview.dart';

class FakeBackend implements FletBackend {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class TestControl extends Control {
  final errors = <String>[];
  TestControl({bool broadcast = false}) : super(
    id: 1, type: 'StcCameraPreview', backend: FakeBackend(),
    properties: {'lens': 'back', 'broadcasting': broadcast});
  @override
  void triggerEvent(String eventName, [dynamic data]) {
    if (eventName == 'error') errors.add(data.toString());
  }
}

class FakeCamera extends CameraPlatform {
  final events = <String>[];
  final formats = <ImageFormatGroup>[];
  final presets = <ResolutionPreset?>[];
  final names = <String>[];
  final active = <int>{};
  final streams = <int, StreamController<CameraImageData>>{};
  final errorStreams = <int, StreamController<CameraErrorEvent>>{};
  int nextId = 0;
  Completer<void>? initializeGate;
  Completer<void>? disposeGate;
  int failuresRemaining = 0;
  bool permissionFailure = false;
  bool streamFailure = false;

  @override
  Future<List<CameraDescription>> availableCameras() async => [
    const CameraDescription(name: 'back', lensDirection: CameraLensDirection.back, sensorOrientation: 90),
    const CameraDescription(name: 'front', lensDirection: CameraLensDirection.front, sensorOrientation: 90),
  ];
  @override
  Future<int> createCameraWithSettings(CameraDescription description, MediaSettings settings) async {
    if (active.isNotEmpty) throw StateError('Overlapping camera sessions: $active');
    final id = ++nextId;
    active.add(id);
    names.add(description.name);
    presets.add(settings.resolutionPreset);
    events.add('create:$id');
    return id;
  }
  @override
  Future<void> initializeCamera(int cameraId, {ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown}) async {
    formats.add(imageFormatGroup);
    events.add('initialize:$cameraId');
    final gate = initializeGate;
    initializeGate = null;
    if (gate != null) await gate.future;
    if (permissionFailure) throw PlatformException(code: 'CameraAccessDenied', message: 'Permission denied');
    if (failuresRemaining > 0) {
      failuresRemaining--;
      throw PlatformException(code: 'IllegalArgumentException', message: 'No supported surface combination is found');
    }
  }
  @override
  Stream<CameraInitializedEvent> onCameraInitialized(int cameraId) => Stream.value(
    CameraInitializedEvent(cameraId, 640, 480, ExposureMode.auto, true, FocusMode.auto, true));
  @override
  Stream<CameraErrorEvent> onCameraError(int cameraId) =>
    (errorStreams[cameraId] = StreamController<CameraErrorEvent>()).stream;
  @override
  Stream<DeviceOrientationChangedEvent> onDeviceOrientationChanged() =>
    const Stream.empty();
  @override
  bool supportsImageStreaming() => true;
  @override
  Stream<CameraImageData> onStreamedFrameAvailable(int cameraId, {CameraImageStreamOptions? options}) {
    if (streamFailure) throw PlatformException(code: 'streamFailure', message: 'Cannot start stream');
    events.add('stream:$cameraId');
    final stream = StreamController<CameraImageData>(onCancel: () { events.add('stop:$cameraId'); });
    streams[cameraId] = stream;
    return stream.stream;
  }
  @override
  Widget buildPreview(int cameraId) => const SizedBox();
  @override
  Future<void> dispose(int cameraId) async {
    events.add('dispose-start:$cameraId');
    final gate = disposeGate;
    disposeGate = null;
    if (gate != null) await gate.future;
    active.remove(cameraId);
    events.add('dispose-end:$cameraId');
  }
}

Widget screen(TestControl control, {Key? key}) => MaterialApp(home: Scaffold(
  body: StcCameraPreviewControl(key: key, control: control)));

Future<void> flush(WidgetTester tester) async {
  for (var i = 0; i < 12; i++) { await tester.pump(const Duration(milliseconds: 1)); }
  await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 10)));
  await tester.pump();
}

void androidTest(String name, WidgetTesterCallback callback) => testWidgets(name, callback, variant: TargetPlatformVariant.only(TargetPlatform.android));

void main() {
  late FakeCamera camera;
  setUp(() {

    camera = FakeCamera();
    CameraPlatform.instance = camera;
  });


  androidTest('mode change waits for old disposal and starts only one medium stream', (tester) async {
    final control = TestControl();
    await tester.pumpWidget(screen(control));
    await flush(tester);
    final release = Completer<void>();
    camera.disposeGate = release;
    control.properties['broadcasting'] = true;
    await tester.pumpWidget(screen(control));
    await flush(tester);
    expect(camera.presets, [ResolutionPreset.veryHigh]);
    release.complete();
    await flush(tester);
    expect(camera.presets, [ResolutionPreset.veryHigh, ResolutionPreset.medium]);
    expect(camera.events.where((e) => e.startsWith('stream:')), ['stream:2']);
    expect(control.errors, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
    expect(camera.active, isEmpty, reason: camera.events.join(", "));
    expect(camera.events.indexOf('stop:2'), lessThan(camera.events.indexOf('dispose-start:2')));
  });

  androidTest('mode change during initialization is not lost', (tester) async {
    final gate = Completer<void>();
    camera.initializeGate = gate;
    final control = TestControl();
    await tester.pumpWidget(screen(control));
    await flush(tester);
    control.properties['broadcasting'] = true;
    await tester.pumpWidget(screen(control));
    gate.complete();
    await flush(tester);
    expect(camera.presets, [ResolutionPreset.veryHigh, ResolutionPreset.medium]);
    expect(camera.events, contains('stream:2'));
    expect(control.errors, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
  });

  androidTest('replacing the widget releases the previous native owner first', (tester) async {
    final old = TestControl(broadcast: true);
    await tester.pumpWidget(screen(old, key: const ValueKey('old')));
    await flush(tester);
    final release = Completer<void>();
    camera.disposeGate = release;
    final next = TestControl(broadcast: true);
    await tester.pumpWidget(screen(next, key: const ValueKey('next')));
    await flush(tester);
    expect(camera.nextId, 1);
    release.complete();
    await flush(tester);
    expect(camera.nextId, 2);
    expect(next.errors, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
    expect(camera.active, isEmpty, reason: camera.events.join(", "));
  });

  androidTest('unsupported medium configuration retries low after cleanup', (tester) async {
    camera.failuresRemaining = 1;
    final control = TestControl(broadcast: true);
    await tester.pumpWidget(screen(control));
    await flush(tester);
    expect(camera.presets, [ResolutionPreset.medium, ResolutionPreset.low]);
    expect(camera.events, contains('stream:2'));
    expect(control.errors, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
  });

  androidTest('permission failure is reported once without resolution retries', (tester) async {
    camera.permissionFailure = true;
    final control = TestControl(broadcast: true);
    await tester.pumpWidget(screen(control));
    await flush(tester);
    expect(camera.nextId, 1);
    expect(camera.active, isEmpty, reason: camera.events.join(", "));
    expect(control.errors.single, contains('CameraAccessDenied'));
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
  });

  androidTest('async stream-start failure is caught and releases the camera', (tester) async {
    camera.streamFailure = true;
    final control = TestControl(broadcast: true);
    await tester.pumpWidget(screen(control));
    await flush(tester);
    expect(camera.active, isEmpty, reason: camera.events.join(", "));
    expect(control.errors.single, contains('Cannot start stream'));
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
  });

  androidTest('unmount while initializing never starts a stream', (tester) async {
    final gate = Completer<void>();
    camera.initializeGate = gate;
    final control = TestControl(broadcast: true);
    await tester.pumpWidget(screen(control));
    await flush(tester);
    await tester.pumpWidget(const SizedBox());
    gate.complete();
    await flush(tester);
    expect(camera.active, isEmpty, reason: camera.events.join(", "));
    expect(camera.events.where((e) => e.startsWith('stream:')), isEmpty);
    expect(control.errors, isEmpty);
  });
  testWidgets('iOS starts BGRA streaming without Android preview rotation', (tester) async {
    final control = TestControl(broadcast: true);
    await tester.pumpWidget(screen(control));
    await flush(tester);
    expect(camera.formats, [ImageFormatGroup.bgra8888]);
    expect(camera.events, contains('stream:1'));
    expect(find.byType(RotatedBox), findsNothing);
    expect(control.errors, isEmpty);
    await tester.pumpWidget(const SizedBox());
    await flush(tester);
    expect(camera.active, isEmpty);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

}



