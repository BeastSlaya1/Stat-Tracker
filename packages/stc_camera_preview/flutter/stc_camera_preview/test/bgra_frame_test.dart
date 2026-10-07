import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:stc_camera_preview/src/bgra_frame.dart';

BgraFrameData sample({int width = 64, int height = 32, int padding = 16,
    bool mirror = false, int maxWidth = 480}) {
  final stride = width * 4 + padding;
  final bytes = Uint8List((height - 1) * stride + width * 4);
  for (var y = 0; y < height; y++) {
    for (var x = 0; x < width; x++) {
      final i = y * stride + x * 4;
      bytes[i] = x < width ~/ 2 ? 0 : 255;
      bytes[i + 1] = 0;
      bytes[i + 2] = x < width ~/ 2 ? 255 : 0;
      bytes[i + 3] = 255;
    }
  }
  return BgraFrameData(bytes: bytes, width: width, height: height,
      bytesPerRow: stride, mirror: mirror, maxWidth: maxWidth, quality: 95);
}
void main() {
  test('BGRA channel order and padded rows survive JPEG conversion', () {
    final output = img.decodeJpg(encodeBgraCameraFrame(sample())!)!;
    expect(output.width, 64);
    expect(output.height, 32);
    expect(output.getPixel(8, 24).r, greaterThan(230));
    expect(output.getPixel(8, 24).b, lessThan(25));
    expect(output.getPixel(56, 24).b, greaterThan(230));
  });
  test('front camera frame mirrors horizontally', () {
    final output = img.decodeJpg(encodeBgraCameraFrame(sample(mirror: true))!)!;
    expect(output.getPixel(8, 24).b, greaterThan(230));
    expect(output.getPixel(56, 24).r, greaterThan(230));
  });
  test('non-multiple widths remain within streaming width limit', () {
    final output = img.decodeJpg(encodeBgraCameraFrame(sample(width: 641, maxWidth: 480))!)!;
    expect(output.width, 321);
    expect(output.height, 16);
  });
  test('truncated buffer and invalid dimensions are dropped', () {
    for (final frame in [
      BgraFrameData(bytes: Uint8List(10), width: 64, height: 32, bytesPerRow: 256),
      BgraFrameData(bytes: Uint8List(256), width: 64, height: 1, bytesPerRow: 4),
      BgraFrameData(bytes: Uint8List(0), width: 0, height: 0, bytesPerRow: 0),
      BgraFrameData(bytes: Uint8List(256), width: 64, height: 1, bytesPerRow: 256, maxWidth: 0),
    ]) {
      expect(encodeBgraCameraFrame(frame), isNull);
    }
  });
}
