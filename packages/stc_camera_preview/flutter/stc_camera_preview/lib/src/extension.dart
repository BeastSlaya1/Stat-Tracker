import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';

import 'camera_preview.dart';
import 'rtc_video.dart';

// Keep the live camera and peer connection when Python moves its control
// between the workspace and fullscreen layouts. A local key restarts capture.
class _RtcVideoKey extends GlobalObjectKey {
  final int controlId;
  _RtcVideoKey(Control control) : controlId = control.id, super(control.backend);
  @override
  bool operator ==(Object other) => other is _RtcVideoKey &&
      identical(value, other.value) && controlId == other.controlId;
  @override
  int get hashCode => Object.hash(identityHashCode(value), controlId);
}

class Extension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "StcCameraPreview":
        return StcCameraPreviewControl(key: key, control: control);
      case "StcRtcVideo":
        return StcRtcVideoControl(key: _RtcVideoKey(control), control: control);
      default:
        return null;
    }
  }
}
