import 'package:flutter_webrtc/flutter_webrtc.dart';

// Native plugins expect numeric targets; browsers support preferred constraints
// that can fall back to the closest camera mode without rejecting permission.
Map<String, dynamic> cameraVideoConstraints({required bool web, required String lens}) => {
  'facingMode': lens == 'front' ? 'user' : 'environment',
  'width': web ? {'ideal': 1920} : 1920,
  'height': web ? {'ideal': 1080} : 1080,
  'frameRate': web ? {'ideal': 30, 'max': 30} : 30,
};

// Windows uses optional.sourceId for video; deviceId alone is ignored there.
void selectCameraDevice(Map<String, dynamic> video, String deviceId, {required bool web}) {
  if (deviceId.isEmpty) throw StateError('The selected camera is unavailable. Detect cameras again.');
  video.remove('facingMode');
  video['deviceId'] = web ? {'exact': deviceId} : deviceId;
  if (!web) video['optional'] = [{'sourceId': deviceId}];
}

Future<bool> configureVideoSender(RTCRtpSender sender) async {
  // Apply after setLocalDescription, when the negotiated encoding exists.
  // Never force a minimum bitrate: congestion control must still be able to
  // reduce traffic on a weak connection. Optional tuning cannot abort a stream.
  for (final preferResolution in [true, false]) {
    try {
      final parameters = sender.parameters;
      final encodings = parameters.encodings;
      if (encodings == null || encodings.isEmpty) return false;
      for (final encoding in encodings) {
        encoding.maxBitrate = 8000000;
        encoding.maxFramerate = 30;
        encoding.scaleResolutionDownBy = 1.0;
      }
      if (preferResolution) {
        parameters.degradationPreference = RTCDegradationPreference.MAINTAIN_RESOLUTION;
      }
      if (await sender.setParameters(parameters)) return true;
    } catch (_) {
      // Older camera backends may reject degradation preferences or tuning.
    }
  }
  return false;
}
