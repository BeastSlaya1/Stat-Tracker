import 'package:flutter/services.dart';

/// Raw sensor buffers need rotation; CameraPreview's texture already has it.
int cameraFrameQuarterTurns(int sensorDegrees, DeviceOrientation orientation,
    bool frontFacing) {
  final deviceDegrees = switch (orientation) {
    DeviceOrientation.portraitUp => 0,
    DeviceOrientation.landscapeLeft => 90,
    DeviceOrientation.portraitDown => 180,
    DeviceOrientation.landscapeRight => 270,
  };
  return ((sensorDegrees + (frontFacing ? deviceDegrees : -deviceDegrees)) % 360) ~/ 90;
}
