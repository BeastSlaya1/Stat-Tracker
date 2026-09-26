import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:stc_camera_preview/src/frame_orientation.dart';

void main() {
  test('back camera compensates for every device orientation', () {
    expect(cameraFrameQuarterTurns(90, DeviceOrientation.portraitUp, false), 1);
    expect(cameraFrameQuarterTurns(90, DeviceOrientation.landscapeLeft, false), 0);
    expect(cameraFrameQuarterTurns(90, DeviceOrientation.portraitDown, false), 3);
    expect(cameraFrameQuarterTurns(90, DeviceOrientation.landscapeRight, false), 2);
  });
  test('front camera uses the opposite device compensation', () {
    expect(cameraFrameQuarterTurns(270, DeviceOrientation.portraitUp, true), 3);
    expect(cameraFrameQuarterTurns(270, DeviceOrientation.landscapeLeft, true), 0);
    expect(cameraFrameQuarterTurns(270, DeviceOrientation.portraitDown, true), 1);
    expect(cameraFrameQuarterTurns(270, DeviceOrientation.landscapeRight, true), 2);
  });
}
