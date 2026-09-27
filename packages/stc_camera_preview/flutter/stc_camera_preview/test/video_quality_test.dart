import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:stc_camera_preview/src/video_quality.dart';

class Sender implements RTCRtpSender {
  bool rejectPreference = false, rejectAll = false, empty = false;
  final attempts = <RTCRtpParameters>[];
  @override
  RTCRtpParameters get parameters => RTCRtpParameters(transactionId: 'unchanged',
    encodings: empty ? [] : [RTCRtpEncoding(rid: 'video', ssrc: 42)]);
  @override
  Future<bool> setParameters(RTCRtpParameters value) async {
    attempts.add(value);
    if (rejectAll || (rejectPreference && value.degradationPreference != null)) throw StateError('Unsupported');
    return true;
  }
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('browser capture preferences allow lower resolution hardware', () {
    final video = cameraVideoConstraints(web: true, lens: 'front');
    expect(video['width'], {'ideal': 1920});
    expect(video['height'], {'ideal': 1080});
    expect(video['facingMode'], 'user');
    expect(cameraVideoConstraints(web: false, lens: 'back')['width'], 1920);
  });
  test('HD tuning preserves sender identity and leaves congestion control free', () async {
    final sender = Sender();
    expect(await configureVideoSender(sender), isTrue);
    final p = sender.attempts.single;
    expect(p.transactionId, 'unchanged');
    expect(p.encodings!.single.ssrc, 42);
    expect(p.encodings!.single.rid, 'video');
    expect(p.encodings!.single.maxBitrate, 8000000);
    expect(p.encodings!.single.minBitrate, isNull);
    expect(p.encodings!.single.scaleResolutionDownBy, 1);
  });
  test('unsupported preferences fall back without preventing streaming', () async {
    final sender = Sender()..rejectPreference = true;
    expect(await configureVideoSender(sender), isTrue);
    expect(sender.attempts.length, 2);
    expect(sender.attempts.last.degradationPreference, isNull);
    sender.rejectAll = true;
    expect(await configureVideoSender(sender), isFalse);
    sender.empty = true;
    expect(await configureVideoSender(sender), isFalse);
  });
}
