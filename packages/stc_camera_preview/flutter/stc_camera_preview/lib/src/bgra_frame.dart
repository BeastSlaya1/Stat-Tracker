import 'dart:typed_data';
import 'package:image/image.dart' as img;

/// Plain frame data suitable for Flutter compute(). Row padding is preserved.
class BgraFrameData {
  final Uint8List bytes;
  final int width, height, bytesPerRow, maxWidth, quality;
  final bool mirror;
  const BgraFrameData({required this.bytes, required this.width,
    required this.height, required this.bytesPerRow, this.mirror = false,
    this.maxWidth = 480, this.quality = 70});
}

Uint8List? encodeBgraCameraFrame(BgraFrameData frame) {
  if (frame.width <= 0 || frame.height <= 0 || frame.maxWidth <= 0 ||
      frame.bytesPerRow < frame.width * 4 ||
      frame.bytes.length < (frame.height - 1) * frame.bytesPerRow + frame.width * 4) {
    return null;
  }
  final step = (frame.width / frame.maxWidth).ceil().clamp(1, frame.width);
  final output = img.Image(width: (frame.width / step).ceil(),
      height: (frame.height / step).ceil());
  for (var y = 0; y < output.height; y++) {
    for (var x = 0; x < output.width; x++) {
      final offset = y * step * frame.bytesPerRow + x * step * 4;
      output.setPixelRgb(x, y, frame.bytes[offset + 2],
          frame.bytes[offset + 1], frame.bytes[offset]);
    }
  }
  final oriented = frame.mirror ? img.flipHorizontal(output) : output;
  return Uint8List.fromList(img.encodeJpg(oriented, quality: frame.quality));
}
